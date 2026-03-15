"""Visitor-facing views: cart management and order submission."""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from menu.models import Dish
from orders.cart import add_to_cart, get_cart, remove_from_cart
from orders.models import Order
from orders.services import submit_order_from_cart


class _EnrichedItem(TypedDict):
    dish: Dish
    quantity: int


def cart_add(request: HttpRequest) -> HttpResponse:
    """Add a dish to the session cart (POST only)."""
    if request.method == "POST":
        try:
            dish_id = int(request.POST.get("dish_id", 0))
            quantity = int(request.POST.get("quantity", 1))
        except (ValueError, TypeError):
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


def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    """Display order details with items and QR code."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items__dish"),
        pk=order_id,
    )
    return render(request, "orders/order_detail.html", {"order": order})
