"""Guest feedback model for post-delivery reviews."""

from __future__ import annotations

from django.db import models


class GuestFeedback(models.Model):
    """Visitor feedback after receiving their order.

    Lifecycle: created (unpublished) → published by moderator → optionally featured.
    OneToOne with Order — one feedback per order.
    """

    class Mood(models.TextChoices):
        LOVE = "love", "❤️ Чудово"
        GOOD = "good", "😊 Добре"
        OK = "ok", "😐 Нормально"
        BAD = "bad", "😕 Не дуже"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name="Замовлення",
    )
    visitor_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Ім'я відвідувача",
    )
    mood = models.CharField(
        max_length=10,
        choices=Mood.choices,
        verbose_name="Настрій",
    )
    message = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Повідомлення",
    )

    is_published = models.BooleanField(default=False, db_index=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=5, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Відгук"
        verbose_name_plural = "Відгуки"

    def __str__(self) -> str:
        name = self.visitor_name or "Анонім"
        return f"{name}: {self.get_mood_display()} — Order #{self.order_id}"
