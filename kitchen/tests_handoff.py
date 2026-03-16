"""Tests for KitchenHandoff model and QR generation (Task 5.1)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

from kitchen.models import KitchenHandoff, KitchenTicket
from kitchen.services import create_handoff
from menu.models import Category, Dish
from orders.models import Order, OrderItem


def _make_done_ticket(
    django_user_model: Any,
) -> tuple[KitchenTicket, Any, Any]:
    """Create a DONE ticket with kitchen user and waiter."""
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="TestDish",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", username="ktest", password="testpass123", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.DONE,
        assigned_to=kitchen_user,
        done_at=timezone.now(),
    )
    return ticket, kitchen_user, waiter


# --- Model tests ---


def test_handoff_token_is_uuid() -> None:
    handoff = KitchenHandoff()
    handoff.token = uuid.uuid4()
    assert isinstance(handoff.token, uuid.UUID)


def test_handoff_is_expired_true() -> None:
    handoff = KitchenHandoff()
    handoff.is_confirmed = False
    handoff.created_at = timezone.now() - timedelta(seconds=200)

    with patch("kitchen.models.settings") as mock_settings:
        mock_settings.HANDOFF_TOKEN_TTL = 120
        assert handoff.is_expired is True


def test_handoff_is_expired_false() -> None:
    handoff = KitchenHandoff()
    handoff.is_confirmed = False
    handoff.created_at = timezone.now() - timedelta(seconds=30)

    with patch("kitchen.models.settings") as mock_settings:
        mock_settings.HANDOFF_TOKEN_TTL = 120
        assert handoff.is_expired is False


def test_handoff_confirmed_not_expired() -> None:
    handoff = KitchenHandoff()
    handoff.is_confirmed = True
    handoff.created_at = timezone.now() - timedelta(seconds=200)
    assert handoff.is_expired is False


# --- Service tests ---


@pytest.mark.django_db
def test_create_handoff_success(django_user_model: Any) -> None:
    ticket, _, waiter = _make_done_ticket(django_user_model)

    handoff = create_handoff(ticket, target_waiter=waiter)

    assert handoff.token is not None
    assert isinstance(handoff.token, uuid.UUID)
    assert handoff.target_waiter == waiter
    assert handoff.is_confirmed is False
    assert handoff.ticket == ticket


@pytest.mark.django_db
def test_create_handoff_replaces_old_unconfirmed(django_user_model: Any) -> None:
    ticket, _, waiter = _make_done_ticket(django_user_model)

    old_handoff = create_handoff(ticket, target_waiter=waiter)
    old_token = old_handoff.token

    new_handoff = create_handoff(ticket, target_waiter=waiter)

    assert new_handoff.token != old_token
    assert not KitchenHandoff.objects.filter(token=old_token).exists()


@pytest.mark.django_db
def test_create_handoff_wrong_status(django_user_model: Any) -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", username="ktest", password="testpass123", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=kitchen_user,
    )

    with pytest.raises(ValueError, match="Cannot handoff ticket"):
        create_handoff(ticket, target_waiter=waiter)


# --- View tests ---


@pytest.mark.django_db
def test_handoff_qr_get_shows_waiter_form(
    client: Client, django_user_model: Any
) -> None:
    ticket, kitchen_user, waiter = _make_done_ticket(django_user_model)

    client.force_login(kitchen_user)
    response = client.get(f"/kitchen/ticket/{ticket.id}/handoff/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Оберіть офіціанта" in content
    assert waiter.email in content


@pytest.mark.django_db
def test_handoff_qr_post_returns_png(client: Client, django_user_model: Any) -> None:
    ticket, kitchen_user, waiter = _make_done_ticket(django_user_model)

    client.force_login(kitchen_user)
    response = client.post(
        f"/kitchen/ticket/{ticket.id}/handoff/",
        {"waiter_id": waiter.id},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert KitchenHandoff.objects.filter(ticket=ticket).exists()


@pytest.mark.django_db
def test_handoff_qr_requires_kitchen_role(
    client: Client, django_user_model: Any
) -> None:
    ticket, _, waiter = _make_done_ticket(django_user_model)

    client.force_login(waiter)
    response = client.get(f"/kitchen/ticket/{ticket.id}/handoff/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_handoff_qr_404_for_other_cook(client: Client, django_user_model: Any) -> None:
    ticket, _, _ = _make_done_ticket(django_user_model)

    other_cook = django_user_model.objects.create_user(
        email="other@test.com", username="other", password="testpass123", role="kitchen"
    )
    client.force_login(other_cook)
    response = client.get(f"/kitchen/ticket/{ticket.id}/handoff/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_handoff_str(django_user_model: Any) -> None:
    ticket, _, waiter = _make_done_ticket(django_user_model)
    handoff = create_handoff(ticket, target_waiter=waiter)
    assert "Handoff" in str(handoff)
    assert str(handoff.token) in str(handoff)
