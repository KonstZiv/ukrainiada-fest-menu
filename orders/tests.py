from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from menu.models import Category, Dish
from orders.models import Order, OrderItem


def test_order_status_flow_values() -> None:
    statuses = {s.value for s in Order.Status}
    expected = {"draft", "submitted", "approved", "in_progress", "ready", "delivered"}
    assert statuses == expected


def test_order_default_status_and_payment() -> None:
    order = Order()
    assert order.status == Order.Status.DRAFT
    assert order.payment_status == Order.PaymentStatus.UNPAID


@pytest.mark.django_db
def test_order_total_price() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    dish2 = Dish.objects.create(
        title="D2",
        description="",
        price=Decimal("3.50"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish1, quantity=2)
    OrderItem.objects.create(order=order, dish=dish2, quantity=1)
    assert order.total_price == Decimal("13.50")


@pytest.mark.django_db
def test_order_item_unique_per_dish() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(IntegrityError):
        OrderItem.objects.create(order=order, dish=dish, quantity=2)


@pytest.mark.django_db
def test_cannot_delete_dish_with_active_order() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(ProtectedError):
        dish.delete()


@pytest.mark.django_db
def test_order_str() -> None:
    order = Order.objects.create()
    assert f"Order #{order.pk}" in str(order)
    assert "Чернетка" in str(order)


@pytest.mark.django_db
def test_order_item_subtotal() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("7.50"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=3)
    assert item.subtotal == Decimal("22.50")
