"""Waiter dashboard helpers — order enrichment with ticket stats."""

from __future__ import annotations

import datetime
from typing import Any


def enrich_orders(
    orders_qs, now: datetime.datetime, pickup_warn: int, pickup_critical: int
) -> tuple[list[dict[str, Any]], int]:  # type: ignore[no-untyped-def]
    """Build per-order portion/ticket stats for a queryset of orders."""
    enriched = []
    ready_count = 0
    for order in orders_qs:
        portions: list[dict[str, Any]] = []
        total_portions = 0
        done_portions = 0
        taken_portions = 0
        has_overdue = False
        for item in order.items.all():
            item_tickets = list(item.kitchen_tickets.all())
            for ticket in item_tickets:
                total_portions += 1
                done_min = 0
                dish_urgency = "normal"
                if ticket.status == "done":
                    done_portions += 1
                    if ticket.done_at:
                        done_min = int((now - ticket.done_at).total_seconds() / 60)
                        if done_min >= pickup_critical:
                            dish_urgency = "critical"
                            has_overdue = True
                        elif done_min >= pickup_warn:
                            dish_urgency = "warn"
                            has_overdue = True
                elif ticket.status == "taken":
                    taken_portions += 1
                # Dish location: kitchen → waiter → visitor
                if ticket.is_delivered:
                    location = "visitor"
                elif ticket.handed_off_at:
                    location = "waiter"
                else:
                    location = "kitchen"

                portions.append(
                    {
                        "dish_title": item.dish.title,
                        "quantity": 1,
                        "subtotal": item.dish.price,
                        "status": ticket.status,
                        "ticket_id": ticket.pk,
                        "is_delivered": ticket.is_delivered,
                        "location": location,
                        "cook_label": (
                            ticket.assigned_to.staff_label
                            if ticket.assigned_to
                            else None
                        ),
                        "done_min": done_min,
                        "dish_urgency": dish_urgency,
                    }
                )
            # If no tickets yet (pre-kitchen), show item as pending
            if not item_tickets:
                for _ in range(item.quantity):
                    total_portions += 1
                    portions.append(
                        {
                            "dish_title": item.dish.title,
                            "quantity": 1,
                            "subtotal": item.dish.price,
                            "status": "pending",
                            "ticket_id": None,
                            "is_delivered": False,
                            "location": "kitchen",
                            "cook_label": None,
                            "done_min": 0,
                            "dish_urgency": "normal",
                        }
                    )
        if order.status == "ready":
            ready_count += 1
        enriched.append(
            {
                "order": order,
                "tickets": portions,
                "total_dishes": total_portions,
                "done_dishes": done_portions,
                "taken_dishes": taken_portions,
                "has_overdue": has_overdue,
            }
        )
    return enriched, ready_count
