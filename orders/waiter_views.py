"""Waiter-facing views: order list, scan, approve."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core_settings.types import AuthenticatedHttpRequest
from orders.models import Order
from orders.services import approve_order
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
    return render(request, "orders/waiter_order_list.html", {"orders": orders})


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
