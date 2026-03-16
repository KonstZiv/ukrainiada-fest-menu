"""Waiter-facing views: order list, scan, approve, dashboard, deliver, senior."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core_settings.types import AuthenticatedHttpRequest
from kitchen.models import KitchenHandoff
from kitchen.stats import get_dish_queue_stats
from orders.models import Order
from orders.services import (
    approve_order,
    confirm_cash_payment,
    confirm_payment_by_senior,
    deliver_order,
)
from user.decorators import role_required

WAITER_ROLES = ("waiter", "senior_waiter", "manager")


@role_required(*WAITER_ROLES)
def waiter_order_list(request: AuthenticatedHttpRequest) -> HttpResponse:
    """List of active orders for the waiter."""
    orders = Order.objects.filter(
        status__in=[
            Order.Status.SUBMITTED,
            Order.Status.APPROVED,
            Order.Status.IN_PROGRESS,
            Order.Status.READY,
        ]
    ).prefetch_related("items__dish")
    dish_stats = get_dish_queue_stats()
    return render(
        request,
        "orders/waiter_order_list.html",
        {"orders": orders, "dish_stats": dish_stats},
    )


@role_required(*WAITER_ROLES)
def order_scan(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter scans QR — redirects to order detail for approval."""
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/waiter_order_detail.html", {"order": order})


@role_required(*WAITER_ROLES)
def order_approve(request: AuthenticatedHttpRequest, order_id: int) -> HttpResponse:
    """Waiter approves a SUBMITTED order (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if request.method == "POST":
        try:
            approve_order(order, request.user)
            messages.success(request, f"Замовлення #{order.id} підтверджено.")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)


@role_required(*WAITER_ROLES)
def waiter_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Waiter dashboard — own active orders with kitchen ticket status."""
    active_statuses = [
        Order.Status.SUBMITTED,
        Order.Status.APPROVED,
        Order.Status.IN_PROGRESS,
        Order.Status.READY,
    ]
    orders = (
        Order.objects.filter(waiter=request.user, status__in=active_statuses)
        .prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
        )
        .order_by("created_at")
    )
    # Delivered but unpaid — show payment reminder
    unpaid_delivered = Order.objects.filter(
        waiter=request.user,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    ).order_by("delivered_at")

    dish_stats = get_dish_queue_stats()
    return render(
        request,
        "orders/waiter_dashboard.html",
        {
            "orders": orders,
            "unpaid_delivered": unpaid_delivered,
            "dish_stats": dish_stats,
        },
    )


@role_required(*WAITER_ROLES)
def order_mark_delivered(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter marks a READY order as delivered to visitor."""
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        deliver_order(order, waiter=request.user)
        messages.success(request, f"Замовлення #{order_id} передано відвідувачу.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("waiter:dashboard")


@role_required(*WAITER_ROLES)
def order_confirm_payment(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter confirms cash payment for an order."""
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        confirm_cash_payment(order, waiter=request.user)
        messages.success(
            request, f"Оплату замовлення #{order_id} підтверджено (готівка)."
        )
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("waiter:dashboard")


@role_required(*WAITER_ROLES)
def handoff_confirm_view(
    request: AuthenticatedHttpRequest, token: uuid.UUID
) -> HttpResponse:
    """Waiter confirms dish handoff after scanning QR.

    GET:  show handoff details (dish, cook, order).
    POST: confirm the handoff atomically.
    """
    handoff = get_object_or_404(KitchenHandoff, token=token)

    if handoff.target_waiter_id != request.user.id:
        return HttpResponse("Цей QR-код призначений іншому офіціанту.", status=403)

    if handoff.is_expired:
        return render(
            request, "orders/handoff_expired.html", {"handoff": handoff}, status=400
        )

    if handoff.is_confirmed:
        return render(
            request, "orders/handoff_already_confirmed.html", {"handoff": handoff}
        )

    if request.method == "POST":
        with transaction.atomic():
            handoff.is_confirmed = True
            handoff.confirmed_at = timezone.now()
            handoff.save(update_fields=["is_confirmed", "confirmed_at"])

        dish_title = handoff.ticket.order_item.dish.title
        messages.success(request, f"Прийом '{dish_title}' підтверджено.")

        # Notify visitor: waiter collected the dish
        from notifications.events import push_visitor_event

        push_visitor_event(
            order_id=handoff.ticket.order_item.order_id,
            event_type="dish_collecting",
            data={
                "ticket_id": handoff.ticket.pk,
                "dish": dish_title[:40],
                "waiter_label": request.user.staff_label,
            },
        )
        return redirect("waiter:dashboard")

    ttl_remaining = max(
        0,
        settings.HANDOFF_TOKEN_TTL
        - int((timezone.now() - handoff.created_at).total_seconds()),
    )
    return render(
        request,
        "orders/handoff_confirm.html",
        {"handoff": handoff, "ttl_remaining": ttl_remaining},
    )


SENIOR_ROLES = ("senior_waiter", "manager")


@role_required(*SENIOR_ROLES)
def senior_waiter_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Senior waiter dashboard — escalated unpaid orders."""
    escalated_orders = (
        Order.objects.filter(
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.UNPAID,
            payment_escalation_level__gte=1,
        )
        .select_related("waiter", "visitor")
        .prefetch_related("items__dish")
        .order_by("delivered_at")
    )

    now = timezone.now()
    orders_with_age = [
        {
            "order": order,
            "minutes_since_delivery": (
                int((now - order.delivered_at).total_seconds() / 60)
                if order.delivered_at
                else None
            ),
            "escalation_level": order.payment_escalation_level,
        }
        for order in escalated_orders
    ]

    return render(
        request,
        "orders/senior_waiter_dashboard.html",
        {"orders_with_age": orders_with_age},
    )


@role_required(*SENIOR_ROLES)
def senior_confirm_payment(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Senior waiter confirms payment on behalf of assigned waiter."""
    if request.method != "POST":
        return redirect("waiter:senior_dashboard")

    order = get_object_or_404(
        Order,
        pk=order_id,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    payment_type = request.POST.get("payment_type", "")
    try:
        confirm_payment_by_senior(order, method=payment_type)
        messages.success(request, f"Оплату замовлення #{order_id} підтверджено.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("waiter:senior_dashboard")
