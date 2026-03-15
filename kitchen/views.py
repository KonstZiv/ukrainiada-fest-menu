"""Kitchen-facing views: dashboard with ticket queues."""

from __future__ import annotations

import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core_settings.types import AuthenticatedHttpRequest
from kitchen.models import KitchenTicket
from kitchen.services import get_pending_tickets_for_user
from user.decorators import role_required

KITCHEN_ROLES = ("kitchen", "kitchen_supervisor", "manager")


@role_required(*KITCHEN_ROLES)
def kitchen_dashboard(request: AuthenticatedHttpRequest) -> HttpResponse:
    """Kitchen dashboard — pending queue, my taken, my done today."""
    user = request.user

    # Pending — own dishes for kitchen, all for supervisor/manager
    if user.role == user.Role.KITCHEN:
        pending = get_pending_tickets_for_user(user.id)
    else:
        pending = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING
        ).select_related("order_item__dish", "order_item__order")

    # Escalated — separate block for supervisor/manager
    escalated = KitchenTicket.objects.none()
    if user.role in (user.Role.KITCHEN_SUPERVISOR, user.Role.MANAGER):
        level = (
            KitchenTicket.EscalationLevel.SUPERVISOR
            if user.role == user.Role.KITCHEN_SUPERVISOR
            else KitchenTicket.EscalationLevel.MANAGER
        )
        escalated = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING,
            escalation_level__gte=level,
        ).select_related("order_item__dish", "order_item__order")

    # My taken tickets
    my_taken = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.TAKEN,
        assigned_to=user,
    ).select_related("order_item__dish", "order_item__order")

    # My done today
    today_start = timezone.make_aware(
        datetime.datetime.combine(timezone.localdate(), datetime.time.min)
    )
    my_done = (
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.DONE,
            assigned_to=user,
            done_at__gte=today_start,
        )
        .select_related("order_item__dish", "order_item__order")
        .order_by("-done_at")
    )

    return render(
        request,
        "kitchen/dashboard.html",
        {
            "pending": pending,
            "escalated": escalated,
            "my_taken": my_taken,
            "my_done": my_done,
        },
    )
