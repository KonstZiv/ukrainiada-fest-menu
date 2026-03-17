"""Tests for order delivery to visitor (Task 5.4)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from kitchen.models import KitchenTicket
from menu.models import Category, Dish
from orders.models import Order, OrderItem
from orders.services import deliver_order


def _make_ready_order(
    django_user_model: Any,
    *,
    ticket_status: str = "done",
) -> tuple[Order, Any]:
    """Create a READY order with a kitchen ticket."""
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.READY,
        ready_at=timezone.now(),
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(order_item=item, status=ticket_status)
    return order, waiter


# --- Service tests ---


@pytest.mark.django_db
def test_deliver_order_success(django_user_model: Any) -> None:
    order, waiter = _make_ready_order(django_user_model)

    result = deliver_order(order, waiter=waiter)

    assert result.status == Order.Status.DELIVERED
    assert result.delivered_at is not None


@pytest.mark.django_db
def test_deliver_fails_if_ticket_not_done(django_user_model: Any) -> None:
    order, waiter = _make_ready_order(django_user_model, ticket_status="taken")

    with pytest.raises(ValueError, match="not yet ready"):
        deliver_order(order, waiter=waiter)


@pytest.mark.django_db
def test_deliver_fails_if_not_ready_status(django_user_model: Any) -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.VERIFIED)

    with pytest.raises(ValueError, match="not ready"):
        deliver_order(order, waiter=waiter)


@pytest.mark.django_db
def test_deliver_fails_wrong_waiter(django_user_model: Any) -> None:
    order, _ = _make_ready_order(django_user_model)
    other_waiter = django_user_model.objects.create_user(
        email="w2@test.com", username="w2", password="testpass123", role="waiter"
    )

    with pytest.raises(ValueError, match="Only the assigned waiter"):
        deliver_order(order, waiter=other_waiter)


# --- View tests ---


@pytest.mark.django_db
def test_deliver_view_success(client: Client, django_user_model: Any) -> None:
    order, waiter = _make_ready_order(django_user_model)

    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/delivered/")

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED


@pytest.mark.django_db
def test_deliver_view_shows_error_on_failure(
    client: Client, django_user_model: Any
) -> None:
    order, waiter = _make_ready_order(django_user_model, ticket_status="taken")

    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/delivered/", follow=True)

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.READY  # not changed


@pytest.mark.django_db
def test_unpaid_delivered_shown_on_dashboard(
    client: Client, django_user_model: Any
) -> None:
    order, waiter = _make_ready_order(django_user_model)
    deliver_order(order, waiter=waiter)

    client.force_login(waiter)
    response = client.get("/waiter/dashboard/")

    content = response.content.decode()
    assert "НЕ ОПЛАЧЕНО" in content
    assert f"#{order.id}" in content
