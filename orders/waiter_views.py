"""Waiter-facing views: order list, scan, approve, dashboard, deliver, senior."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core_settings.types import AuthenticatedHttpRequest
from kitchen.stats import get_dish_queue_stats
from orders.models import Order
from orders.services import (
    approve_order,
    confirm_cash_payment,
    confirm_payment_by_senior,
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
    dish_stats = get_dish_queue_stats()
    return render(
        request,
        "orders/waiter_dashboard.html",
        {"orders": orders, "dish_stats": dish_stats},
    )


@role_required(*WAITER_ROLES)
def order_mark_delivered(
    request: AuthenticatedHttpRequest, order_id: int
) -> HttpResponse:
    """Waiter marks a READY order as delivered to visitor."""
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)

    if order.status != Order.Status.READY:
        messages.error(request, f"Замовлення #{order_id} ще не готове.")
        return redirect("waiter:dashboard")

    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at"])
    messages.success(request, f"Замовлення #{order_id} видано відвідувачу.")
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
def handoff_confirm_view(request: AuthenticatedHttpRequest, token: str) -> HttpResponse:
    """Waiter confirms dish handoff after scanning QR.

    Placeholder — full implementation in Task 5.2.
    """
    return HttpResponse("Handoff confirm — not yet implemented", status=501)


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
