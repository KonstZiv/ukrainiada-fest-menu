"""Celery tasks for order payment escalation."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

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
    manager_count = base_qs.filter(
        payment_escalation_level__lt=2,
        delivered_at__lte=manager_threshold,
    ).update(payment_escalation_level=2)

    # Level 1 — senior_waiter (1 * PAY_TIMEOUT)
    senior_threshold = now - pay_delay
    senior_count = base_qs.filter(
        payment_escalation_level=0,
        delivered_at__lte=senior_threshold,
    ).update(payment_escalation_level=1)

    return {"senior_waiter": senior_count, "manager": manager_count}
