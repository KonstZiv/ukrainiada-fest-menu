"""Tests for order detail live tracking UI (Tasks 9.3+9.4)."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from kitchen.models import KitchenTicket
from menu.models import Category, Dish
from orders.models import Order, OrderItem


def _make_approved_order(
    django_user_model: Any,
) -> tuple[Order, Any]:
    """Create an approved order with kitchen tickets."""
    cat = Category.objects.create(title_uk="C", description_uk="", number_in_line=1)
    dish = Dish.objects.create(
        title_uk="Борщ",
        description_uk="",
        price=Decimal("8.00"),
        weight=400,
        calorie=320,
        category=cat,
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    cook = django_user_model.objects.create_user(
        email="k@test.com",
        username="k",
        password="testpass123",
        role="kitchen",
        display_title="Повариха",
        public_name="Валентина",
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.APPROVED)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=cook,
    )
    return order, waiter


@pytest.mark.django_db
def test_order_detail_has_ticket_states(client: Client, django_user_model: Any) -> None:
    order, waiter = _make_approved_order(django_user_model)
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "data-ticket-id" in content
    assert "ticket-status-row" in content


@pytest.mark.django_db
def test_order_detail_has_progress_bar(client: Client, django_user_model: Any) -> None:
    order, waiter = _make_approved_order(django_user_model)
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    content = response.content.decode()
    assert "order-progress" in content
    assert "progress-step" in content


@pytest.mark.django_db
def test_order_detail_has_cook_label(client: Client, django_user_model: Any) -> None:
    order, waiter = _make_approved_order(django_user_model)
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    content = response.content.decode()
    assert "Повариха Валентина" in content


@pytest.mark.django_db
def test_order_detail_includes_tracker_js(
    client: Client, django_user_model: Any
) -> None:
    order, waiter = _make_approved_order(django_user_model)
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    content = response.content.decode()
    assert "order_tracker.js" in content


@pytest.mark.django_db
def test_draft_order_no_tracker(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/?token={order.access_token}")
    content = response.content.decode()
    assert "order_tracker.js" not in content
    assert "order-progress" not in content


def test_order_tracker_js_exists() -> None:
    assert os.path.exists(os.path.join("staticfiles", "js", "order_tracker.js"))
