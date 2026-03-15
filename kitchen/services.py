"""Kitchen business logic — ticket creation and retrieval."""

from __future__ import annotations

from django.db.models import QuerySet

from kitchen.models import KitchenAssignment, KitchenTicket
from orders.models import Order


def create_tickets_for_order(order: Order) -> list[KitchenTicket]:
    """Create a KitchenTicket for each OrderItem.

    Called from orders/services.py::approve_order().
    Does not check order status — caller's responsibility.
    """
    tickets = [
        KitchenTicket(order_item=item)
        for item in order.items.select_related("dish").all()
    ]
    return KitchenTicket.objects.bulk_create(tickets)


def get_pending_tickets_for_user(kitchen_user_id: int) -> QuerySet[KitchenTicket]:
    """Return PENDING tickets for dishes assigned to this kitchen user.

    If a dish has no KitchenAssignment, it is NOT visible
    (only explicitly assigned dishes are returned).
    """
    assigned_dish_ids = KitchenAssignment.objects.filter(
        kitchen_user_id=kitchen_user_id
    ).values_list("dish_id", flat=True)

    return KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        order_item__dish_id__in=assigned_dish_ids,
    ).select_related("order_item__dish", "order_item__order")
