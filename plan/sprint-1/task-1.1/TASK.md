# Task 1.1 — Модель Order і OrderItem (детально)

## orders/models.py

```python
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from menu.models import Dish


class Order(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Чернетка"
        SUBMITTED = "submitted", "Передано офіціанту"
        APPROVED = "approved", "Підтверджено"
        IN_PROGRESS = "in_progress", "Готується"
        READY = "ready", "Готово — очікує офіціанта"
        DELIVERED = "delivered", "Видано відвідувачу"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачено"
        PAID = "paid", "Оплачено"

    visitor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visitor_orders",
        null=True,
        blank=True,
        help_text="None якщо офіціант створив замовлення без акаунту відвідувача",
    )
    waiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="waiter_orders",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    notes = models.TextField(blank=True, help_text="Нотатки офіціанта")

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} [{self.get_status_display()}]"

    @property
    def total_price(self) -> Decimal:
        return sum(
            (item.dish.price * item.quantity for item in self.items.select_related("dish")),
            Decimal("0"),
        )


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.PROTECT,  # PROTECT: не можна видалити страву з активним замовленням
        related_name="order_items",
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [("order", "dish")]

    def __str__(self) -> str:
        return f"{self.dish.title} x{self.quantity}"

    @property
    def subtotal(self) -> Decimal:
        return self.dish.price * self.quantity
```

## orders/admin.py

```python
from django.contrib import admin
from orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["subtotal"]

    def subtotal(self, obj: OrderItem) -> str:
        return f"€{obj.subtotal:.2f}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "payment_status", "waiter", "created_at", "total_price_display"]
    list_filter = ["status", "payment_status"]
    readonly_fields = ["created_at", "updated_at", "submitted_at", "approved_at",
                       "ready_at", "delivered_at", "payment_confirmed_at"]
    inlines = [OrderItemInline]

    def total_price_display(self, obj: Order) -> str:
        return f"€{obj.total_price:.2f}"
    total_price_display.short_description = "Сума"
```

## Тести

```python
# orders/tests/test_models.py
import pytest
from decimal import Decimal


@pytest.mark.tier1
def test_order_status_flow_values():
    from orders.models import Order
    statuses = {s.value for s in Order.Status}
    expected = {"draft", "submitted", "approved", "in_progress", "ready", "delivered"}
    assert statuses == expected


@pytest.mark.tier1
def test_order_default_status_and_payment():
    from orders.models import Order
    order = Order()
    assert order.status == Order.Status.DRAFT
    assert order.payment_status == Order.PaymentStatus.UNPAID


@pytest.mark.tier2
@pytest.mark.django_db
def test_order_total_price():
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    dish2 = Dish.objects.create(
        title="D2", description="", price=Decimal("3.50"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish1, quantity=2)  # 10.00
    OrderItem.objects.create(order=order, dish=dish2, quantity=1)  # 3.50
    assert order.total_price == Decimal("13.50")


@pytest.mark.tier2
@pytest.mark.django_db
def test_order_item_unique_per_dish():
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish
    from django.db import IntegrityError

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(IntegrityError):
        OrderItem.objects.create(order=order, dish=dish, quantity=2)


@pytest.mark.tier2
@pytest.mark.django_db
def test_cannot_delete_dish_with_active_order():
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish
    from django.db.models import ProtectedError

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(ProtectedError):
        dish.delete()
```

## Міграція

```bash
uv run python manage.py makemigrations orders --name="initial_order_models"
uv run python manage.py migrate
```

## Acceptance criteria

- [ ] `Order`, `OrderItem` — в БД, міграції застосовані
- [ ] `order.total_price` — правильний підрахунок через property
- [ ] `on_delete=PROTECT` на `OrderItem.dish` — страву не можна видалити при активних замовленнях
- [ ] Адмінка: `Order` з `OrderItemInline`, `total_price_display`
- [ ] `uv run pytest -m "tier1 or tier2" orders/tests/test_models.py` — зелені
