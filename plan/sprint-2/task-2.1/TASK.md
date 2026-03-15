# Task 2.1 — Kitchen dashboard (детально)

## Модель — додати до KitchenTicket

```python
# kitchen/models.py — розширити KitchenTicket

class EscalationLevel(models.IntegerChoices):
    NONE = 0, "Немає"
    SUPERVISOR = 1, "Старший кухні"
    MANAGER = 2, "Менеджер"

escalation_level = models.IntegerField(
    choices=EscalationLevel.choices,
    default=EscalationLevel.NONE,
    db_index=True,
)
```

## kitchen/views.py

```python
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from kitchen.models import KitchenTicket
from kitchen.services import get_pending_tickets_for_user
from user.decorators import role_required

KITCHEN_ROLES = ("kitchen", "kitchen_supervisor", "manager")


@role_required(*KITCHEN_ROLES)
def kitchen_dashboard(request: HttpRequest) -> HttpResponse:
    user = request.user

    # Pending — тільки страви цього кухаря (або всі якщо supervisor/manager)
    if user.role == "kitchen":
        pending = get_pending_tickets_for_user(user.id)
    else:
        # supervisor і manager бачать всі pending
        pending = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING
        ).select_related("order_item__dish", "order_item__order__waiter")

    # Ескальовані — окремий блок для supervisor і manager
    escalated = []
    if user.role in ("kitchen_supervisor", "manager"):
        level = (
            KitchenTicket.EscalationLevel.SUPERVISOR
            if user.role == "kitchen_supervisor"
            else KitchenTicket.EscalationLevel.MANAGER
        )
        escalated = KitchenTicket.objects.filter(
            status=KitchenTicket.Status.PENDING,
            escalation_level__gte=level,
        ).select_related("order_item__dish", "order_item__order__waiter")

    # Мій пул — taken мною
    my_taken = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.TAKEN,
        assigned_to=user,
    ).select_related("order_item__dish", "order_item__order__waiter")

    # Передані — done мною (за сьогодні)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    my_done = KitchenTicket.objects.filter(
        status=KitchenTicket.Status.DONE,
        assigned_to=user,
        done_at__gte=today_start,
    ).select_related("order_item__dish", "order_item__order__waiter").order_by("-done_at")

    return render(request, "kitchen/dashboard.html", {
        "pending": pending,
        "escalated": escalated,
        "my_taken": my_taken,
        "my_done": my_done,
    })
```

## Тести

```python
# kitchen/tests/test_dashboard.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_kitchen_dashboard_requires_auth(client):
    response = client.get("/kitchen/")
    assert response.status_code == 302  # redirect to login


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_cannot_access_kitchen(client, django_user_model):
    visitor = django_user_model.objects.create_user(
        email="v@test.com", password="pass", role="visitor"
    )
    client.force_login(visitor)
    response = client.get("/kitchen/")
    assert response.status_code == 403


@pytest.mark.tier2
@pytest.mark.django_db
def test_kitchen_user_sees_dashboard(client, django_user_model):
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/kitchen/")
    assert response.status_code == 200
```

## Acceptance criteria

- [ ] `escalation_level` поле на `KitchenTicket`, міграція
- [ ] Kitchen бачить: pending (свої), taken (свої), done (сьогодні)
- [ ] Supervisor/Manager бачать всі pending + ескальовані окремо
- [ ] Тести зелені
