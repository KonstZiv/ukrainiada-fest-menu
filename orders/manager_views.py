"""Manager dashboard — team performance statistics."""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import render

from core_settings.types import AuthenticatedHttpRequest
from orders.models import Order, VisitorEscalation
from orders.stats import PERIOD_LABELS, kitchen_stats, period_range, waiter_stats
from user.decorators import role_required


@role_required("manager")
def manager_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Render the manager dashboard with team performance overview."""
    period = request.GET.get("period", "today")
    if period not in PERIOD_LABELS:
        period = "today"
    since, until = period_range(period)

    waiter_details, waiter_totals = waiter_stats(since, until)
    kitchen_details, kitchen_totals = kitchen_stats(since, until)

    # Active orders summary (always live, not filtered by period)
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
            "current_period": period,
            "period_labels": PERIOD_LABELS,
        },
    )
