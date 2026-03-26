"""Tests for OrderEvent model and event logging in order lifecycle."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from menu.models import Category, Dish
from orders.event_log import log_event
from orders.models import Order, OrderEvent, OrderItem


@pytest.fixture
def category() -> Category:
    return Category.objects.create(title="Cat", description="", number_in_line=1)


@pytest.fixture
def dish(category: Category) -> Dish:
    return Dish.objects.create(
        title="Борщ",
        description="Наваристий борщ",
        price=Decimal("8.00"),
        weight=300,
        calorie=250,
        category=category,
        availability="available",
    )


# --- Model tests ---


@pytest.mark.django_db
def test_order_event_created() -> None:
    """OrderEvent can be created with basic fields."""
    order = Order.objects.create()
    event = log_event(order, "Test event", actor_label="Тестер")
    assert event.pk is not None
    assert event.order == order
    assert event.message == "Test event"
    assert event.actor_label == "Тестер"
    assert event.timestamp is not None


@pytest.mark.django_db
def test_order_event_log_line_format() -> None:
    """log_line property formats timestamp + message."""
    order = Order.objects.create()
    event = log_event(order, "Замовлення створено")
    line = event.log_line
    assert "Замовлення створено" in line
    assert "—" in line


@pytest.mark.django_db
def test_order_event_ordering() -> None:
    """Events are ordered by timestamp (ascending)."""
    order = Order.objects.create()
    e1 = log_event(order, "First")
    e2 = log_event(order, "Second")
    events = list(order.events.all())
    assert events == [e1, e2]


# --- Integration: events created during order lifecycle ---


@pytest.mark.django_db
def test_submit_order_creates_event(client: Client, dish: Dish) -> None:
    """Submitting an order logs 'замовлення сформовано' event."""
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 1}]
    session.save()

    client.post("/order/submit/")

    order = Order.objects.first()
    assert order is not None
    events = list(order.events.all())
    assert len(events) == 1
    assert "сформовано" in events[0].message.lower()
    assert dish.title in events[0].message


@pytest.mark.django_db
def test_approve_order_creates_event(
    client: Client, dish: Dish, django_user_model: Any
) -> None:
    """Approving an order logs event with waiter name."""
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    OrderItem.objects.create(order=order, dish=dish, quantity=1)

    waiter = django_user_model.objects.create_user(
        email="w@test.com",
        username="waiter1",
        password="testpass123",
        role="waiter",
    )
    client.force_login(waiter)
    client.post(f"/waiter/order/{order.id}/approve/")

    events = list(order.events.all())
    assert any(
        "верифікував" in e.message.lower() or "перевірив" in e.message.lower()
        for e in events
    )


@pytest.mark.django_db
def test_deliver_order_creates_event(django_user_model: Any) -> None:
    """Delivering an order logs event."""
    from orders.services import deliver_order

    waiter = django_user_model.objects.create_user(
        email="w@test.com",
        username="waiter1",
        password="testpass123",
        role="waiter",
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.READY,
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)

    from kitchen.models import KitchenTicket

    KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.DONE,
    )

    deliver_order(order, waiter)
    events = list(order.events.all())
    assert any("доставив" in e.message.lower() for e in events)


@pytest.mark.django_db
def test_cash_payment_creates_event(django_user_model: Any) -> None:
    """Confirming cash payment logs event."""
    from orders.services import confirm_cash_payment

    waiter = django_user_model.objects.create_user(
        email="w@test.com",
        username="waiter1",
        password="testpass123",
        role="waiter",
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    confirm_cash_payment(order, waiter=waiter)
    events = list(order.events.all())
    assert any("оплату" in e.message.lower() for e in events)


@pytest.mark.django_db
def test_online_payment_creates_event() -> None:
    """Online payment stub logs event."""
    from orders.services import confirm_online_payment_stub

    order = Order.objects.create(payment_status=Order.PaymentStatus.UNPAID)
    confirm_online_payment_stub(order)
    events = list(order.events.all())
    assert any("онлайн" in e.message.lower() for e in events)
