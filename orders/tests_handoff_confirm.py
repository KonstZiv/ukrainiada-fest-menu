"""Tests for waiter handoff confirmation flow (Task 5.2)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from kitchen.models import KitchenHandoff, KitchenTicket
from menu.models import Category, Dish
from orders.models import Order, OrderItem


def _make_handoff(
    django_user_model: Any,
) -> tuple[KitchenHandoff, Any, Any]:
    """Create a handoff with kitchen user and target waiter."""
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="Борщ",
        description="",
        price=Decimal("8.00"),
        weight=400,
        calorie=320,
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
    handoff = KitchenHandoff.objects.create(ticket=ticket, target_waiter=waiter)
    return handoff, kitchen_user, waiter


@pytest.mark.django_db
def test_handoff_confirm_get(client: Client, django_user_model: Any) -> None:
    handoff, _, waiter = _make_handoff(django_user_model)

    client.force_login(waiter)
    response = client.get(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Борщ" in content
    assert "Підтверджую прийом" in content


@pytest.mark.django_db
def test_handoff_confirm_post(client: Client, django_user_model: Any) -> None:
    handoff, _, waiter = _make_handoff(django_user_model)

    client.force_login(waiter)
    response = client.post(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 302
    handoff.refresh_from_db()
    assert handoff.is_confirmed is True
    assert handoff.confirmed_at is not None


@pytest.mark.django_db
def test_wrong_waiter_gets_403(client: Client, django_user_model: Any) -> None:
    handoff, _, _ = _make_handoff(django_user_model)

    other_waiter = django_user_model.objects.create_user(
        email="w2@test.com", username="w2", password="testpass123", role="waiter"
    )
    client.force_login(other_waiter)
    response = client.get(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_expired_handoff_returns_400(client: Client, django_user_model: Any) -> None:
    handoff, _, waiter = _make_handoff(django_user_model)

    old_time = timezone.now() - timedelta(seconds=300)
    KitchenHandoff.objects.filter(pk=handoff.pk).update(created_at=old_time)

    client.force_login(waiter)
    response = client.get(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 400
    assert "прострочений" in response.content.decode()


@pytest.mark.django_db
def test_already_confirmed_shows_info(client: Client, django_user_model: Any) -> None:
    handoff, _, waiter = _make_handoff(django_user_model)
    handoff.is_confirmed = True
    handoff.confirmed_at = timezone.now()
    handoff.save(update_fields=["is_confirmed", "confirmed_at"])

    client.force_login(waiter)
    response = client.get(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 200
    assert "Вже підтверджено" in response.content.decode()


@pytest.mark.django_db
def test_kitchen_role_cannot_confirm(client: Client, django_user_model: Any) -> None:
    handoff, kitchen_user, _ = _make_handoff(django_user_model)

    client.force_login(kitchen_user)
    response = client.get(f"/waiter/handoff/{handoff.token}/confirm/")

    assert response.status_code == 403
