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
