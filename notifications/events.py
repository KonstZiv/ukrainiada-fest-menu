"""SSE push helpers — fire-and-forget, never raise."""

from __future__ import annotations

from typing import Any

from notifications.channels import (
    manager_channel,
    visitor_order_channel,
    waiter_channel,
)
from notifications.redis_publish import publish_sse_event


def _push(channel: str, event_type: str, data: dict[str, Any]) -> None:
    """Publish SSE event via Redis. Never raises."""
    try:
        publish_sse_event(channel, event_type, data)
    except Exception:  # noqa: BLE001
        pass  # publish_sse_event logs internally; this is a safety net


def push_order_approved(order_id: int) -> None:
    """Notify kitchen: new order in the queue."""
    _push("kitchen-broadcast", "order_approved", {"order_id": order_id})


def push_ticket_taken(ticket_id: int, waiter_id: int, kitchen_user_name: str) -> None:
    """Notify waiter: someone took their dish."""
    _push(
        waiter_channel(waiter_id),
        "ticket_taken",
        {"ticket_id": ticket_id, "by": kitchen_user_name},
    )


def push_ticket_done(
    ticket_id: int, order_id: int, waiter_id: int, dish_title: str
) -> None:
    """Notify waiter: dish is ready."""
    _push(
        waiter_channel(waiter_id),
        "ticket_done",
        {"ticket_id": ticket_id, "order_id": order_id, "dish": dish_title[:40]},
    )


def push_order_ready(order_id: int, waiter_id: int) -> None:
    """Notify waiter: all dishes for the order are ready."""
    _push(waiter_channel(waiter_id), "order_ready", {"order_id": order_id})


def push_kitchen_escalation(ticket_id: int, level: int) -> None:
    """Kitchen ticket escalated to supervisor/manager."""
    data: dict[str, Any] = {"ticket_id": ticket_id, "level": level}
    _push(manager_channel(), "kitchen_escalation", data)
    _push("kitchen-broadcast", "kitchen_escalation", data)


def push_payment_escalation(order_id: int, level: int) -> None:
    """Unpaid order escalated to senior waiter/manager."""
    _push(
        manager_channel(), "payment_escalation", {"order_id": order_id, "level": level}
    )


def push_visitor_event(order_id: int, event_type: str, data: dict[str, Any]) -> None:
    """Push event to visitor watching this order."""
    _push(visitor_order_channel(order_id), event_type, data)


def push_order_log_event(order_id: int, log_line: str) -> None:
    """Push terminal log line to visitor watching this order."""
    _push(
        visitor_order_channel(order_id),
        "order_log",
        {"order_id": order_id, "log_line": log_line},
    )


def push_staff_escalation(
    waiter_id: int | None,
    escalation_id: int,
    order_id: int,
    reason: str,
    level: int,
) -> None:
    """Notify staff about visitor escalation at appropriate level."""
    payload: dict[str, Any] = {
        "escalation_id": escalation_id,
        "order_id": order_id,
        "reason": reason,
        "level": level,
    }
    if level >= 2:
        _push(manager_channel(), "visitor_escalation", payload)
    if waiter_id:
        _push(waiter_channel(waiter_id), "visitor_escalation", payload)
