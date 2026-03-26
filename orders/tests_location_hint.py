"""Tests for Order.location_hint field (Task 8.3)."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from orders.models import Order


@pytest.mark.django_db
def test_location_hint_blank_allowed() -> None:
    order = Order.objects.create()
    assert order.location_hint == ""


@pytest.mark.django_db
def test_location_hint_saved() -> None:
    order = Order.objects.create(location_hint="біля дерева")
    order.refresh_from_db()
    assert order.location_hint == "біля дерева"


@pytest.mark.django_db
def test_location_hint_shown_on_waiter_dashboard(
    client: Client, django_user_model: Any
) -> None:
    from decimal import Decimal

    from menu.models import Category, Dish

    waiter = django_user_model.objects.create_user(  # type: ignore[union-attr]
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    cat = Category.objects.create(title_uk="C", description_uk="", number_in_line=1)
    dish = Dish.objects.create(
        title_uk="D",
        description_uk="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.VERIFIED,
        location_hint="столик у Марини",
    )
    from orders.models import OrderItem

    OrderItem.objects.create(order=order, dish=dish, quantity=1)

    client.force_login(waiter)
    response = client.get("/waiter/dashboard/")
    content = response.content.decode()
    assert "столик у Марини" in content
