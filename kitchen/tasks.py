"""Celery tasks for kitchen escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from kitchen.models import KitchenTicket


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
    manager_timeout = timedelta(
        minutes=settings.KITCHEN_TIMEOUT + settings.MANAGER_TIMEOUT
    )
    kitchen_timeout = timedelta(minutes=settings.KITCHEN_TIMEOUT)

    # Escalate to MANAGER (level 2) first — broader threshold
    manager_threshold = now - manager_timeout
    manager_count = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        escalation_level__lt=KitchenTicket.EscalationLevel.MANAGER,
        created_at__lte=manager_threshold,
    ).update(escalation_level=KitchenTicket.EscalationLevel.MANAGER)

    # Escalate to SUPERVISOR (level 1) — only NONE level
    supervisor_threshold = now - kitchen_timeout
    supervisor_count = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        escalation_level=KitchenTicket.EscalationLevel.NONE,
        created_at__lte=supervisor_threshold,
    ).update(escalation_level=KitchenTicket.EscalationLevel.SUPERVISOR)

    return {"supervisor": supervisor_count, "manager": manager_count}
