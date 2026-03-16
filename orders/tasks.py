"""Celery tasks for order payment escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from notifications.events import push_payment_escalation
from orders.models import Order


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
