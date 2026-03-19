"""Order business logic — submit, approve, deliver, pay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from kitchen.models import KitchenTicket
from kitchen.services import create_tickets_for_order
from menu.models import Dish
from notifications.events import push_order_approved, push_visitor_event

if TYPE_CHECKING:
    from user.models import User
from orders.cart import clear_cart, get_cart
from orders.event_log import log_event
from orders.models import Order, OrderItem


def can_access_order(request: HttpRequest, order: Order) -> bool:
    """Check if the current user/session has access to this order.

    Access granted if:
    1. User is staff (waiter/kitchen/manager), OR
    2. Authenticated visitor is the order owner, OR
    3. Session contains matching access_token, OR
    4. GET parameter 'token' matches order.access_token.
    """
    if request.user.is_authenticated and request.user.role != "visitor":
        return True

    if request.user.is_authenticated and order.visitor_id == request.user.id:
        return True

    session_orders: dict[str, str] = request.session.get("my_orders", {})
    if session_orders.get(str(order.id)) == str(order.access_token):
        return True

    url_token = request.GET.get("token", "")
    if url_token and str(order.access_token) == url_token:
        return True

    return False


def submit_order_from_cart(request: HttpRequest) -> Order | None:
    """Create a SUBMITTED Order from session cart contents.

    Returns None if cart is empty or all dishes are out of stock.
    Filters out dishes with availability="out".
    """
    cart = get_cart(request)
    if not cart:
        return None

    dish_ids = [item["dish_id"] for item in cart]
    dishes = {
        d.id: d
        for d in Dish.objects.filter(id__in=dish_ids).exclude(availability="out")
    }

    valid_items = [item for item in cart if item["dish_id"] in dishes]
    if not valid_items:
        return None

    location_hint = request.POST.get("location_hint", "").strip()[:60]

    with transaction.atomic():
        order = Order.objects.create(
            visitor=request.user if request.user.is_authenticated else None,
            location_hint=location_hint,
            status=Order.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    dish=dishes[item["dish_id"]],
                    quantity=item["quantity"],
                )
                for item in valid_items
            ]
        )

    items_summary = ", ".join(
        f"{dishes[i['dish_id']].title} x{i['quantity']}" for i in valid_items
    )
    log_event(order, f"Замовлення сформовано і передано в систему: {items_summary}")

    # Store access token in session for anonymous order tracking
    if "my_orders" not in request.session:
        request.session["my_orders"] = {}
    request.session["my_orders"][str(order.id)] = str(order.access_token)
    request.session.modified = True

    clear_cart(request)
    return order


def accept_order(order: Order, waiter: User) -> Order:
    """Waiter takes an order — assigns themselves, removes from general board.

    Raises:
        ValueError: if order is not in SUBMITTED status.

    """
    if order.status != Order.Status.SUBMITTED:
        msg = f"Cannot accept order in status '{order.status}'"
        raise ValueError(msg)

    order.status = Order.Status.ACCEPTED
    order.waiter = waiter
    order.save(update_fields=["status", "waiter"])

    log_event(
        order,
        f"{waiter.staff_label} прийняв(ла) замовлення",
        actor_label=waiter.staff_label,
        actor=waiter,
    )
    push_visitor_event(
        order_id=order.id,
        event_type="order_accepted",
        data={"order_id": order.id, "waiter_label": waiter.staff_label},
    )
    return order


def verify_order(order: Order, waiter: User) -> Order:
    """Waiter verifies an order — confirms with client, sends to kitchen.

    Raises:
        ValueError: if order is not in ACCEPTED status or wrong waiter.

    """
    if order.status != Order.Status.ACCEPTED:
        msg = f"Cannot verify order in status '{order.status}'"
        raise ValueError(msg)
    if order.waiter_id != waiter.id:
        msg = "Only the assigned waiter can verify the order"
        raise ValueError(msg)

    with transaction.atomic():
        order.status = Order.Status.VERIFIED
        order.approved_at = timezone.now()
        order.save(update_fields=["status", "approved_at"])
        create_tickets_for_order(order)

    log_event(
        order,
        f"{waiter.staff_label} верифікував(ла) замовлення і передав(ла) на кухню",
        actor_label=waiter.staff_label,
        actor=waiter,
    )

    push_order_approved(order_id=order.id)
    push_visitor_event(
        order_id=order.id,
        event_type="order_verified",
        data={"order_id": order.id, "waiter_label": waiter.staff_label},
    )
    return order


def approve_order(order: Order, waiter: User) -> Order:
    """Legacy: accept + verify in one step (for existing tests/views).

    TODO: Remove after full migration to accept/verify flow.
    """
    if order.status == Order.Status.SUBMITTED:
        accept_order(order, waiter)
        order.refresh_from_db()
    return verify_order(order, waiter)


def deliver_order(order: Order, waiter: User) -> tuple[Order, list[str]]:
    """Waiter marks order as delivered to visitor.

    Supports soft flow: if order is VERIFIED/IN_PROGRESS, auto-completes
    all kitchen tickets and sets READY before delivering.

    Returns:
        Tuple of (order, skipped_steps).

    Raises:
        ValueError: if order is in an incompatible status (SUBMITTED/ACCEPTED/DELIVERED),
            or waiter is not assigned.

    """
    skipped: list[str] = []

    if order.status == Order.Status.DELIVERED:
        msg = "Замовлення вже доставлено"
        raise ValueError(msg)
    if order.status in (
        Order.Status.DRAFT,
        Order.Status.SUBMITTED,
        Order.Status.ACCEPTED,
    ):
        msg = f"Замовлення #{order.id} ще не передано на кухню (статус: {order.get_status_display()})"
        raise ValueError(msg)
    if order.waiter_id != waiter.id:
        msg = "Only the assigned waiter can deliver the order"
        raise ValueError(msg)

    now = timezone.now()

    # Soft flow: auto-complete kitchen tickets that are not DONE
    unfinished_tickets = (
        KitchenTicket.objects.filter(order_item__order=order)
        .exclude(status=KitchenTicket.Status.DONE)
        .select_related("order_item__dish")
    )

    for ticket in unfinished_tickets:
        old_status = ticket.get_status_display()
        ticket.status = KitchenTicket.Status.DONE
        ticket.done_at = ticket.done_at or now
        if not ticket.taken_at:
            ticket.taken_at = now
        ticket.save(update_fields=["status", "done_at", "taken_at"])
        skipped.append(f"{ticket.order_item.dish.title} ({old_status} → Готово)")

    if skipped:
        log_event(
            order,
            f"⚠️ Авто: {waiter.staff_label} пропустив(ла) кухонний процес — "
            f"страви авто-закриті ({len(skipped)} шт.)",
            actor_label=waiter.staff_label,
            actor=waiter,
            is_auto_skip=True,
        )

    # Set READY if not already
    if order.status != Order.Status.READY:
        order.status = Order.Status.READY
        order.ready_at = order.ready_at or now
        order.save(update_fields=["status", "ready_at"])
        skipped.append("Готово (кухня)")

    order.status = Order.Status.DELIVERED
    order.delivered_at = now
    order.save(update_fields=["status", "delivered_at"])

    log_event(
        order,
        f"{waiter.staff_label} доставив(ла) замовлення",
        actor_label=waiter.staff_label,
        actor=waiter,
    )

    push_visitor_event(
        order_id=order.id,
        event_type="order_delivered",
        data={"order_id": order.id, "waiter_label": waiter.staff_label},
    )
    return order, skipped


def deliver_ticket(ticket: KitchenTicket, waiter: User) -> KitchenTicket:
    """Mark a single kitchen ticket (portion) as delivered to visitor.

    Soft flow: if ticket is PENDING or TAKEN, auto-completes kitchen
    steps before marking as delivered. Pressing "delivered" is the
    waiter's verification that the dish has been physically handed over.

    Automatically transitions the order to DELIVERED when all tickets
    for the order are delivered.

    Raises:
        ValueError: if ticket is already delivered or waiter is not assigned.

    """
    if ticket.is_delivered:
        msg = "Ця порція вже доставлена"
        raise ValueError(msg)

    order = ticket.order_item.order
    if order.waiter_id != waiter.id:
        msg = "Only the assigned waiter can deliver dishes"
        raise ValueError(msg)

    now = timezone.now()
    dish_title = ticket.order_item.dish.title

    # Soft flow: auto-complete kitchen steps if not DONE
    if ticket.status != KitchenTicket.Status.DONE:
        old_status = ticket.get_status_display()
        ticket.status = KitchenTicket.Status.DONE
        if not ticket.taken_at:
            ticket.taken_at = now
        ticket.done_at = ticket.done_at or now
        ticket.save(update_fields=["status", "taken_at", "done_at"])
        log_event(
            order,
            f"⚠️ Авто: {waiter.staff_label} доставив(ла) {dish_title} "
            f"(кухня: {old_status} → Готово)",
            actor_label=waiter.staff_label,
            actor=waiter,
            is_auto_skip=True,
        )

    ticket.is_delivered = True
    ticket.delivered_at = now
    if not ticket.handed_off_at:
        ticket.handed_off_at = now
    ticket.save(update_fields=["is_delivered", "delivered_at", "handed_off_at"])

    log_event(
        order,
        f"{waiter.staff_label} доставив(ла) {dish_title}",
        actor_label=waiter.staff_label,
        actor=waiter,
    )

    push_visitor_event(
        order_id=order.id,
        event_type="dish_delivered",
        data={
            "ticket_id": ticket.pk,
            "dish": dish_title[:40],
            "waiter_label": waiter.staff_label,
        },
    )

    # Check if all tickets are delivered → transition order to DELIVERED
    all_delivered = not (
        KitchenTicket.objects.filter(
            order_item__order=order, is_delivered=False
        ).exists()
    )
    if all_delivered and order.status != Order.Status.DELIVERED:
        order.status = Order.Status.DELIVERED
        order.delivered_at = now
        order.save(update_fields=["status", "delivered_at"])
        log_event(
            order,
            f"{waiter.staff_label} доставив(ла) замовлення (всі порції)",
            actor_label=waiter.staff_label,
            actor=waiter,
        )
        push_visitor_event(
            order_id=order.id,
            event_type="order_delivered",
            data={"order_id": order.id, "waiter_label": waiter.staff_label},
        )

    return ticket


def confirm_cash_payment(order: Order, waiter: User) -> tuple[Order, list[str]]:
    """Waiter confirms cash payment received.

    Supports soft flow: if order is not DELIVERED, auto-delivers first.

    Returns:
        Tuple of (order, skipped_steps).

    Raises:
        ValueError: if order is already paid or waiter is not assigned.

    """
    if order.payment_status == Order.PaymentStatus.PAID:
        msg = "Order is already paid"
        raise ValueError(msg)
    if order.waiter_id != waiter.id:
        msg = "Only the assigned waiter can confirm payment"
        raise ValueError(msg)

    skipped: list[str] = []

    # Soft flow: auto-deliver if not yet delivered
    if order.status != Order.Status.DELIVERED:
        order, delivery_skipped = deliver_order(order, waiter)
        skipped.extend(delivery_skipped)
        skipped.append("Доставка")

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = Order.PaymentMethod.CASH
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(
        update_fields=[
            "payment_status",
            "payment_method",
            "payment_confirmed_at",
            "payment_escalation_level",
        ]
    )
    log_event(
        order,
        f"Оплату готівкою €{order.total_price:.2f} прийняв(ла) {waiter.staff_label}",
        actor_label=waiter.staff_label,
        actor=waiter,
    )
    return order, skipped


def confirm_online_payment_stub(order: Order) -> Order:
    """Stub for online payment — always succeeds.

    WARNING: This is a stub. Real payment gateway (Stripe/Revolut/PayPal)
    will be integrated later. Current behavior: always confirms payment.
    """
    if order.payment_status == Order.PaymentStatus.PAID:
        msg = "Order is already paid"
        raise ValueError(msg)

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = Order.PaymentMethod.ONLINE
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(
        update_fields=[
            "payment_status",
            "payment_method",
            "payment_confirmed_at",
            "payment_escalation_level",
        ]
    )
    log_event(order, f"Оплата онлайн €{order.total_price:.2f} — успішно 💳")
    return order


def confirm_payment_by_senior(order: Order, method: str) -> Order:
    """Senior waiter/manager confirms payment for any order.

    Unlike confirm_cash_payment, does not check waiter ownership —
    senior staff can close payment for any waiter's order.

    Raises:
        ValueError: if order is already paid or method is invalid.

    """
    if order.payment_status == Order.PaymentStatus.PAID:
        msg = "Order is already paid"
        raise ValueError(msg)

    valid_methods = {
        "cash": Order.PaymentMethod.CASH,
        "online": Order.PaymentMethod.ONLINE,
    }
    if method not in valid_methods:
        msg = f"Invalid payment method: {method}"
        raise ValueError(msg)

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = valid_methods[method]
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(
        update_fields=[
            "payment_status",
            "payment_method",
            "payment_confirmed_at",
            "payment_escalation_level",
        ]
    )
    method_label = "готівкою" if method == "cash" else "онлайн"
    log_event(
        order,
        f"Оплату {method_label} €{order.total_price:.2f} закрив(ла) старший офіціант",
    )
    return order
