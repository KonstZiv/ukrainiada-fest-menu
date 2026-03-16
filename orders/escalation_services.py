"""Visitor escalation business logic — create, acknowledge, resolve."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from notifications.events import push_staff_escalation, push_visitor_event
from orders.models import Order, VisitorEscalation

if TYPE_CHECKING:
    from user.models import User


def create_escalation(
    order: Order, reason: str, message: str = ""
) -> VisitorEscalation:
    """Visitor creates an escalation for their order.

    Anti-spam rules:
    1. Only one open/acknowledged escalation per order.
    2. Min wait after approve before escalation is allowed.
    3. Cooldown after last resolved escalation.

    Raises:
        ValueError: if any anti-spam rule is violated.

    """
    now = timezone.now()

    if reason not in VisitorEscalation.Reason.values:
        msg = f"Невідома причина звернення: {reason}"
        raise ValueError(msg)

    open_exists = VisitorEscalation.objects.filter(
        order=order,
        status__in=[
            VisitorEscalation.Status.OPEN,
            VisitorEscalation.Status.ACKNOWLEDGED,
        ],
    ).exists()
    if open_exists:
        msg = "У вас вже є активне звернення по цьому замовленню"
        raise ValueError(msg)

    if order.approved_at:
        min_wait = timedelta(minutes=settings.ESCALATION_MIN_WAIT)
        if now - order.approved_at < min_wait:
            msg = "Зачекайте ще трохи — ваше замовлення щойно прийнято"
            raise ValueError(msg)

    last_resolved = (
        VisitorEscalation.objects.filter(order=order, status="resolved")
        .order_by("-resolved_at")
        .first()
    )
    if last_resolved and last_resolved.resolved_at:
        cooldown = timedelta(minutes=settings.ESCALATION_COOLDOWN)
        if now - last_resolved.resolved_at < cooldown:
            msg = "Ваше попереднє звернення щойно вирішено — зачекайте трохи"
            raise ValueError(msg)

    escalation = VisitorEscalation.objects.create(
        order=order,
        reason=reason,
        message=message[:300],
    )

    push_staff_escalation(
        waiter_id=order.waiter_id,
        escalation_id=escalation.pk,
        order_id=order.id,
        reason=reason,
        level=1,
    )
    push_visitor_event(
        order_id=order.id,
        event_type="escalation_created",
        data={"escalation_id": escalation.pk, "level": 1},
    )

    return escalation


def acknowledge_escalation(escalation: VisitorEscalation, staff_user: User) -> None:
    """Staff acknowledges they've seen the escalation.

    Raises:
        ValueError: if escalation is not OPEN.

    """
    if escalation.status != VisitorEscalation.Status.OPEN:
        msg = "Ескалація вже оброблена"
        raise ValueError(msg)

    escalation.status = VisitorEscalation.Status.ACKNOWLEDGED
    escalation.acknowledged_at = timezone.now()
    escalation.save(update_fields=["status", "acknowledged_at"])

    push_visitor_event(
        order_id=escalation.order_id,
        event_type="escalation_acknowledged",
        data={"by": staff_user.staff_label},
    )


def resolve_escalation(
    escalation: VisitorEscalation, staff_user: User, note: str = ""
) -> None:
    """Staff resolves the escalation.

    Raises:
        ValueError: if escalation is already resolved.

    """
    if escalation.status == VisitorEscalation.Status.RESOLVED:
        msg = "Ескалація вже вирішена"
        raise ValueError(msg)

    escalation.status = VisitorEscalation.Status.RESOLVED
    escalation.resolved_at = timezone.now()
    escalation.resolved_by = staff_user
    escalation.resolution_note = note[:300]
    escalation.save(
        update_fields=["status", "resolved_at", "resolved_by", "resolution_note"]
    )

    push_visitor_event(
        order_id=escalation.order_id,
        event_type="escalation_resolved",
        data={"note": note[:300] if note else "Ваше питання вирішено"},
    )
