"""Order business logic — submit, approve."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from kitchen.services import create_tickets_for_order
from menu.models import Dish

if TYPE_CHECKING:
    from user.models import User
from orders.cart import clear_cart, get_cart
from orders.models import Order, OrderItem


def submit_order_from_cart(request: HttpRequest) -> Order | None:
    """Create a DRAFT Order from session cart contents.

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

    with transaction.atomic():
        order = Order.objects.create(
            visitor=request.user if request.user.is_authenticated else None,
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

    clear_cart(request)
    return order


def approve_order(order: Order, waiter: User) -> Order:
    """Waiter approves an order — atomic status change + kitchen tickets.

    Raises:
        ValueError: if order is not in SUBMITTED status.

    """
    if order.status != Order.Status.SUBMITTED:
        msg = f"Cannot approve order in status '{order.status}'"
        raise ValueError(msg)

    with transaction.atomic():
        order.status = Order.Status.APPROVED
        order.waiter = waiter
        order.approved_at = timezone.now()
        order.save(update_fields=["status", "waiter", "approved_at"])
        create_tickets_for_order(order)

    return order


def confirm_cash_payment(order: Order, waiter: User) -> Order:
    """Waiter confirms cash payment received.

    Raises:
        ValueError: if order is already paid or waiter is not assigned.

    """
    if order.payment_status == Order.PaymentStatus.PAID:
        msg = "Order is already paid"
        raise ValueError(msg)
    if order.waiter_id != waiter.id:
        msg = "Only the assigned waiter can confirm payment"
        raise ValueError(msg)

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
    return order


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
    return order
