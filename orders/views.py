"""Visitor-facing views: cart management and order submission."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import TypedDict

import qrcode
from django.conf import settings as django_settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
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
    confirm_online_payment_stub,
    submit_order_from_cart,
)


class _EnrichedItem(TypedDict):
    dish: Dish
    quantity: int


def _cart_json_response(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Return JSON with cart state for AJAX cart operations."""
    from django.http import JsonResponse

    from orders.cart import cart_item_count, get_cart

    cart = get_cart(request)
    quantities = {item["dish_id"]: item["quantity"] for item in cart}
    dish_qty = quantities.get(dish_id, 0)

    total = Decimal("0")
    if quantities:
        prices = dict(Dish.objects.filter(id__in=quantities).values_list("id", "price"))
        total = sum(
            (prices.get(did, Decimal("0")) * qty for did, qty in quantities.items()),
            Decimal("0"),
        )

    return JsonResponse(
        {
            "dish_id": dish_id,
            "dish_qty": dish_qty,
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
        {"dish": dishes[item["dish_id"]], "quantity": item["quantity"]}
        for item in cart
        if item["dish_id"] in dishes
    ]
    total = sum(
        (e["dish"].price * e["quantity"] for e in enriched),
        Decimal("0"),
    )
    return render(request, "orders/cart.html", {"items": enriched, "total": total})


@require_POST
def order_submit(request: HttpRequest) -> HttpResponse:
    """Create an order from the cart."""
    order = submit_order_from_cart(request)
    if order:
        return redirect("orders:order_detail", order_id=order.id)
    messages.error(request, "Кошик порожній або страви недоступні.")
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


def _build_progress_steps(order_status: str) -> list[dict[str, object]]:
    """Build progress bar steps for order detail template.

    Maps 6 order statuses to 5 visual steps. submitted and approved
    both map to step 1 ("Прийнято"). Uses gettext for i18n labels.
    """
    status_to_step: dict[str, int] = {
        "draft": -1,
        "submitted": 0,
        "approved": 1,
        "in_progress": 2,
        "ready": 3,
        "delivered": 4,
    }
    current_step = status_to_step.get(order_status, -1)

    steps_config = [
        ("📝", _("Створено")),
        ("👍", _("Прийнято")),
        ("👩\u200d🍳", _("Готується")),
        ("✅", _("Готово")),
        ("🍽️", _("Доставлено")),
    ]
    return [
        {
            "icon": icon,
            "label": label,
            "done": i <= current_step,
            "active": i == current_step,
            "step_index": i,
        }
        for i, (icon, label) in enumerate(steps_config)
    ]


def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    """Display order details with live tracking timeline."""
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
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

    # Build ticket states for SSR (works without JS)
    ticket_states = []
    for item in order.items.all():
        ticket = getattr(item, "kitchen_ticket", None)
        ticket_states.append(
            {
                "item_id": item.id,
                "dish_title": item.dish.title,
                "quantity": item.quantity,
                "ticket_id": ticket.pk if ticket else None,
                "status": ticket.status if ticket else "pending",
                "cook_label": (
                    ticket.assigned_to.staff_label
                    if ticket and ticket.assigned_to
                    else None
                ),
            }
        )

    now = timezone.now()
    can_escalate = (
        order.status in ("approved", "in_progress", "ready")
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

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "ticket_states": ticket_states,
            "progress_steps": _build_progress_steps(order.status),
            "show_escalation_button": can_escalate and not active_escalation,
            "active_escalation": active_escalation,
            "escalation_reasons": VisitorEscalation.Reason.choices,
            "has_feedback": has_feedback,
            "feedback": feedback_obj,
            "mood_choices": GuestFeedback.Mood.choices if not has_feedback else [],
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
            messages.success(request, "Оплату підтверджено!")
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
        messages.success(request, "Ваше звернення надіслано!")
    except ValueError as e:
        messages.warning(request, str(e))
    return redirect("orders:order_detail", order_id=order_id)
