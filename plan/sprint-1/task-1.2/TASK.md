# Task 1.2 — KitchenAssignment і KitchenTicket (детально)

## Концепція

`KitchenAssignment` — адмін задає які страви готує який кухар.
Один кухар може готувати кілька страв, одну страву можуть готувати кілька кухарів.

`KitchenTicket` — одна позиція замовлення у черзі кухні.
Створюється при approve замовлення офіціантом (Task 1.5).
Тікет «висить» нічийним поки хтось з кухні не бере його в роботу (Sprint 2).

## kitchen/models.py

```python
from __future__ import annotations

from django.conf import settings
from django.db import models


class KitchenAssignment(models.Model):
    """Яка страва може готуватися яким кухарем.

    Один кухар — багато страв (M2M через цю модель).
    Одна страва — потенційно кілька кухарів.
    Адміністратор налаштовує перед фестивалем.
    """

    dish = models.ForeignKey(
        "menu.Dish",
        on_delete=models.CASCADE,
        related_name="kitchen_assignments",
        verbose_name="Страва",
    )
    kitchen_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kitchen_assignments",
        limit_choices_to={"role__in": ["kitchen", "kitchen_supervisor"]},
        verbose_name="Кухар",
    )

    class Meta:
        unique_together = [("dish", "kitchen_user")]
        verbose_name = "Розподіл кухні"
        verbose_name_plural = "Розподіл кухні"

    def __str__(self) -> str:
        return f"{self.dish.title} → {self.kitchen_user.get_full_name() or self.kitchen_user.email}"


class KitchenTicket(models.Model):
    """Одна позиція замовлення у черзі кухні.

    Lifecycle:
        PENDING  — створено при approve, ніхто не взяв
        TAKEN    — кухар взяв в роботу (assigned_to заповнено)
        DONE     — кухар позначив як готово, очікує офіціанта
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Очікує"
        TAKEN = "taken", "Готується"
        DONE = "done", "Готово"

    order_item = models.OneToOneField(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="kitchen_ticket",
        verbose_name="Позиція замовлення",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kitchen_tickets",
        verbose_name="Кухар",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Тікет кухні"
        verbose_name_plural = "Тікети кухні"

    def __str__(self) -> str:
        return f"Ticket #{self.pk}: {self.order_item} [{self.status}]"
```

## kitchen/services.py

```python
from orders.models import Order
from kitchen.models import KitchenTicket


def create_tickets_for_order(order: Order) -> list[KitchenTicket]:
    """Створити KitchenTicket для кожного OrderItem.

    Викликається з orders/services.py::approve_order().
    Не перевіряє статус order — відповідальність на стороні виклику.
    """
    tickets = [
        KitchenTicket(order_item=item)
        for item in order.items.select_related("dish").all()
    ]
    return KitchenTicket.objects.bulk_create(tickets)


def get_pending_tickets_for_user(kitchen_user_id: int) -> "QuerySet[KitchenTicket]":
    """Тікети які може взяти в роботу конкретний кухар.

    Повертає PENDING тікети для страв де є KitchenAssignment для цього кухаря.
    Якщо страва не має жодного KitchenAssignment — вона видима ВСІМ кухарям.
    """
    from kitchen.models import KitchenAssignment
    from django.db.models import QuerySet

    assigned_dish_ids = KitchenAssignment.objects.filter(
        kitchen_user_id=kitchen_user_id
    ).values_list("dish_id", flat=True)

    return KitchenTicket.objects.filter(
        status=KitchenTicket.Status.PENDING,
        order_item__dish_id__in=assigned_dish_ids,
    ).select_related("order_item__dish", "order_item__order")
```

## kitchen/admin.py

```python
from django.contrib import admin
from kitchen.models import KitchenAssignment, KitchenTicket


@admin.register(KitchenAssignment)
class KitchenAssignmentAdmin(admin.ModelAdmin):
    list_display = ["dish", "kitchen_user"]
    list_filter = ["kitchen_user"]
    search_fields = ["dish__title", "kitchen_user__email"]


@admin.register(KitchenTicket)
class KitchenTicketAdmin(admin.ModelAdmin):
    list_display = ["id", "order_item", "assigned_to", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["created_at", "taken_at", "done_at"]
```

## Тести

```python
# kitchen/tests/test_services.py
import pytest
from decimal import Decimal


@pytest.mark.tier1
def test_kitchen_ticket_status_choices():
    from kitchen.models import KitchenTicket
    statuses = {s.value for s in KitchenTicket.Status}
    assert statuses == {"pending", "taken", "done"}


@pytest.mark.tier1
def test_kitchen_ticket_default_status():
    from kitchen.models import KitchenTicket
    ticket = KitchenTicket()
    assert ticket.status == KitchenTicket.Status.PENDING


@pytest.mark.tier2
@pytest.mark.django_db
def test_create_tickets_for_order(django_user_model):
    from orders.models import Order, OrderItem
    from kitchen.models import KitchenTicket
    from kitchen.services import create_tickets_for_order
    from menu.models import Category, Dish

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    dish2 = Dish.objects.create(
        title="D2", description="", price=Decimal("3.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish1, quantity=1)
    OrderItem.objects.create(order=order, dish=dish2, quantity=2)

    tickets = create_tickets_for_order(order)

    assert len(tickets) == 2
    assert all(t.status == KitchenTicket.Status.PENDING for t in tickets)
    assert KitchenTicket.objects.filter(order_item__order=order).count() == 2


@pytest.mark.tier2
@pytest.mark.django_db
def test_get_pending_tickets_filtered_by_assignment(django_user_model):
    from orders.models import Order, OrderItem
    from kitchen.models import KitchenTicket, KitchenAssignment
    from kitchen.services import create_tickets_for_order, get_pending_tickets_for_user
    from menu.models import Category, Dish

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish_mine = Dish.objects.create(
        title="Mine", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    dish_other = Dish.objects.create(
        title="Other", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    KitchenAssignment.objects.create(dish=dish_mine, kitchen_user=kitchen_user)

    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish_mine, quantity=1)
    OrderItem.objects.create(order=order, dish=dish_other, quantity=1)
    create_tickets_for_order(order)

    tickets = get_pending_tickets_for_user(kitchen_user.id)
    dish_titles = {t.order_item.dish.title for t in tickets}
    assert "Mine" in dish_titles
    assert "Other" not in dish_titles
```

## Acceptance criteria

- [ ] `KitchenAssignment`, `KitchenTicket` — в БД, міграції застосовані
- [ ] `create_tickets_for_order` — bulk_create, повертає список тікетів
- [ ] `get_pending_tickets_for_user` — фільтрує по KitchenAssignment
- [ ] Адмінка: обидві моделі зареєстровані
- [ ] `uv run pytest -m "tier1 or tier2" kitchen/tests/` — зелені
