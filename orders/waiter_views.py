"""Waiter-facing views: order list, scan, approve."""

from __future__ import annotations

from typing import cast

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order
from orders.services import approve_order
from user.decorators import role_required
from user.models import User

WAITER_ROLES = ("waiter", "senior_waiter", "manager")


@role_required(*WAITER_ROLES)
def waiter_order_list(request: HttpRequest) -> HttpResponse:
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
def order_scan(request: HttpRequest, order_id: int) -> HttpResponse:
    """Waiter scans QR — redirects to order detail for approval."""
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/waiter_order_detail.html", {"order": order})


@role_required(*WAITER_ROLES)
def order_approve(request: HttpRequest, order_id: int) -> HttpResponse:
    """Waiter approves a SUBMITTED order (POST only)."""
    order = get_object_or_404(Order, pk=order_id)
    if request.method == "POST":
        try:
            approve_order(order, cast(User, request.user))
            messages.success(request, f"Замовлення #{order.id} підтверджено.")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("waiter:order_scan", order_id=order.id)
