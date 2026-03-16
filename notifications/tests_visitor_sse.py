"""Tests for visitor SSE channel and push events (Tasks 9.1+9.2)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from kitchen.models import KitchenTicket
from kitchen.services import mark_ticket_done, take_ticket
from menu.models import Category, Dish
from notifications.channels import channels_for_user, visitor_order_channel
from orders.models import Order, OrderItem
from orders.services import approve_order, deliver_order


def test_visitor_order_channel_format() -> None:
    assert visitor_order_channel(42) == "visitor-order-42"


def test_visitor_channel_not_in_user_channels() -> None:
    from user.models import User

    user = User(role="visitor", email="v@test.com")
    assert not any(c.startswith("visitor-order-") for c in channels_for_user(user))


def test_visitor_event_payload_size() -> None:
    payload = {
        "type": "ticket_taken",
        "ticket_id": 42,
        "dish": "Борщ",
        "cook_label": "Повариха Валентина",
    }
    assert len(json.dumps(payload).encode()) < 200


@pytest.mark.django_db
def test_visitor_sse_endpoint_unauthorized(client: Client) -> None:
    order = Order.objects.create()
    response = client.get(f"/events/visitor/{order.id}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_visitor_sse_endpoint_with_token(client: Client) -> None:
    order = Order.objects.create()
    response = client.get(
        f"/events/visitor/{order.id}/?token={order.access_token}",
        HTTP_ACCEPT="text/event-stream",
    )
    # EventResponse returns 200 for valid SSE
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_take_ticket_pushes_visitor_event(django_user_model: Any) -> None:
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
    ticket = KitchenTicket.objects.create(order_item=item)

    with patch("kitchen.services.push_visitor_event") as mock_push:
        take_ticket(ticket, kitchen_user=cook)

    mock_push.assert_called_once()
    call_kwargs = mock_push.call_args[1]
    assert call_kwargs["event_type"] == "ticket_taken"
    assert call_kwargs["data"]["cook_label"] == "Повариха Валентина"


@pytest.mark.django_db
def test_approve_pushes_visitor_event(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(status=Order.Status.SUBMITTED)

    with patch("orders.services.push_visitor_event") as mock_push:
        approve_order(order, waiter)

    mock_push.assert_called_once()
    assert mock_push.call_args[1]["event_type"] == "order_approved"


@pytest.mark.django_db
def test_deliver_pushes_visitor_event(django_user_model: Any) -> None:
    cat = Category.objects.create(title_uk="C", description_uk="", number_in_line=1)
    dish = Dish.objects.create(
        title_uk="D",
        description_uk="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.READY,
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(order_item=item, status=KitchenTicket.Status.DONE)

    with patch("orders.services.push_visitor_event") as mock_push:
        deliver_order(order, waiter=waiter)

    mock_push.assert_called_once()
    assert mock_push.call_args[1]["event_type"] == "order_delivered"
