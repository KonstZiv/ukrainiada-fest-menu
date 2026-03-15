# Task 3.3 — Celery task: ескалація несплачених замовлень (детально)

## orders/tasks.py

```python
from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from orders.models import Order


@shared_task(name="orders.escalate_unpaid_orders")
def escalate_unpaid_orders() -> dict[str, int]:
    """Ескалація доставлених але несплачених замовлень.

    Логіка:
        delivered_at + PAY_TIMEOUT → payment_escalation_level = 1 (senior_waiter)
        delivered_at + PAY_TIMEOUT * 2 → payment_escalation_level = 2 (manager)

    Запускається Celery Beat кожну хвилину.
    """
    now = timezone.now()
    pay_timeout = timedelta(minutes=settings.PAY_TIMEOUT)

    # Умова: доставлено і не оплачено
    base_qs = Order.objects.filter(
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    # Рівень 2 — manager (2 * PAY_TIMEOUT)
    manager_threshold = now - (pay_timeout * 2)
    manager_count = base_qs.filter(
        payment_escalation_level__lt=2,
        delivered_at__lte=manager_threshold,
    ).update(payment_escalation_level=2)

    # Рівень 1 — senior_waiter (1 * PAY_TIMEOUT)
    senior_threshold = now - pay_timeout
    senior_count = base_qs.filter(
        payment_escalation_level=0,
        delivered_at__lte=senior_threshold,
    ).update(payment_escalation_level=1)

    return {"senior_waiter": senior_count, "manager": manager_count}
```

## Реєстрація у Celery Beat (settings/base.py)

```python
CELERY_BEAT_SCHEDULE = {
    "escalate-kitchen-tickets": {
        "task": "kitchen.escalate_pending_tickets",
        "schedule": 60.0,
    },
    "escalate-unpaid-orders": {
        "task": "orders.escalate_unpaid_orders",
        "schedule": 60.0,
    },
}
```

## Тести

```python
# orders/tests/test_payment_escalation.py
import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch


@pytest.mark.tier1
def test_escalate_task_registered():
    from orders.tasks import escalate_unpaid_orders
    assert callable(escalate_unpaid_orders)


@pytest.mark.tier2
@pytest.mark.django_db
def test_escalate_to_senior_waiter(django_user_model):
    from orders.tasks import escalate_unpaid_orders
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    # Симулюємо що доставлено PAY_TIMEOUT + 1 хв тому
    old_time = timezone.now() - timedelta(minutes=11)
    Order.objects.filter(pk=order.pk).update(delivered_at=old_time)

    with patch("django.conf.settings.PAY_TIMEOUT", 10):
        result = escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 1
    assert result["senior_waiter"] >= 1


@pytest.mark.tier2
@pytest.mark.django_db
def test_paid_orders_not_escalated(django_user_model):
    from orders.tasks import escalate_unpaid_orders
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.PAID,  # вже оплачено
    )
    old_time = timezone.now() - timedelta(minutes=30)
    Order.objects.filter(pk=order.pk).update(delivered_at=old_time)

    escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 0  # не ескальовано


@pytest.mark.tier2
@pytest.mark.django_db
def test_not_delivered_orders_not_escalated(django_user_model):
    from orders.tasks import escalate_unpaid_orders
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.READY,  # ще не доставлено
        payment_status=Order.PaymentStatus.UNPAID,
    )
    escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 0
```

## Acceptance criteria

- [ ] `escalate_unpaid_orders` — два bulk update запити (не N+1)
- [ ] Тільки `DELIVERED + UNPAID` замовлення ескалуються
- [ ] `PAID` і не-`DELIVERED` замовлення не чіпаємо
- [ ] Celery Beat запускає кожну хвилину (поруч з kitchen task)
- [ ] Тести зелені
