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
    notes = models.TextField(blank=True)

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
        """Calculate total price from all order items."""
        return sum(
            (
                item.dish.price * item.quantity
                for item in self.items.select_related("dish")
            ),
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
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [("order", "dish")]

    def __str__(self) -> str:
        return f"{self.dish.title} x{self.quantity}"

    @property
    def subtotal(self) -> Decimal:
        """Calculate subtotal for this item."""
        return self.dish.price * self.quantity
