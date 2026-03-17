from __future__ import annotations

import uuid
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

    class PaymentMethod(models.TextChoices):
        NOT_SET = "not_set", "Не визначено"
        CASH = "cash", "Готівка"
        ONLINE = "online", "Онлайн"

    access_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
    )
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
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.NOT_SET,
    )
    payment_escalation_level = models.IntegerField(
        default=0,
        db_index=True,
    )
    location_hint = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Де вас знайти (необов'язково)",
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
        """Calculate total price using DB aggregation.

        NOTE: For list views, prefer annotate(total_annotated=...) on QuerySet
        to avoid N+1 queries. This property is for single-object access.
        """
        result = self.items.aggregate(
            total=models.Sum(
                models.F("dish__price") * models.F("quantity"),
                output_field=models.DecimalField(),
            )
        )["total"]
        return result or Decimal("0")


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


class OrderEvent(models.Model):
    """Unified event log for order lifecycle.

    Each row = one real event that happened (submitted, approved, kitchen
    accepted, ready, delivered, paid, etc.).  Rendered as a terminal-style
    log with typewriter animation on the visitor's order page.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="events",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    message = models.CharField(max_length=300)
    actor_label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable actor name, e.g. 'офіціант Ірина'",
    )

    class Meta:
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.message}"

    @property
    def log_line(self) -> str:
        """Format as terminal log line."""
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} — {self.message}"


class VisitorEscalation(models.Model):
    """Visitor-initiated escalation for an order issue.

    Lifecycle: OPEN → ACKNOWLEDGED → RESOLVED.
    Auto-escalation: level 1→2→3 via Celery task.
    """

    class Reason(models.TextChoices):
        SLOW = "slow", "Довго чекаю"
        WRONG = "wrong", "Щось не те"
        QUESTION = "question", "Маю питання"
        OTHER = "other", "Інше"

    class Level(models.IntegerChoices):
        WAITER = 1, "Офіціант"
        SENIOR = 2, "Старший офіціант"
        MANAGER = 3, "Менеджер"

    class Status(models.TextChoices):
        OPEN = "open", "Відкрита"
        ACKNOWLEDGED = "acknowledged", "Побачено"
        RESOLVED = "resolved", "Вирішено"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="escalations",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    message = models.TextField(blank=True, max_length=300, verbose_name="Коментар")
    level = models.IntegerField(
        choices=Level.choices,
        default=Level.WAITER,
        db_index=True,
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_escalations",
    )
    resolution_note = models.TextField(blank=True, max_length=300)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"Escalation #{self.pk} Order#{self.order_id} [{self.get_status_display()}]"
        )
