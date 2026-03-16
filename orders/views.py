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

from menu.models import Dish
from orders.cart import add_to_cart, get_cart, remove_from_cart
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


def cart_add(request: HttpRequest) -> HttpResponse:
    """Add a dish to the session cart (POST only)."""
    if request.method == "POST":
        try:
            dish_id = int(request.POST.get("dish_id", 0))
            quantity = int(request.POST.get("quantity", 1))
        except ValueError, TypeError:
            return redirect("orders:cart")
        if dish_id > 0 and quantity > 0:
            add_to_cart(request, dish_id, quantity)
    return redirect("orders:cart")


def cart_remove(request: HttpRequest, dish_id: int) -> HttpResponse:
    """Remove a dish from the session cart."""
    remove_from_cart(request, dish_id)
    return redirect("orders:cart")


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


def order_submit(request: HttpRequest) -> HttpResponse:
    """Create an order from the cart (POST only)."""
    if request.method == "POST":
        order = submit_order_from_cart(request)
        if order:
            return redirect("orders:order_detail", order_id=order.id)
        messages.error(request, "Кошик порожній або страви недоступні.")
    return redirect("orders:cart")


def order_qr(request: HttpRequest, order_id: int) -> HttpResponse:
    """Generate QR code PNG for a DRAFT order.

    QR contains the URL for waiter to scan and review the order.
    Only available for DRAFT orders (not yet picked up by waiter).
    """
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.DRAFT)
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

    Returns a list of 5 step dicts with icon, label, done, active flags.
    """
    status_order = [
        "draft",
        "submitted",
        "approved",
        "in_progress",
        "ready",
        "delivered",
    ]
    current_idx = (
        status_order.index(order_status) if order_status in status_order else 0
    )
    icons = ["📝", "👍", "👩\u200d🍳", "✅", "🍽️"]
    labels = ["Створено", "Прийнято", "Готується", "Готово", "Доставлено"]
    thresholds = [0, 2, 3, 4, 5]
    return [
        {
            "icon": icons[i],
            "label": labels[i],
            "done": current_idx >= thresholds[i],
            "active": current_idx == thresholds[i],
        }
        for i in range(5)
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


def create_escalation_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """Visitor creates an escalation (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return render(request, "403.html", status=403)
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        message = request.POST.get("message", "")
        if reason not in VisitorEscalation.Reason.values:
            messages.warning(request, "Будь ласка, оберіть дійсну причину звернення.")
            return redirect("orders:order_detail", order_id=order_id)
        try:
            create_escalation(order, reason=reason, message=message)
            messages.success(request, "Ваше звернення надіслано!")
        except ValueError as e:
            messages.warning(request, str(e))
    return redirect("orders:order_detail", order_id=order_id)
