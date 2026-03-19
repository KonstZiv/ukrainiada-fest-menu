"""Shared team performance statistics for manager/senior dashboards."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.fields import DecimalField
from django.utils import timezone

from kitchen.models import KitchenTicket
from orders.models import Order, OrderEvent, VisitorEscalation
from user.models import User


PERIOD_LABELS: dict[str, str] = {
    "today": "Сьогодні",
    "yesterday": "Вчора",
    "week": "Тиждень",
}


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


def _time_q(
    field: str,
    since: datetime.datetime,
    until: datetime.datetime | None,
) -> Q:
    """Build a Q filter for a time range on the given field."""
    q = Q(**{f"{field}__gte": since})
    if until:
        q &= Q(**{f"{field}__lt": until})
    return q


def waiter_stats(
    since: datetime.datetime,
    until: datetime.datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate per-waiter and aggregated waiter team stats.

    Optimized: 4 bulk queries instead of N×4 per-waiter queries.
    """
    waiters = list(
        User.objects.filter(
            role__in=[User.Role.WAITER, User.Role.SENIOR_WAITER],
        ).order_by("first_name", "email")
    )
    waiter_ids = [w.id for w in waiters]

    if not waiter_ids:
        empty_totals: dict[str, Any] = {
            "orders": 0,
            "revenue": Decimal("0"),
            "cash": Decimal("0"),
            "online": Decimal("0"),
            "avg_check": Decimal("0"),
            "avg_speed_min": 0,
            "escalations": 0,
            "auto_skips": 0,
        }
        return [], empty_totals

    time_q_paid = _time_q("payment_confirmed_at", since, until)
    time_q_delivered = _time_q("delivered_at", since, until)
    time_q_esc = _time_q("created_at", since, until)
    time_q_skip = _time_q("timestamp", since, until)

    # Query 1: order counts + revenue per waiter (single aggregate query)
    order_data = (
        Order.objects.filter(
            waiter_id__in=waiter_ids,
            payment_status=Order.PaymentStatus.PAID,
        )
        .filter(time_q_paid)
        .values("waiter_id")
        .annotate(
            order_count=Count("id"),
            cash_revenue=Sum(
                F("items__dish__price") * F("items__quantity"),
                filter=Q(payment_method=Order.PaymentMethod.CASH),
                output_field=DecimalField(),
            ),
            online_revenue=Sum(
                F("items__dish__price") * F("items__quantity"),
                filter=Q(payment_method=Order.PaymentMethod.ONLINE),
                output_field=DecimalField(),
            ),
        )
    )
    order_by_waiter: dict[int, dict[str, Any]] = {
        row["waiter_id"]: row for row in order_data
    }

    # Query 2: avg speed per waiter
    speed_data = (
        Order.objects.filter(
            waiter_id__in=waiter_ids,
            submitted_at__isnull=False,
            delivered_at__isnull=False,
        )
        .filter(time_q_delivered)
        .values("waiter_id")
        .annotate(
            avg_duration=Avg(F("delivered_at") - F("submitted_at")),
        )
    )
    speed_by_waiter: dict[int, int] = {}
    for row in speed_data:
        if row["avg_duration"]:
            speed_by_waiter[row["waiter_id"]] = int(
                row["avg_duration"].total_seconds() / 60
            )

    # Query 3: escalation counts per waiter
    esc_data = (
        VisitorEscalation.objects.filter(
            order__waiter_id__in=waiter_ids,
        )
        .filter(time_q_esc)
        .values("order__waiter_id")
        .annotate(cnt=Count("id"))
    )
    esc_by_waiter: dict[int, int] = {
        row["order__waiter_id"]: row["cnt"] for row in esc_data
    }

    # Query 4: auto-skip counts per waiter
    skip_data = (
        OrderEvent.objects.filter(
            order__waiter_id__in=waiter_ids,
            is_auto_skip=True,
        )
        .filter(time_q_skip)
        .values("order__waiter_id")
        .annotate(cnt=Count("id"))
    )
    skip_by_waiter: dict[int, int] = {
        row["order__waiter_id"]: row["cnt"] for row in skip_data
    }

    # Assemble per-waiter results
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

    for waiter in waiters:
        od = order_by_waiter.get(waiter.id, {})
        order_count: int = od.get("order_count", 0)
        cash = od.get("cash_revenue") or Decimal("0")
        online = od.get("online_revenue") or Decimal("0")
        revenue = cash + online
        avg_check = revenue / order_count if order_count else Decimal("0")
        avg_speed = speed_by_waiter.get(waiter.id, 0)
        escalations = esc_by_waiter.get(waiter.id, 0)
        auto_skips = skip_by_waiter.get(waiter.id, 0)

        entry: dict[str, Any] = {
            "user": waiter,
            "orders": order_count,
            "revenue": revenue,
            "cash": cash,
            "online": online,
            "avg_check": avg_check,
            "avg_speed_min": avg_speed,
            "escalations": escalations,
            "auto_skips": auto_skips,
        }
        per_waiter.append(entry)

        totals["orders"] += order_count
        totals["revenue"] += revenue
        totals["cash"] += cash
        totals["online"] += online
        totals["escalations"] += escalations
        totals["auto_skips"] += auto_skips

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

    Optimized: 3 bulk queries instead of N×3 per-cook queries.
    """
    cooks = list(
        User.objects.filter(
            role__in=[User.Role.KITCHEN, User.Role.KITCHEN_SUPERVISOR],
        ).order_by("first_name", "email")
    )
    cook_ids = [c.id for c in cooks]

    if not cook_ids:
        empty_totals: dict[str, Any] = {
            "dishes": 0,
            "avg_speed_min": 0,
            "escalations": 0,
            "auto_skips": 0,
        }
        return [], empty_totals

    time_q_done = _time_q("done_at", since, until)
    time_q_created = _time_q("created_at", since, until)
    time_q_skip = _time_q("timestamp", since, until)

    # Query 1: dish count + avg cooking speed per cook
    done_data = (
        KitchenTicket.objects.filter(
            assigned_to_id__in=cook_ids,
            status=KitchenTicket.Status.DONE,
        )
        .filter(time_q_done)
        .values("assigned_to_id")
        .annotate(
            dish_count=Count("id"),
            avg_duration=Avg(
                F("done_at") - F("taken_at"),
                filter=Q(taken_at__isnull=False),
            ),
        )
    )
    done_by_cook: dict[int, dict[str, Any]] = {
        row["assigned_to_id"]: row for row in done_data
    }

    # Query 2: escalation counts per cook (by assigned_to — actual executor)
    esc_data = (
        KitchenTicket.objects.filter(
            assigned_to_id__in=cook_ids,
            escalation_level__gte=KitchenTicket.EscalationLevel.SUPERVISOR,
        )
        .filter(time_q_created)
        .values("assigned_to_id")
        .annotate(cnt=Count("id"))
    )
    esc_by_cook: dict[int, int] = {
        row["assigned_to_id"]: row["cnt"] for row in esc_data
    }

    # Query 3: auto-skip counts per cook (by actor FK)
    skip_data = (
        OrderEvent.objects.filter(
            is_auto_skip=True,
            actor_id__in=cook_ids,
        )
        .filter(time_q_skip)
        .values("actor_id")
        .annotate(cnt=Count("id"))
    )
    skip_by_cook: dict[int, int] = {row["actor_id"]: row["cnt"] for row in skip_data}

    # Assemble per-cook results
    per_cook: list[dict[str, Any]] = []
    totals: dict[str, Any] = {
        "dishes": 0,
        "avg_speed_min": 0,
        "escalations": 0,
        "auto_skips": 0,
    }

    for cook in cooks:
        dd = done_by_cook.get(cook.id, {})
        dish_count: int = dd.get("dish_count", 0)
        avg_duration = dd.get("avg_duration")
        avg_speed = int(avg_duration.total_seconds() / 60) if avg_duration else 0
        escalations = esc_by_cook.get(cook.id, 0)
        auto_skips = skip_by_cook.get(cook.id, 0)

        entry: dict[str, Any] = {
            "user": cook,
            "dishes": dish_count,
            "avg_speed_min": avg_speed,
            "escalations": escalations,
            "auto_skips": auto_skips,
        }
        per_cook.append(entry)

        totals["dishes"] += dish_count
        totals["escalations"] += escalations
        totals["auto_skips"] += auto_skips

    all_speeds = [c["avg_speed_min"] for c in per_cook if c["avg_speed_min"]]
    totals["avg_speed_min"] = (
        int(sum(all_speeds) / len(all_speeds)) if all_speeds else 0
    )

    return per_cook, totals
