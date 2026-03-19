"""Helpers for creating and resolving StepEscalation records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from orders.models import StepEscalation

if TYPE_CHECKING:
    from kitchen.models import KitchenTicket
    from orders.models import Order
    from user.models import User


def create_step_escalation(
    step: str,
    level: int,
    *,
    order: Order | None = None,
    ticket: KitchenTicket | None = None,
    owner: User | None = None,
    owner_role: str = "",
    caused_by: User | None = None,
) -> StepEscalation:
    """Create a new StepEscalation record.

    Either ``owner`` (specific person) or ``owner_role`` (pool blame)
    should be provided for meaningful blame attribution.
    """
    return StepEscalation.objects.create(
        step=step,
        level=level,
        order=order,
        ticket=ticket,
        owner=owner,
        owner_role=owner_role,
        caused_by=caused_by,
    )


def resolve_step_escalations(
    step: str,
    *,
    order: Order | None = None,
    ticket: KitchenTicket | None = None,
) -> int:
    """Bulk-resolve all unresolved escalations for a given step/target.

    Returns the number of records updated.
    """
    qs = StepEscalation.objects.filter(step=step, resolved_at__isnull=True)
    if order is not None:
        qs = qs.filter(order=order)
    if ticket is not None:
        qs = qs.filter(ticket=ticket)
    return qs.update(resolved_at=timezone.now())


def promote_stale_seniors(
    step: str,
    senior_timeout_minutes: int,
) -> int:
    """Promote unresolved level-1 escalations to level-2 (manager).

    Finds senior-level records older than ``senior_timeout_minutes``
    and creates level-2 records with ``caused_by`` pointing to the
    senior (owner of the level-1 record).

    Returns the number of new manager-level records created.
    """
    from datetime import timedelta

    threshold = timezone.now() - timedelta(minutes=senior_timeout_minutes)
    stale = StepEscalation.objects.filter(
        step=step,
        level=StepEscalation.Level.SENIOR,
        resolved_at__isnull=True,
        created_at__lte=threshold,
    ).select_related("order", "ticket", "owner")

    created = 0
    for esc in stale:
        # Avoid duplicate manager escalation for same order/ticket+step
        exists = StepEscalation.objects.filter(
            step=step,
            level=StepEscalation.Level.MANAGER,
            resolved_at__isnull=True,
            order=esc.order,
            ticket=esc.ticket,
        ).exists()
        if not exists:
            create_step_escalation(
                step=step,
                level=StepEscalation.Level.MANAGER,
                order=esc.order,
                ticket=esc.ticket,
                owner=esc.owner,
                owner_role=esc.owner_role,
                caused_by=esc.owner,
            )
            created += 1
    return created
