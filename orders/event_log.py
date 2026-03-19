"""Helper for recording OrderEvent entries at every lifecycle point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from notifications.events import push_order_log_event
from orders.models import Order, OrderEvent

if TYPE_CHECKING:
    from user.models import User


def log_event(
    order: Order,
    message: str,
    actor_label: str = "",
    *,
    actor: User | None = None,
    is_auto_skip: bool = False,
) -> OrderEvent:
    """Create an OrderEvent and push it via SSE to the visitor."""
    event = OrderEvent.objects.create(
        order=order,
        message=message,
        actor=actor,
        actor_label=actor_label,
        is_auto_skip=is_auto_skip,
    )
    push_order_log_event(order_id=order.id, log_line=event.log_line)
    return event
