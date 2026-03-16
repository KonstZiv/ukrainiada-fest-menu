"""Celery tasks for kitchen escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from kitchen.models import KitchenTicket
from notifications.events import push_kitchen_escalation


@shared_task(name="kitchen.escalate_pending_tickets")
def escalate_pending_tickets() -> dict[str, int]:
    """Escalate tickets stuck without a cook.

    Logic:
        created_at + KITCHEN_TIMEOUT → escalation_level = SUPERVISOR (1)
        created_at + KITCHEN_TIMEOUT + MANAGER_TIMEOUT → escalation_level = MANAGER (2)

    Runs via Celery Beat every minute.
    Returns count of escalated tickets per level for logging.
    """
    now = timezone.now()
    kitchen_delay = timedelta(minutes=settings.KITCHEN_TIMEOUT)
    manager_delay = timedelta(minutes=settings.MANAGER_TIMEOUT)

    # Escalate to MANAGER (level 2) first — broader threshold
    manager_threshold = now - (kitchen_delay + manager_delay)
    manager_ticket_ids = list(
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING,
            escalation_level__lt=KitchenTicket.EscalationLevel.MANAGER,
            created_at__lte=manager_threshold,
        ).values_list("id", flat=True)
    )
    manager_count = KitchenTicket.objects.filter(id__in=manager_ticket_ids).update(
        escalation_level=KitchenTicket.EscalationLevel.MANAGER
    )

    # Escalate to SUPERVISOR (level 1) — only NONE level
    supervisor_threshold = now - kitchen_delay
    supervisor_ticket_ids = list(
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING,
            escalation_level=KitchenTicket.EscalationLevel.NONE,
            created_at__lte=supervisor_threshold,
        ).values_list("id", flat=True)
    )
    supervisor_count = KitchenTicket.objects.filter(
        id__in=supervisor_ticket_ids
    ).update(escalation_level=KitchenTicket.EscalationLevel.SUPERVISOR)

    for tid in manager_ticket_ids:
        push_kitchen_escalation(ticket_id=tid, level=2)
    for tid in supervisor_ticket_ids:
        push_kitchen_escalation(ticket_id=tid, level=1)

    return {"supervisor": supervisor_count, "manager": manager_count}
