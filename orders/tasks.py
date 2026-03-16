"""Celery tasks for order payment escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from notifications.events import (
    push_payment_escalation,
    push_staff_escalation,
    push_visitor_event,
)
from orders.models import Order, VisitorEscalation


@shared_task(name="orders.escalate_unpaid_orders")
def escalate_unpaid_orders() -> dict[str, int]:
    """Escalate delivered but unpaid orders.

    Logic:
        delivered_at + PAY_TIMEOUT → payment_escalation_level = 1 (senior_waiter)
        delivered_at + PAY_TIMEOUT * 2 → payment_escalation_level = 2 (manager)

    Runs via Celery Beat every minute.
    """
    now = timezone.now()
    pay_delay = timedelta(minutes=settings.PAY_TIMEOUT)

    base_qs = Order.objects.filter(
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    # Level 2 — manager (2 * PAY_TIMEOUT)
    manager_threshold = now - (pay_delay * 2)
    manager_order_ids = list(
        base_qs.filter(
            payment_escalation_level__lt=2,
            delivered_at__lte=manager_threshold,
        ).values_list("id", flat=True)
    )
    manager_count = Order.objects.filter(id__in=manager_order_ids).update(
        payment_escalation_level=2
    )

    # Level 1 — senior_waiter (1 * PAY_TIMEOUT)
    senior_threshold = now - pay_delay
    senior_order_ids = list(
        base_qs.filter(
            payment_escalation_level=0,
            delivered_at__lte=senior_threshold,
        ).values_list("id", flat=True)
    )
    senior_count = Order.objects.filter(id__in=senior_order_ids).update(
        payment_escalation_level=1
    )

    for oid in manager_order_ids:
        push_payment_escalation(order_id=oid, level=2)
    for oid in senior_order_ids:
        push_payment_escalation(order_id=oid, level=1)

    return {"senior_waiter": senior_count, "manager": manager_count}


@shared_task(name="orders.escalate_visitor_issues")
def escalate_visitor_issues() -> dict[str, int]:
    """Auto-escalate unacknowledged visitor escalations.

    Logic:
        created_at + ESCALATION_AUTO_LEVEL → level 1→2 (senior_waiter)
        created_at + ESCALATION_AUTO_LEVEL*2 → level 2→3 (manager)

    Runs via Celery Beat every minute.
    """
    now = timezone.now()
    auto_delay = timedelta(minutes=settings.ESCALATION_AUTO_LEVEL)

    # Level → 3 (manager): older than 2x delay, still unresolved
    manager_threshold = now - (auto_delay * 2)
    to_manager = VisitorEscalation.objects.filter(
        status__in=["open", "acknowledged"],
        level__lt=VisitorEscalation.Level.MANAGER,
        created_at__lte=manager_threshold,
    )
    manager_ids = list(to_manager.values_list("id", flat=True))
    manager_count = VisitorEscalation.objects.filter(id__in=manager_ids).update(
        level=VisitorEscalation.Level.MANAGER,
    )

    # Level 1→2 (senior): OPEN only, older than 1x delay
    senior_threshold = now - auto_delay
    to_senior = VisitorEscalation.objects.filter(
        status=VisitorEscalation.Status.OPEN,
        level=VisitorEscalation.Level.WAITER,
        created_at__lte=senior_threshold,
    ).exclude(id__in=manager_ids)
    senior_ids = list(to_senior.values_list("id", flat=True))
    senior_count = VisitorEscalation.objects.filter(id__in=senior_ids).update(
        level=VisitorEscalation.Level.SENIOR,
    )

    # SSE pushes
    for esc_id in manager_ids:
        esc = VisitorEscalation.objects.select_related("order").get(id=esc_id)
        push_staff_escalation(
            waiter_id=esc.order.waiter_id,
            escalation_id=esc.pk,
            order_id=esc.order_id,
            reason=esc.reason,
            level=3,
        )
        push_visitor_event(
            order_id=esc.order_id,
            event_type="escalation_level_up",
            data={"level": 3},
        )

    for esc_id in senior_ids:
        esc = VisitorEscalation.objects.select_related("order").get(id=esc_id)
        push_staff_escalation(
            waiter_id=esc.order.waiter_id,
            escalation_id=esc.pk,
            order_id=esc.order_id,
            reason=esc.reason,
            level=2,
        )
        push_visitor_event(
            order_id=esc.order_id,
            event_type="escalation_level_up",
            data={"level": 2},
        )

    return {"to_senior": senior_count, "to_manager": manager_count}
