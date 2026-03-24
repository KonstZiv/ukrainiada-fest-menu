from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from menu.models import Dish


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Чернетка")
        SUBMITTED = "submitted", _("Створено")
        ACCEPTED = "accepted", _("Прийнято")
        VERIFIED = "verified", _("Верифіковано")
        IN_PROGRESS = "in_progress", _("Готується")
        READY = "ready", _("Готово")
        DELIVERED = "delivered", _("Доставлено")
        CANCELLED = "cancelled", _("Скасовано")

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", _("Не оплачено")
        PAID = "paid", _("Оплачено")

    class PaymentMethod(models.TextChoices):
        NOT_SET = "not_set", _("Не визначено")
        CASH = "cash", _("Готівка")
        ONLINE = "online", _("Онлайн")

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
        verbose_name=_("Де вас знайти (необов'язково)"),
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

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
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_events",
    )
    actor_label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Human-readable actor name, e.g. 'офіціант Ірина'",
    )
    is_auto_skip = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when this event was generated by auto-skipping a flow step",
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
        SLOW = "slow", _("Довго чекаю")
        WRONG = "wrong", _("Щось не те")
        QUESTION = "question", _("Маю питання")
        OTHER = "other", _("Інше")

    class Level(models.IntegerChoices):
        WAITER = 1, _("Офіціант")
        SENIOR = 2, _("Старший офіціант")
        MANAGER = 3, _("Менеджер")

    class Status(models.TextChoices):
        OPEN = "open", _("Відкрита")
        ACKNOWLEDGED = "acknowledged", _("Побачено")
        RESOLVED = "resolved", _("Вирішено")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="escalations",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    message = models.TextField(blank=True, max_length=300, verbose_name=_("Коментар"))
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


class StepEscalation(models.Model):
    """Blame-tracking escalation for each lifecycle step.

    Each step has an "owner" — the person responsible for completing it
    on time.  A missed deadline creates a level-1 (senior) record; if
    the senior doesn't resolve it within SENIOR_RESPONSE_TIMEOUT, a
    level-2 (manager) record is created with ``caused_by`` pointing to
    the senior.
    """

    class Step(models.TextChoices):
        SUBMIT_ACCEPT = "submit_accept", _("Прийняття замовлення")
        ACCEPT_VERIFY = "accept_verify", _("Верифікація")
        PENDING_TAKEN = "pending_taken", _("Взяття тікета кухарем")
        TAKEN_DONE = "taken_done", _("Приготування")
        DONE_HANDOFF = "done_handoff", _("Передача офіціанту")
        DELIVER_PAY = "deliver_pay", _("Оплата")

    class Level(models.IntegerChoices):
        SENIOR = 1, _("Старший")
        MANAGER = 2, _("Менеджер")

    step = models.CharField(max_length=20, choices=Step.choices, db_index=True)
    level = models.IntegerField(choices=Level.choices)

    # Blame target — specific person or pool role
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="step_escalations_owned",
    )
    owner_role = models.CharField(
        max_length=30,
        blank=True,
        help_text="Pool blame role, e.g. 'senior_waiter', 'kitchen_supervisor'",
    )

    # What was escalated
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="step_escalations",
    )
    ticket = models.ForeignKey(
        "kitchen.KitchenTicket",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="step_escalations",
    )

    # For level=2: who failed to resolve the senior escalation
    caused_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="step_escalations_caused",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["step", "level", "resolved_at"]),
        ]

    def __str__(self) -> str:
        target = (
            f"Order#{self.order_id}" if self.order_id else f"Ticket#{self.ticket_id}"
        )
        return f"StepEsc {self.step}:{self.level} {target}"
