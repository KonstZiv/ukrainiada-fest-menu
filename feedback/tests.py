"""Tests for GuestFeedback model, services, views, and board (Sprint 11)."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from feedback.models import GuestFeedback
from feedback.services import (
    create_feedback,
    feature_feedback,
    get_public_feedback,
    publish_feedback,
)
from orders.models import Order


# --- Service tests ---


@pytest.mark.django_db
def test_create_feedback_success() -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    fb = create_feedback(order, mood="love", message="Чудовий борщ!")
    assert fb.mood == "love"
    assert fb.message == "Чудовий борщ!"
    assert fb.is_published is False


@pytest.mark.django_db
def test_cannot_feedback_non_delivered() -> None:
    order = Order.objects.create(status=Order.Status.VERIFIED)
    with pytest.raises(ValueError, match="після отримання"):
        create_feedback(order, mood="good")


@pytest.mark.django_db
def test_cannot_duplicate_feedback() -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    create_feedback(order, mood="love")
    with pytest.raises(ValueError, match="вже залишили"):
        create_feedback(order, mood="good")


@pytest.mark.django_db
def test_invalid_mood_rejected() -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    with pytest.raises(ValueError, match="Невідомий"):
        create_feedback(order, mood="invalid")


@pytest.mark.django_db
def test_publish_feedback() -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    fb = create_feedback(order, mood="good")
    publish_feedback(fb)
    fb.refresh_from_db()
    assert fb.is_published is True


@pytest.mark.django_db
def test_feature_feedback_auto_publishes() -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    fb = create_feedback(order, mood="love")
    feature_feedback(fb)
    fb.refresh_from_db()
    assert fb.is_featured is True
    assert fb.is_published is True


@pytest.mark.django_db
def test_get_public_feedback_featured_first() -> None:
    o1 = Order.objects.create(status=Order.Status.DELIVERED)
    o2 = Order.objects.create(status=Order.Status.DELIVERED)
    fb1 = create_feedback(o1, mood="good")
    fb2 = create_feedback(o2, mood="love")
    publish_feedback(fb1)
    feature_feedback(fb2)

    public = list(get_public_feedback())
    assert public[0].pk == fb2.pk  # featured first


# --- View tests ---


@pytest.mark.django_db
def test_board_accessible(client: Client) -> None:
    response = client.get("/feedback/board/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_board_shows_published_only(client: Client) -> None:
    o1 = Order.objects.create(status=Order.Status.DELIVERED)
    o2 = Order.objects.create(status=Order.Status.DELIVERED)
    fb1 = create_feedback(o1, mood="love", visitor_name="Олена")
    create_feedback(o2, mood="bad", visitor_name="Секрет")
    publish_feedback(fb1)

    response = client.get("/feedback/board/")
    content = response.content.decode()
    assert "Олена" in content
    assert "Секрет" not in content


@pytest.mark.django_db
def test_submit_creates_feedback(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DELIVERED)
    response = client.post(
        f"/feedback/{order.id}/submit/?token={order.access_token}",
        {"mood": "love", "message": "Super!"},
    )
    assert response.status_code == 302
    assert GuestFeedback.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_moderate_requires_manager(client: Client, django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    client.force_login(waiter)
    response = client.get("/feedback/moderate/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_moderate_accessible_by_manager(client: Client, django_user_model: Any) -> None:
    manager = django_user_model.objects.create_user(
        email="m@test.com", username="m", password="testpass123", role="manager"
    )
    client.force_login(manager)
    response = client.get("/feedback/moderate/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_moderate_publish_action(client: Client, django_user_model: Any) -> None:
    manager = django_user_model.objects.create_user(
        email="m@test.com", username="m", password="testpass123", role="manager"
    )
    order = Order.objects.create(status=Order.Status.DELIVERED)
    fb = create_feedback(order, mood="love")

    client.force_login(manager)
    response = client.post(
        f"/feedback/moderate/{fb.pk}/",
        {"action": "publish"},
    )
    assert response.status_code == 302
    fb.refresh_from_db()
    assert fb.is_published is True
