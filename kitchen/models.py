from __future__ import annotations

from django.conf import settings
from django.db import models


class KitchenAssignment(models.Model):
    """Which dish can be prepared by which kitchen staff member.

    M2M relationship between Dish and kitchen users.
    Configured by admin before the festival.
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
        name = self.kitchen_user.get_full_name() or self.kitchen_user.email
        return f"{self.dish.title} \u2192 {name}"


class KitchenTicket(models.Model):
    """Single order item in the kitchen queue.

    Lifecycle:
        PENDING  — created on approve, unassigned
        TAKEN    — kitchen staff picked it up
        DONE     — marked as ready, waiting for waiter
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
        limit_choices_to={"role__in": ["kitchen", "kitchen_supervisor"]},
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
