"""Feedback business logic — create, moderate, query."""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils.translation import get_language

from feedback.models import GuestFeedback
from orders.models import Order


def create_feedback(
    order: Order,
    mood: str,
    message: str = "",
    visitor_name: str = "",
) -> GuestFeedback:
    """Create feedback for a delivered order.

    Raises:
        ValueError: if order is not delivered, feedback exists, or mood is invalid.

    """
    if order.status != Order.Status.DELIVERED:
        msg = "Відгук можна залишити тільки після отримання замовлення"
        raise ValueError(msg)

    if GuestFeedback.objects.filter(order=order).exists():
        msg = "Ви вже залишили відгук для цього замовлення"
        raise ValueError(msg)

    if mood not in GuestFeedback.Mood.values:
        msg = f"Невідомий настрій: {mood}"
        raise ValueError(msg)

    return GuestFeedback.objects.create(
        order=order,
        mood=mood,
        message=message[:500],
        visitor_name=visitor_name[:50],
        language=get_language() or "uk",
    )


def publish_feedback(feedback: GuestFeedback) -> None:
    """Moderator publishes feedback to public board."""
    feedback.is_published = True
    feedback.save(update_fields=["is_published"])


def feature_feedback(feedback: GuestFeedback) -> None:
    """Moderator marks feedback as featured (auto-publishes)."""
    feedback.is_featured = True
    feedback.is_published = True
    feedback.save(update_fields=["is_featured", "is_published"])


def get_public_feedback(limit: int = 50) -> QuerySet[GuestFeedback]:
    """Return published feedback for public board, featured first."""
    return GuestFeedback.objects.filter(is_published=True).order_by(
        "-is_featured", "-created_at"
    )[:limit]
