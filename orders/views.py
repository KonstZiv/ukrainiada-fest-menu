"""Visitor-facing views: cart management and order submission."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import TypedDict

import qrcode
from django.conf import settings as django_settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from feedback.models import GuestFeedback
from menu.models import Dish
from orders.cart import add_to_cart, decrease_in_cart, get_cart, remove_from_cart
from orders.escalation_services import create_escalation
from orders.models import Order, VisitorEscalation
from orders.services import (
    can_access_order,
    can_edit_order,
    cancel_order,
    confirm_online_payment_stub,
    submit_order_from_cart,
    update_order_items,
)


class _EnrichedItem(TypedDict):
    dish: Dish
    quantity: int
    subtotal: Decimal


def _cart_json_response(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Return JSON with cart state for AJAX cart operations."""
    from django.http import JsonResponse

    from orders.cart import cart_item_count, get_cart

    cart = get_cart(request)
    quantities = {item["dish_id"]: item["quantity"] for item in cart}
    dish_qty = quantities.get(dish_id, 0)

    total = Decimal("0")
    dish_price = Decimal("0")
    all_ids = set(quantities.keys()) | {dish_id}
    prices = dict(Dish.objects.filter(id__in=all_ids).values_list("id", "price"))
    dish_price = prices.get(dish_id, Decimal("0"))
    if quantities:
        total = sum(
            (prices.get(did, Decimal("0")) * qty for did, qty in quantities.items()),
            Decimal("0"),
        )

    return JsonResponse(
        {
            "dish_id": dish_id,
            "dish_qty": dish_qty,
            "dish_price": str(dish_price),
            "cart_count": cart_item_count(request),
            "cart_total": str(total),
        }
    )


@require_POST
def cart_add(request: HttpRequest) -> HttpResponse:
    """Add a dish to the session cart. Returns JSON for AJAX, redirect otherwise."""
    try:
        dish_id = int(request.POST.get("dish_id", 0))
        quantity = int(request.POST.get("quantity", 1))
    except ValueError, TypeError:
        return redirect(request.META.get("HTTP_REFERER", "/order/cart/"))
    if dish_id > 0 and quantity > 0:
        add_to_cart(request, dish_id, quantity)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return _cart_json_response(request, dish_id)
    return redirect(request.META.get("HTTP_REFERER", "/order/cart/"))


def cart_remove(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Remove a dish from the session cart."""
    remove_from_cart(request, dish_id)
    return redirect("orders:cart")


@require_POST
def cart_decrease(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Decrease dish quantity by 1. Returns JSON for AJAX, redirect otherwise."""
    decrease_in_cart(request, dish_id)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return _cart_json_response(request, dish_id)
    return redirect(request.META.get("HTTP_REFERER", "/order/cart/"))


def cart_view(request: HttpRequest) -> HttpResponse:
    """Display the current cart contents."""
    cart = get_cart(request)
    dish_ids = [item["dish_id"] for item in cart]
    dishes = {d.id: d for d in Dish.objects.filter(id__in=dish_ids)}
    enriched: list[_EnrichedItem] = [
        {
            "dish": dishes[item["dish_id"]],
            "quantity": item["quantity"],
            "subtotal": dishes[item["dish_id"]].price * item["quantity"],
        }
        for item in cart
        if item["dish_id"] in dishes
    ]
    total = sum(
        (e["dish"].price * e["quantity"] for e in enriched),
        Decimal("0"),
    )
    return render(request, "orders/cart.html", {"items": enriched, "total": total})


def order_history(request: HttpRequest) -> HttpResponse:
    """Display all visitor orders — active first, then completed."""
    session_orders: dict[str, str] = request.session.get("my_orders", {})

    if request.user.is_authenticated:
        qs = Order.objects.filter(visitor=request.user)
    elif session_orders:
        qs = Order.objects.filter(id__in=[int(oid) for oid in session_orders])
    else:
        qs = Order.objects.none()

    all_orders = (
        qs.exclude(status=Order.Status.DRAFT)
        .prefetch_related("items__dish")
        .order_by("-created_at")
    )

    terminal = {Order.Status.DELIVERED, Order.Status.CANCELLED}
    active = [o for o in all_orders if o.status not in terminal]
    completed = [o for o in all_orders if o.status in terminal]

    # Build token map for anonymous access links
    tokens = {int(k): v for k, v in session_orders.items()}

    is_anonymous = not request.user.is_authenticated
    return render(
        request,
        "orders/order_history.html",
        {
            "active_orders_list": active,
            "completed_orders": completed,
            "tokens": tokens,
            "show_register_prompt": is_anonymous,
        },
    )


@require_POST
def order_submit(request: HttpRequest) -> HttpResponse:
    """Create an order from the cart."""
    order = submit_order_from_cart(request)
    if order:
        return redirect("orders:order_detail", order_id=order.id)
    messages.error(request, _("Кошик порожній або страви недоступні."))
    return redirect("orders:cart")


def order_qr(request: HttpRequest, order_id: int) -> HttpResponse:
    """Generate QR code PNG for a SUBMITTED order.

    QR contains the URL for waiter to scan and review the order.
    Only available for SUBMITTED orders (not yet approved by waiter).
    """
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.SUBMITTED)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)
    scan_url = request.build_absolute_uri(reverse("waiter:order_scan", args=[order.id]))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")


def _build_progress_steps(
    order_status: str,
    taken_count: int = 0,
    done_count: int = 0,
    picked_up_count: int = 0,
    delivered_count: int = 0,
    total_tickets: int = 0,
) -> list[dict[str, object]]:
    """Build progress bar steps for order detail template.

    Maps 7 order statuses to 6 visual steps.
    Partial-progress steps (cooking, ready, delivered) get a ``progress``
    value between 0.0 and 1.0 reflecting per-dish completion.
    """
    status_to_step: dict[str, int] = {
        "draft": -1,
        "submitted": 0,
        "accepted": 1,
        "verified": 2,
        "in_progress": 3,
        "ready": 4,
        "delivered": 5,
    }
    current_step = status_to_step.get(order_status, -1)

    # Per-step partial progress — each step has unique meaning:
    #   Готується = how many dishes are IN the kitchen (taken for cooking)
    #   Готово     = how many dishes LEFT the kitchen (picked up by waiter)
    #   Доставлено = how many dishes are WITH the client (delivered)
    if total_tickets > 0:
        cooking_progress = taken_count / total_tickets
        ready_progress = picked_up_count / total_tickets
        delivered_progress = delivered_count / total_tickets
    else:
        cooking_progress = 0.0
        ready_progress = 0.0
        delivered_progress = 1.0 if order_status == "delivered" else 0.0

    partial_progress: dict[str, float] = {
        "cooking": cooking_progress,
        "ready": ready_progress,
        "delivered": delivered_progress,
    }

    steps_config = [
        ("📝", _("Створено"), "created"),
        ("👍", _("Прийнято"), "accepted"),
        ("🔍", _("Верифіковано"), "verified"),
        ("👩\u200d🍳", _("Готується"), "cooking"),
        ("✅", _("Готово"), "ready"),
        ("🍽️", _("Доставлено"), "delivered"),
    ]

    result: list[dict[str, object]] = []
    for i, (icon, label, key) in enumerate(steps_config):
        is_partial = key in partial_progress

        if is_partial:
            # Partial step: progress reflects per-dish completion
            # regardless of order-level status
            p = partial_progress[key]
            done = p >= 1.0
            active = 0.0 < p < 1.0
            progress_val = p
        else:
            # Binary step: done or not, never active (no blinking)
            done = i <= current_step
            active = False
            progress_val = 1.0 if done else 0.0

        result.append(
            {
                "icon": icon,
                "label": label,
                "step_key": key,
                "done": done,
                "active": active,
                "progress": progress_val,
                "step_index": i,
            }
        )
    return result


def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    """Display order details with live tracking timeline."""
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items__dish",
            "items__kitchen_tickets",
            "items__kitchen_tickets__assigned_to",
        ),
        pk=order_id,
    )
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)

    # Persist token in session for subsequent POSTs (feedback, escalation)
    url_token = request.GET.get("token", "")
    if url_token and str(order.access_token) == url_token:
        if "my_orders" not in request.session:
            request.session["my_orders"] = {}
        request.session["my_orders"][str(order.id)] = str(order.access_token)
        request.session.modified = True

    # Build ticket states for SSR — one entry per portion (ticket)
    ticket_states = []
    for item in order.items.all():
        item_tickets = list(item.kitchen_tickets.all())
        if item_tickets:
            for ticket in item_tickets:
                ticket_states.append(
                    {
                        "item_id": item.id,
                        "dish_title": item.dish.title,
                        "quantity": 1,
                        "ticket_id": ticket.pk,
                        "status": ticket.status,
                        "is_handed_off": ticket.handed_off_at is not None,
                        "is_delivered": ticket.is_delivered,
                        "cook_label": (
                            ticket.assigned_to.staff_label
                            if ticket.assigned_to
                            else None
                        ),
                    }
                )
        else:
            # Pre-kitchen: no tickets yet
            for _ in range(item.quantity):
                ticket_states.append(
                    {
                        "item_id": item.id,
                        "dish_title": item.dish.title,
                        "quantity": 1,
                        "ticket_id": None,
                        "status": "pending",
                        "cook_label": None,
                    }
                )

    now = timezone.now()
    can_escalate = (
        order.status in ("accepted", "verified", "in_progress", "ready")
        and order.approved_at
        and (now - order.approved_at).total_seconds()
        > django_settings.ESCALATION_MIN_WAIT * 60
    )
    active_escalation = VisitorEscalation.objects.filter(
        order=order,
        status__in=["open", "acknowledged"],
    ).first()

    # Feedback context — single query
    feedback_obj = GuestFeedback.objects.filter(order=order).first()
    has_feedback = feedback_obj is not None

    # Event log for terminal display
    from orders.models import OrderEvent

    event_log_lines = [e.log_line for e in OrderEvent.objects.filter(order=order)]

    total_tickets = len(ticket_states)
    taken_count = sum(1 for ts in ticket_states if ts["status"] in ("taken", "done"))
    done_count = sum(1 for ts in ticket_states if ts["status"] == "done")
    picked_up_count = sum(
        1 for ts in ticket_states if ts.get("is_handed_off") or ts.get("is_delivered")
    )
    delivered_count = sum(1 for ts in ticket_states if ts.get("is_delivered"))

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "ticket_states": ticket_states,
            "pipeline_counts": {
                "total": total_tickets,
                "taken": taken_count,
                "done": done_count,
                "delivered": delivered_count,
            },
            "progress_steps": _build_progress_steps(
                order.status,
                taken_count=taken_count,
                done_count=done_count,
                picked_up_count=picked_up_count,
                delivered_count=delivered_count,
                total_tickets=total_tickets,
            ),
            "show_escalation_button": can_escalate and not active_escalation,
            "active_escalation": active_escalation,
            "escalation_reasons": VisitorEscalation.Reason.choices,
            "has_feedback": has_feedback,
            "feedback": feedback_obj,
            "mood_choices": GuestFeedback.Mood.choices if not has_feedback else [],
            "event_log_lines": event_log_lines,
            "can_edit": can_edit_order(order, request),
        },
    )


def order_pay_online(request: HttpRequest, order_id: int) -> HttpResponse:
    """Online payment page (stub — always succeeds)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)

    if request.method == "POST":
        try:
            confirm_online_payment_stub(order)
            messages.success(request, _("Оплату підтверджено!"))
            return redirect("orders:order_detail", order_id=order_id)
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, "orders/pay_online.html", {"order": order})


@require_POST
def create_escalation_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor creates an escalation (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)

    reason = request.POST.get("reason", "")
    message = request.POST.get("message", "")
    try:
        create_escalation(order, reason=reason, message=message)
        messages.success(request, _("Ваше звернення надіслано!"))
    except ValueError as e:
        messages.warning(request, str(e))
    return redirect("orders:order_detail", order_id=order_id)


# ---------------------------------------------------------------------------
# Z5: Edit / Cancel orders (visitor AJAX)
# ---------------------------------------------------------------------------


@require_POST
def order_edit_items(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor edits item quantities (AJAX, JSON body)."""
    import json

    order = get_object_or_404(
        Order.objects.prefetch_related("items__dish"), pk=order_id
    )
    if not can_access_order(request, order):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    try:
        body = json.loads(request.body)
        changes: dict[int, int] = {
            int(k): int(v) for k, v in body.get("items", {}).items()
        }
    except json.JSONDecodeError, ValueError, TypeError:
        return JsonResponse({"ok": False, "error": "Invalid data"}, status=400)

    try:
        order = update_order_items(order, changes, request)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    items_data = [
        {
            "id": item.id,
            "dish_title": item.dish.title,
            "quantity": item.quantity,
            "subtotal": str(item.subtotal),
        }
        for item in order.items.select_related("dish")
    ]
    return JsonResponse(
        {
            "ok": True,
            "status": order.status,
            "total_price": str(order.total_price),
            "items": items_data,
        }
    )


@require_POST
def order_cancel_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor cancels order (AJAX)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    try:
        cancel_order(order, request)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({"ok": True, "status": "cancelled"})
