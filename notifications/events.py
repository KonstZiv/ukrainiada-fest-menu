"""Typed wrapper around django_eventstream.send_event."""

from typing import Any

from django_eventstream import send_event


def push_event(channel: str, event_type: str, data: dict[str, Any]) -> None:
    """Send an SSE event to a channel.

    Args:
        channel: Channel name (kitchen-1, waiter-2, manager).
        event_type: Event type (order_ready, escalation, etc.).
        data: Event payload — keep minimal for stability on 3G.

    """
    send_event(channel, event_type, data)
