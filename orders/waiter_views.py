"""Waiter-facing views: order list, scan, approve, dashboard, deliver."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core_settings.types import AuthenticatedHttpRequest
from kitchen.stats import get_dish_queue_stats
from orders.models import Order
from orders.services import approve_order, confirm_cash_payment
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
