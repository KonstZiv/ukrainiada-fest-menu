# Task 2.4 — Celery task: ескалація кухні (детально)

## kitchen/tasks.py

```python
from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from kitchen.models import KitchenTicket


@shared_task(name="kitchen.escalate_pending_tickets")
def escalate_pending_tickets() -> dict[str, int]:
    """Ескалація тікетів що зависли без кухаря.

    Логіка:
        created_at + KITCHEN_TIMEOUT → escalation_level = SUPERVISOR (1)
        created_at + KITCHEN_TIMEOUT + MANAGER_TIMEOUT → escalation_level = MANAGER (2)

    Запускається Celery Beat кожну хвилину.
    Повертає dict з кількістю ескальованих на кожен рівень (для логування).
    """
    now = timezone.now()
    kitchen_timeout = timedelta(minutes=settings.KITCHEN_TIMEOUT)
    manager_timeout = timedelta(minutes=settings.KITCHEN_TIMEOUT + settings.MANAGER_TIMEOUT)

    # Ескалація до MANAGER (рівень 2) — ще не ескальовано або тільки до supervisor
    manager_threshold = now - manager_timeout
    to_manager = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        escalation_level__lt=KitchenTicket.EscalationLevel.MANAGER,
        created_at__lte=manager_threshold,
    )
    manager_count = to_manager.update(
        escalation_level=KitchenTicket.EscalationLevel.MANAGER
    )

    # Ескалація до SUPERVISOR (рівень 1) — ще не ескальовано взагалі
    supervisor_threshold = now - kitchen_timeout
    to_supervisor = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        escalation_level=KitchenTicket.EscalationLevel.NONE,
        created_at__lte=supervisor_threshold,
    )
    supervisor_count = to_supervisor.update(
        escalation_level=KitchenTicket.EscalationLevel.SUPERVISOR
    )

    return {"supervisor": supervisor_count, "manager": manager_count}
```

## Реєстрація у Celery Beat (через Django адмінку або initial data)

```python
# Варіант 1: через management command або data migration
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json

schedule, _ = IntervalSchedule.objects.get_or_create(
    every=1,
    period=IntervalSchedule.MINUTES,
)
PeriodicTask.objects.get_or_create(
    name="Escalate pending kitchen tickets",
    defaults={
        "task": "kitchen.escalate_pending_tickets",
        "interval": schedule,
        "args": json.dumps([]),
    },
)
```

Або через `settings/base.py`:
```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "escalate-kitchen-tickets": {
        "task": "kitchen.escalate_pending_tickets",
        "schedule": 60.0,  # кожну хвилину
    },
}
```

## Тести

```python
# kitchen/tests/test_tasks.py
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.utils import timezone
from datetime import timedelta


@pytest.mark.tier1
def test_escalate_task_is_registered():
    from kitchen.tasks import escalate_pending_tickets
    assert callable(escalate_pending_tickets)


@pytest.mark.tier2
@pytest.mark.django_db
def test_escalate_to_supervisor(django_user_model):
    from kitchen.tasks import escalate_pending_tickets
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)

    # Симулюємо що тікет старий (понад KITCHEN_TIMEOUT хвилин)
    old_time = timezone.now() - timedelta(minutes=10)
    KitchenTicket.objects.filter(pk=ticket.pk).update(created_at=old_time)

    with patch("django.conf.settings.KITCHEN_TIMEOUT", 5):
        with patch("django.conf.settings.MANAGER_TIMEOUT", 5):
            result = escalate_pending_tickets()

    ticket.refresh_from_db()
    assert ticket.escalation_level == KitchenTicket.EscalationLevel.SUPERVISOR
    assert result["supervisor"] >= 1


@pytest.mark.tier2
@pytest.mark.django_db
def test_escalate_to_manager(django_user_model):
    from kitchen.tasks import escalate_pending_tickets
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)

    # Симулюємо дуже старий тікет (KITCHEN + MANAGER timeout)
    old_time = timezone.now() - timedelta(minutes=15)
    KitchenTicket.objects.filter(pk=ticket.pk).update(created_at=old_time)

    with patch("django.conf.settings.KITCHEN_TIMEOUT", 5):
        with patch("django.conf.settings.MANAGER_TIMEOUT", 5):
            result = escalate_pending_tickets()

    ticket.refresh_from_db()
    assert ticket.escalation_level == KitchenTicket.EscalationLevel.MANAGER
    assert result["manager"] >= 1


@pytest.mark.tier2
@pytest.mark.django_db
def test_taken_tickets_not_escalated(django_user_model):
    from kitchen.tasks import escalate_pending_tickets
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=kitchen_user,
    )
    old_time = timezone.now() - timedelta(minutes=20)
    KitchenTicket.objects.filter(pk=ticket.pk).update(created_at=old_time)

    escalate_pending_tickets()

    ticket.refresh_from_db()
    assert ticket.escalation_level == KitchenTicket.EscalationLevel.NONE
```

## Acceptance criteria

- [ ] `escalate_pending_tickets` — `@shared_task`, один bulk update запит на рівень
- [ ] Celery Beat запускає задачу кожну хвилину
- [ ] `TAKEN` і `DONE` тікети не ескалуються
- [ ] Supervisor бачить тікети з `escalation_level >= 1`
- [ ] Manager бачить тікети з `escalation_level >= 2`
- [ ] Тести зелені (без реального Celery — через виклик функції напряму)
