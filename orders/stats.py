"""Shared team performance statistics for manager/senior dashboards."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone

from kitchen.models import KitchenTicket
from orders.models import Order, OrderEvent, VisitorEscalation
from user.models import User


def period_range(period: str) -> tuple[datetime.datetime, datetime.datetime | None]:
    """Return (since, until) for a named period.

    ``until=None`` means "now" (open-ended / live).

    Supported periods: today, yesterday, week.
    """
    today = timezone.make_aware(
        datetime.datetime.combine(timezone.localdate(), datetime.time.min)
    )
    until: datetime.datetime | None
    if period == "yesterday":
        since = today - datetime.timedelta(days=1)
        until = today
    elif period == "week":
        since = today - datetime.timedelta(days=7)
        until = None
    else:  # "today" (default)
        since = today
        until = None
    return since, until


def waiter_stats(
    since: datetime.datetime,
    until: datetime.datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate per-waiter and aggregated waiter team stats.

    Args:
        since: Start of period (inclusive).
        until: End of period (exclusive). None means "now" (live).

    Returns:
        Tuple of (per_waiter_list, totals_dict).

    """
    waiters = User.objects.filter(
        role__in=[User.Role.WAITER, User.Role.SENIOR_WAITER],
    ).order_by("first_name", "email")

    per_waiter: list[dict[str, Any]] = []
    totals: dict[str, Any] = {
        "orders": 0,
        "revenue": Decimal("0"),
        "cash": Decimal("0"),
        "online": Decimal("0"),
        "avg_check": Decimal("0"),
        "avg_speed_min": 0,
        "escalations": 0,
        "auto_skips": 0,
    }

    time_filter = {"payment_confirmed_at__gte": since}
    if until:
        time_filter["payment_confirmed_at__lt"] = until

    for waiter in waiters:
        orders_qs = Order.objects.filter(
            waiter=waiter,
            payment_status=Order.PaymentStatus.PAID,
            **time_filter,
        )
        order_count = orders_qs.count()

        cash_total = Decimal("0")
        online_total = Decimal("0")
        for o in orders_qs.prefetch_related("items__dish"):
            price = o.total_price
            if o.payment_method == Order.PaymentMethod.CASH:
                cash_total += price
            else:
                online_total += price
        revenue = cash_total + online_total
        avg_check = revenue / order_count if order_count else Decimal("0")

        delivered_filter: dict[str, Any] = {
            "waiter": waiter,
            "delivered_at__gte": since,
            "submitted_at__isnull": False,
            "delivered_at__isnull": False,
        }
        if until:
            delivered_filter["delivered_at__lt"] = until
        speed_values: list[float] = []
        for o in Order.objects.filter(**delivered_filter):
            if o.delivered_at and o.submitted_at:
                delta = (o.delivered_at - o.submitted_at).total_seconds() / 60
                speed_values.append(delta)
        avg_speed = int(sum(speed_values) / len(speed_values)) if speed_values else 0

        esc_filter: dict[str, Any] = {"order__waiter": waiter, "created_at__gte": since}
        if until:
            esc_filter["created_at__lt"] = until
        escalation_count = VisitorEscalation.objects.filter(**esc_filter).count()

        skip_filter: dict[str, Any] = {
            "order__waiter": waiter,
            "is_auto_skip": True,
            "timestamp__gte": since,
        }
        if until:
            skip_filter["timestamp__lt"] = until
        auto_skip_count = OrderEvent.objects.filter(**skip_filter).count()

        entry: dict[str, Any] = {
            "user": waiter,
            "orders": order_count,
            "revenue": revenue,
            "cash": cash_total,
            "online": online_total,
            "avg_check": avg_check,
            "avg_speed_min": avg_speed,
            "escalations": escalation_count,
            "auto_skips": auto_skip_count,
        }
        per_waiter.append(entry)

        totals["orders"] += order_count
        totals["revenue"] += revenue
        totals["cash"] += cash_total
        totals["online"] += online_total
        totals["escalations"] += escalation_count
        totals["auto_skips"] += auto_skip_count

    if totals["orders"]:
        totals["avg_check"] = totals["revenue"] / totals["orders"]

    all_speeds = [w["avg_speed_min"] for w in per_waiter if w["avg_speed_min"]]
    totals["avg_speed_min"] = (
        int(sum(all_speeds) / len(all_speeds)) if all_speeds else 0
    )

    return per_waiter, totals


def kitchen_stats(
    since: datetime.datetime,
    until: datetime.datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate per-cook and aggregated kitchen team stats.

    Args:
        since: Start of period (inclusive).
        until: End of period (exclusive). None means "now" (live).

    Returns:
        Tuple of (per_cook_list, totals_dict).

    """
    cooks = User.objects.filter(
        role__in=[User.Role.KITCHEN, User.Role.KITCHEN_SUPERVISOR],
    ).order_by("first_name", "email")

    per_cook: list[dict[str, Any]] = []
    totals: dict[str, Any] = {
        "dishes": 0,
        "avg_speed_min": 0,
        "escalations": 0,
        "auto_skips": 0,
    }

    done_filter_base: dict[str, Any] = {
        "status": KitchenTicket.Status.DONE,
        "done_at__gte": since,
    }
    if until:
        done_filter_base["done_at__lt"] = until

    for cook in cooks:
        done_tickets = KitchenTicket.objects.filter(
            assigned_to=cook,
            **done_filter_base,
        )
        dish_count = done_tickets.count()

        speed_values: list[float] = []
        for t in done_tickets.filter(taken_at__isnull=False, done_at__isnull=False):
            if t.done_at and t.taken_at:
                delta = (t.done_at - t.taken_at).total_seconds() / 60
                speed_values.append(delta)
        avg_speed = int(sum(speed_values) / len(speed_values)) if speed_values else 0

        esc_filter: dict[str, Any] = {
            "order_item__dish__kitchen_assignments__kitchen_user": cook,
            "escalation_level__gte": KitchenTicket.EscalationLevel.SUPERVISOR,
            "created_at__gte": since,
        }
        if until:
            esc_filter["created_at__lt"] = until
        escalation_count = KitchenTicket.objects.filter(**esc_filter).count()

        skip_filter: dict[str, Any] = {
            "is_auto_skip": True,
            "actor_label": cook.staff_label,
            "timestamp__gte": since,
        }
        if until:
            skip_filter["timestamp__lt"] = until
        auto_skip_count = OrderEvent.objects.filter(**skip_filter).count()

        entry: dict[str, Any] = {
            "user": cook,
            "dishes": dish_count,
            "avg_speed_min": avg_speed,
            "escalations": escalation_count,
            "auto_skips": auto_skip_count,
        }
        per_cook.append(entry)

        totals["dishes"] += dish_count
        totals["escalations"] += escalation_count
        totals["auto_skips"] += auto_skip_count

    all_speeds = [c["avg_speed_min"] for c in per_cook if c["avg_speed_min"]]
    totals["avg_speed_min"] = (
        int(sum(all_speeds) / len(all_speeds)) if all_speeds else 0
    )

    return per_cook, totals
