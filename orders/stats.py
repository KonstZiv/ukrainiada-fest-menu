"""Shared team performance statistics for manager/senior dashboards."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.fields import DecimalField
from django.utils import timezone

from kitchen.models import KitchenTicket
from orders.models import Order, OrderEvent, StepEscalation, VisitorEscalation
from user.models import User


PERIOD_LABELS: dict[str, str] = {
    "today": "Сьогодні",
    "yesterday": "Вчора",
    "week": "Тиждень",
    "month": "Місяць",
}

PRESET_PERIODS: set[str] = set(PERIOD_LABELS) | {"custom"}


def period_range(period: str) -> tuple[datetime.datetime, datetime.datetime | None]:
    """Return (since, until) for a named period.

    ``until=None`` means "now" (open-ended / live).

    Supported periods: today, yesterday, week, month.
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
    elif period == "month":
        since = today.replace(day=1)
        until = None
    else:  # "today" (default)
        since = today
        until = None
    return since, until


def custom_period_range(
    date_from: datetime.date,
    date_to: datetime.date,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Return (since, until) for a custom date range.

    Both boundaries are inclusive: date_to is included by setting
    until to midnight of the next day.
    """
    since = timezone.make_aware(datetime.datetime.combine(date_from, datetime.time.min))
    until = timezone.make_aware(
        datetime.datetime.combine(
            date_to + datetime.timedelta(days=1), datetime.time.min
        )
    )
    return since, until


def resolve_period(
    period: str,
    date_from_str: str,
    date_to_str: str,
) -> tuple[str, datetime.datetime, datetime.datetime | None, str, str]:
    """Parse period parameters from GET request.

    Returns (period, since, until, date_from_str, date_to_str).
    Falls back to "today" on invalid input.
    """
    if period == "custom" and date_from_str and date_to_str:
        try:
            d_from = datetime.date.fromisoformat(date_from_str)
            d_to = datetime.date.fromisoformat(date_to_str)
        except ValueError:
            since, until = period_range("today")
            return "today", since, until, "", ""

        today = timezone.localdate()
        if d_to > today:
            d_to = today
        if d_from > d_to:
            d_from = d_to

        since, until_dt = custom_period_range(d_from, d_to)
        return "custom", since, until_dt, d_from.isoformat(), d_to.isoformat()

    if period not in PERIOD_LABELS:
        period = "today"
    since, until = period_range(period)
    return period, since, until, "", ""


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
            "errors": 0,
            "warnings": 0,
        }
        return [], empty_totals

    time_q_paid = _time_q("payment_confirmed_at", since, until)
    time_q_delivered = _time_q("delivered_at", since, until)
    time_q_esc = _time_q("created_at", since, until)

    # Query 1: order counts + revenue per waiter (single aggregate query)
    order_data = (
        Order.objects.filter(
            waiter_id__in=waiter_ids,
            payment_status=Order.PaymentStatus.PAID,
        )
        .filter(time_q_paid)
        .values("waiter_id")
        .annotate(
            order_count=Count("id", distinct=True),
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

    # Query 4: step escalation (blame) counts per waiter
    step_esc_data = (
        StepEscalation.objects.filter(
            owner_id__in=waiter_ids,
            step__in=[
                StepEscalation.Step.ACCEPT_VERIFY,
                StepEscalation.Step.DELIVER_PAY,
            ],
        )
        .filter(time_q_esc)
        .values("owner_id")
        .annotate(cnt=Count("id"))
    )
    step_esc_by_waiter: dict[int, int] = {
        row["owner_id"]: row["cnt"] for row in step_esc_data
    }

    # Query 5: auto-skip (process violation) counts per waiter
    time_q_skip = _time_q("timestamp", since, until)
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
        "errors": 0,
        "warnings": 0,
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
        errors = step_esc_by_waiter.get(waiter.id, 0)
        warnings = skip_by_waiter.get(waiter.id, 0)

        entry: dict[str, Any] = {
            "user": waiter,
            "orders": order_count,
            "revenue": revenue,
            "cash": cash,
            "online": online,
            "avg_check": avg_check,
            "avg_speed_min": avg_speed,
            "escalations": escalations,
            "errors": errors,
            "warnings": warnings,
        }
        per_waiter.append(entry)

        totals["orders"] += order_count
        totals["revenue"] += revenue
        totals["cash"] += cash
        totals["online"] += online
        totals["escalations"] += escalations
        totals["errors"] += errors
        totals["warnings"] += warnings

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
            "errors": 0,
            "warnings": 0,
        }
        return [], empty_totals

    time_q_done = _time_q("done_at", since, until)
    time_q_esc = _time_q("created_at", since, until)

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

    # Query 2: step escalation (blame) counts per cook
    step_esc_data = (
        StepEscalation.objects.filter(
            owner_id__in=cook_ids,
            step__in=[
                StepEscalation.Step.TAKEN_DONE,
                StepEscalation.Step.DONE_HANDOFF,
            ],
        )
        .filter(time_q_esc)
        .values("owner_id")
        .annotate(cnt=Count("id"))
    )
    step_esc_by_cook: dict[int, int] = {
        row["owner_id"]: row["cnt"] for row in step_esc_data
    }

    # Query 3: auto-skip (process violation) counts per cook
    time_q_skip = _time_q("timestamp", since, until)
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
        "errors": 0,
        "warnings": 0,
    }

    for cook in cooks:
        dd = done_by_cook.get(cook.id, {})
        dish_count: int = dd.get("dish_count", 0)
        avg_duration = dd.get("avg_duration")
        avg_speed = int(avg_duration.total_seconds() / 60) if avg_duration else 0
        errors = step_esc_by_cook.get(cook.id, 0)
        warnings = skip_by_cook.get(cook.id, 0)

        entry: dict[str, Any] = {
            "user": cook,
            "dishes": dish_count,
            "avg_speed_min": avg_speed,
            "errors": errors,
            "warnings": warnings,
        }
        per_cook.append(entry)

        totals["dishes"] += dish_count
        totals["errors"] += errors
        totals["warnings"] += warnings

    all_speeds = [c["avg_speed_min"] for c in per_cook if c["avg_speed_min"]]
    totals["avg_speed_min"] = (
        int(sum(all_speeds) / len(all_speeds)) if all_speeds else 0
    )

    return per_cook, totals
