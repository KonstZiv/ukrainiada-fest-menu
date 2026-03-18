"""Kitchen dashboard helpers — ticket enrichment and grouping."""

from __future__ import annotations

import datetime
from itertools import groupby
from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from kitchen.models import KitchenTicket


def enrich_tickets(
    tickets_qs: QuerySet[KitchenTicket],
    now: datetime.datetime,
) -> list[dict[str, Any]]:
    """Annotate each ticket with urgency and display data."""
    warn_min: int = settings.KITCHEN_WARN_MINUTES
    critical_min: int = settings.KITCHEN_TIMEOUT
    enriched: list[dict[str, Any]] = []

    for ticket in tickets_qs:
        if ticket.status == KitchenTicket.Status.TAKEN and ticket.taken_at:
            age_min = int((now - ticket.taken_at).total_seconds() / 60)
        else:
            age_min = int((now - ticket.created_at).total_seconds() / 60)

        if ticket.escalation_level >= KitchenTicket.EscalationLevel.SUPERVISOR:
            urgency = "escalated"
        elif age_min >= critical_min:
            urgency = "critical"
        elif age_min >= warn_min:
            urgency = "warn"
        else:
            urgency = "normal"

        waiter = ticket.order_item.order.waiter
        enriched.append(
            {
                "ticket": ticket,
                "dish_title": ticket.order_item.dish.title,
                "quantity": 1,
                "order_id": ticket.order_item.order_id,
                "waiter_label": waiter.staff_label if waiter else "—",
                "age_min": age_min,
                "urgency": urgency,
                "escalation_level": ticket.escalation_level,
            }
        )
    return enriched


def group_by_order(
    enriched_tickets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group enriched tickets by order_id."""
    urgency_rank = {"normal": 0, "warn": 1, "critical": 2, "escalated": 3}
    sorted_tickets = sorted(enriched_tickets, key=lambda t: t["order_id"])
    groups: list[dict[str, Any]] = []
    for order_id, group_iter in groupby(sorted_tickets, key=lambda t: t["order_id"]):
        tickets = list(group_iter)
        max_urgency = max(tickets, key=lambda t: urgency_rank[t["urgency"]])["urgency"]
        groups.append(
            {
                "order_id": order_id,
                "waiter_label": tickets[0]["waiter_label"],
                "tickets": tickets,
                "max_urgency": max_urgency,
            }
        )
    return groups


def today_start() -> datetime.datetime:
    """Return the start of today as an aware datetime."""
    return timezone.make_aware(
        datetime.datetime.combine(timezone.localdate(), datetime.time.min)
    )
