"""Guest feedback model for post-delivery reviews."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class GuestFeedback(models.Model):
    """Visitor feedback after receiving their order.

    Lifecycle: created (unpublished) → published by moderator → optionally featured.
    OneToOne with Order — one feedback per order.
    """

    class Mood(models.TextChoices):
        LOVE = "love", _("❤️ Чудово")
        GOOD = "good", _("😊 Добре")
        OK = "ok", _("😐 Нормально")
        BAD = "bad", _("😕 Не дуже")

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Замовлення"),
    )
    visitor_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Ім'я відвідувача"),
    )
    mood = models.CharField(
        max_length=10,
        choices=Mood.choices,
        verbose_name=_("Настрій"),
    )
    message = models.TextField(
        max_length=500,
        blank=True,
        verbose_name=_("Повідомлення"),
    )

    is_published = models.BooleanField(default=False, db_index=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=5, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Відгук")
        verbose_name_plural = _("Відгуки")

    def __str__(self) -> str:
        name = self.visitor_name or "Анонім"
        return f"{name}: {self.get_mood_display()} — Order #{self.order_id}"
