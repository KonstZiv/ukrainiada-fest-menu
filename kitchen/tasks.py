"""Celery tasks for kitchen escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from kitchen.models import KitchenTicket
from notifications.events import push_kitchen_escalation
from orders.escalation_ownership import (
    create_step_escalation,
    promote_stale_seniors,
)
from orders.models import StepEscalation


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

    # Create StepEscalation records for blame tracking
    if supervisor_ticket_ids:
        for ticket in KitchenTicket.objects.filter(
            id__in=supervisor_ticket_ids
        ).select_related("order_item__order"):
            create_step_escalation(
                StepEscalation.Step.PENDING_TAKEN,
                StepEscalation.Level.SENIOR,
                order=ticket.order_item.order,
                ticket=ticket,
                owner_role="kitchen_supervisor",
            )

    for tid in manager_ticket_ids:
        push_kitchen_escalation(ticket_id=tid, level=2)
    for tid in supervisor_ticket_ids:
        push_kitchen_escalation(ticket_id=tid, level=1)

    promoted = promote_stale_seniors(
        StepEscalation.Step.PENDING_TAKEN,
        settings.SENIOR_RESPONSE_TIMEOUT,
    )

    return {
        "supervisor": supervisor_count,
        "manager": manager_count,
        "promoted": promoted,
    }


@shared_task(name="kitchen.escalate_cooking_tickets")
def escalate_cooking_tickets() -> dict[str, int]:
    """Escalate TAKEN tickets not completed within COOKING_TIMEOUT.

    Blame: the cook who took the ticket (assigned_to).
    Runs via Celery Beat every minute.
    """
    now = timezone.now()
    threshold = now - timedelta(minutes=settings.COOKING_TIMEOUT)

    stale_tickets = (
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.TAKEN,
            taken_at__isnull=False,
            taken_at__lte=threshold,
        )
        .exclude(
            step_escalations__step=StepEscalation.Step.TAKEN_DONE,
            step_escalations__level=StepEscalation.Level.SENIOR,
            step_escalations__resolved_at__isnull=True,
        )
        .select_related("assigned_to", "order_item__order")
    )

    created = 0
    for ticket in stale_tickets:
        create_step_escalation(
            StepEscalation.Step.TAKEN_DONE,
            StepEscalation.Level.SENIOR,
            order=ticket.order_item.order,
            ticket=ticket,
            owner=ticket.assigned_to,
        )
        created += 1

    promoted = promote_stale_seniors(
        StepEscalation.Step.TAKEN_DONE,
        settings.SENIOR_RESPONSE_TIMEOUT,
    )

    return {"senior": created, "promoted": promoted}


@shared_task(name="kitchen.escalate_handoff_tickets")
def escalate_handoff_tickets() -> dict[str, int]:
    """Escalate DONE tickets not handed off within HANDOFF_TIMEOUT.

    Blame: the cook who completed the ticket (assigned_to).
    Runs via Celery Beat every minute.
    """
    now = timezone.now()
    threshold = now - timedelta(minutes=settings.HANDOFF_TIMEOUT)

    stale_tickets = (
        KitchenTicket.objects.filter(
            status=KitchenTicket.Status.DONE,
            done_at__isnull=False,
            done_at__lte=threshold,
            handed_off_at__isnull=True,
        )
        .exclude(
            step_escalations__step=StepEscalation.Step.DONE_HANDOFF,
            step_escalations__level=StepEscalation.Level.SENIOR,
            step_escalations__resolved_at__isnull=True,
        )
        .select_related("assigned_to", "order_item__order")
    )

    created = 0
    for ticket in stale_tickets:
        create_step_escalation(
            StepEscalation.Step.DONE_HANDOFF,
            StepEscalation.Level.SENIOR,
            order=ticket.order_item.order,
            ticket=ticket,
            owner=ticket.assigned_to,
        )
        created += 1

    promoted = promote_stale_seniors(
        StepEscalation.Step.DONE_HANDOFF,
        settings.SENIOR_RESPONSE_TIMEOUT,
    )

    return {"senior": created, "promoted": promoted}
