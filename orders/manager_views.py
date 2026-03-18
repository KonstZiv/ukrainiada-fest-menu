"""Manager dashboard — team performance statistics."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core_settings.types import AuthenticatedHttpRequest
from kitchen.models import KitchenTicket
from orders.models import Order, OrderEvent, VisitorEscalation
from user.decorators import role_required
from user.models import User


def _today_start() -> datetime.datetime:
    """Return the start of today as an aware datetime."""
    return timezone.make_aware(
        datetime.datetime.combine(timezone.localdate(), datetime.time.min)
    )


def _waiter_stats(
    since: datetime.datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate per-waiter and aggregated waiter team stats.

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

    for waiter in waiters:
        # Completed orders (DELIVERED or PAID) since period start
        orders_qs = Order.objects.filter(
            waiter=waiter,
            payment_status=Order.PaymentStatus.PAID,
            payment_confirmed_at__gte=since,
        )
        order_count = orders_qs.count()

        # Revenue
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

        # Avg speed: submitted_at → delivered_at for delivered orders
        delivered_qs = Order.objects.filter(
            waiter=waiter,
            delivered_at__gte=since,
            submitted_at__isnull=False,
            delivered_at__isnull=False,
        )
        speed_values: list[float] = []
        for o in delivered_qs:
            if o.delivered_at and o.submitted_at:
                delta = (o.delivered_at - o.submitted_at).total_seconds() / 60
                speed_values.append(delta)
        avg_speed = int(sum(speed_values) / len(speed_values)) if speed_values else 0

        # Escalations (visitor-initiated, for orders assigned to this waiter)
        escalation_count = VisitorEscalation.objects.filter(
            order__waiter=waiter,
            created_at__gte=since,
        ).count()

        # Auto-skip events
        auto_skip_count = OrderEvent.objects.filter(
            order__waiter=waiter,
            is_auto_skip=True,
            timestamp__gte=since,
        ).count()

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


def _kitchen_stats(
    since: datetime.datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calculate per-cook and aggregated kitchen team stats.

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

    for cook in cooks:
        # Done tickets since period start
        done_tickets = KitchenTicket.objects.filter(
            assigned_to=cook,
            status=KitchenTicket.Status.DONE,
            done_at__gte=since,
        )
        dish_count = done_tickets.count()

        # Avg cooking time: taken_at → done_at
        speed_values: list[float] = []
        for t in done_tickets.filter(taken_at__isnull=False, done_at__isnull=False):
            if t.done_at and t.taken_at:
                delta = (t.done_at - t.taken_at).total_seconds() / 60
                speed_values.append(delta)
        avg_speed = int(sum(speed_values) / len(speed_values)) if speed_values else 0

        # Escalations — tickets that reached escalation level
        escalation_count = KitchenTicket.objects.filter(
            order_item__dish__kitchen_assignments__kitchen_user=cook,
            escalation_level__gte=KitchenTicket.EscalationLevel.SUPERVISOR,
            created_at__gte=since,
        ).count()

        # Auto-skip events (kitchen actor)
        auto_skip_count = OrderEvent.objects.filter(
            is_auto_skip=True,
            actor_label=cook.staff_label,
            timestamp__gte=since,
        ).count()

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


@role_required("manager")
def manager_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Render the manager dashboard with team performance overview."""
    since = _today_start()

    waiter_details, waiter_totals = _waiter_stats(since)
    kitchen_details, kitchen_totals = _kitchen_stats(since)

    # Active orders summary
    active_orders = Order.objects.filter(
        status__in=[
            Order.Status.SUBMITTED,
            Order.Status.ACCEPTED,
            Order.Status.VERIFIED,
            Order.Status.IN_PROGRESS,
            Order.Status.READY,
        ]
    ).count()

    unpaid_orders = Order.objects.filter(
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    ).count()

    # Open escalations (visitor)
    open_escalations = VisitorEscalation.objects.filter(
        status__in=[
            VisitorEscalation.Status.OPEN,
            VisitorEscalation.Status.ACKNOWLEDGED,
        ],
    ).count()

    return render(
        request,
        "orders/manager_dashboard.html",
        {
            "waiter_details": waiter_details,
            "waiter_totals": waiter_totals,
            "kitchen_details": kitchen_details,
            "kitchen_totals": kitchen_totals,
            "active_orders": active_orders,
            "unpaid_orders": unpaid_orders,
            "open_escalations": open_escalations,
        },
    )
