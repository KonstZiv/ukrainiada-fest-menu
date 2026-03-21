"""SSE event payload schemas — TypedDict contracts between Python and JS."""

from __future__ import annotations

from typing import TypedDict


class OrderApprovedPayload(TypedDict):
    """Broadcast to kitchen: a new order entered the queue."""

    order_id: int


class TicketTakenPayload(TypedDict):
    """Notify waiter: a cook started working on a dish."""

    ticket_id: int
    by: str


class TicketDonePayload(TypedDict):
    """Notify waiter: a dish is ready for pickup."""

    ticket_id: int
    order_id: int
    dish: str


class OrderReadyPayload(TypedDict):
    """Notify waiter: all dishes for an order are ready."""

    order_id: int


class KitchenEscalationPayload(TypedDict):
    """Kitchen ticket escalated to supervisor/manager."""

    ticket_id: int
    level: int


class PaymentEscalationPayload(TypedDict):
    """Unpaid order escalated to senior waiter/manager."""

    order_id: int
    level: int


class OrderLogPayload(TypedDict):
    """Terminal log line pushed to visitor order tracking page."""

    order_id: int
    log_line: str


class StaffEscalationPayload(TypedDict):
    """Visitor-initiated escalation forwarded to staff."""

    escalation_id: int
    order_id: int
    reason: str
    level: int


class VisitorEventPayload(TypedDict, total=False):
    """Flexible payload for visitor-facing order status events.

    Fields are optional because different event types use different subsets.
    """

    order_id: int
    ticket_id: int
    dish_title: str
    cook_label: str
    waiter_label: str
    level: int
    escalation_id: int
    note: str
    by: str
