"""Tests for Z5: Edit/Cancel orders before verification."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client, RequestFactory

from menu.models import Category, Dish
from orders.models import Order, OrderEvent, OrderItem
from orders.services import cancel_order, can_edit_order, update_order_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dish(title: str = "TestDish", price: str = "5.00") -> Dish:
    cat, _ = Category.objects.get_or_create(
        title="Cat", defaults={"description": "", "number_in_line": 1}
    )
    return Dish.objects.create(
        title=title,
        description="desc",
        price=Decimal(price),
        weight=100,
        calorie=100,
        category=cat,
    )


def _make_order(
    status: str = "submitted",
    visitor: Any = None,
    waiter: Any = None,
) -> Order:
    order = Order.objects.create(status=status, visitor=visitor, waiter=waiter)
    return order


def _add_item(order: Order, dish: Dish, qty: int = 1) -> OrderItem:
    return OrderItem.objects.create(order=order, dish=dish, quantity=qty)


def _make_request(
    user: Any = None,
    session_orders: dict[str, str] | None = None,
) -> Any:
    factory = RequestFactory()
    request = factory.post("/fake/")
    if user:
        request.user = user
    else:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
    request.session = {}  # type: ignore[assignment]
    if session_orders:
        request.session["my_orders"] = session_orders
    return request


def _make_visitor(django_user_model: Any) -> Any:
    return django_user_model.objects.create_user(
        email="visitor@test.ua",
        username="visitor_edit",
        password="test1234",
        role="visitor",
    )


def _make_waiter(django_user_model: Any) -> Any:
    return django_user_model.objects.create_user(
        email="waiter@test.ua",
        username="waiter_edit",
        password="test1234",
        role="waiter",
        first_name="Test",
        last_name="Waiter",
    )


# ---------------------------------------------------------------------------
# Service: can_edit_order
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_can_edit_submitted_by_owner(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="submitted", visitor=visitor)
    request = _make_request(user=visitor)
    assert can_edit_order(order, request) is True


@pytest.mark.django_db
def test_cannot_edit_submitted_by_waiter(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    waiter = _make_waiter(django_user_model)
    order = _make_order(status="submitted", visitor=visitor, waiter=waiter)
    request = _make_request(user=waiter)
    assert can_edit_order(order, request) is False


@pytest.mark.django_db
def test_can_edit_accepted_by_waiter(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    waiter = _make_waiter(django_user_model)
    order = _make_order(status="accepted", visitor=visitor, waiter=waiter)
    request = _make_request(user=waiter)
    assert can_edit_order(order, request) is True


@pytest.mark.django_db
def test_cannot_edit_verified(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="verified", visitor=visitor)
    request = _make_request(user=visitor)
    assert can_edit_order(order, request) is False


@pytest.mark.django_db
def test_can_edit_via_session_token() -> None:
    order = _make_order(status="submitted")
    request = _make_request(session_orders={str(order.id): str(order.access_token)})
    assert can_edit_order(order, request) is True


# ---------------------------------------------------------------------------
# Service: update_order_items
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_item_reduces_quantity(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish(price="10.00")
    order = _make_order(status="submitted", visitor=visitor)
    item = _add_item(order, dish, qty=3)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_updated"),
        patch("orders.services.push_visitor_event"),
    ):
        update_order_items(order, {item.id: 2}, request)

    item.refresh_from_db()
    assert item.quantity == 2
    assert order.total_price == Decimal("20.00")


@pytest.mark.django_db
def test_update_item_zero_removes_item(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish1 = _make_dish(title="Dish1", price="5.00")
    dish2 = _make_dish(title="Dish2", price="10.00")
    order = _make_order(status="submitted", visitor=visitor)
    item1 = _add_item(order, dish1, qty=1)
    _add_item(order, dish2, qty=1)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_updated"),
        patch("orders.services.push_visitor_event"),
    ):
        update_order_items(order, {item1.id: 0}, request)

    assert not OrderItem.objects.filter(id=item1.id).exists()
    assert order.items.count() == 1


@pytest.mark.django_db
def test_update_all_items_zero_cancels_order(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish()
    order = _make_order(status="submitted", visitor=visitor)
    item = _add_item(order, dish, qty=1)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_cancelled"),
        patch("orders.services.push_visitor_event"),
    ):
        result = update_order_items(order, {item.id: 0}, request)

    result.refresh_from_db()
    assert result.status == Order.Status.CANCELLED
    assert result.cancelled_at is not None


@pytest.mark.django_db
def test_edit_blocked_after_verified(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish()
    order = _make_order(status="verified", visitor=visitor)
    item = _add_item(order, dish, qty=2)
    request = _make_request(user=visitor)

    with pytest.raises(ValueError, match="не можна редагувати"):
        update_order_items(order, {item.id: 1}, request)


# ---------------------------------------------------------------------------
# Service: cancel_order
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cancel_sets_status(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="submitted", visitor=visitor)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_cancelled"),
        patch("orders.services.push_visitor_event"),
    ):
        cancel_order(order, request)

    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert order.cancelled_at is not None


@pytest.mark.django_db
def test_cancel_blocked_after_verified(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="verified", visitor=visitor)
    request = _make_request(user=visitor)

    with pytest.raises(ValueError, match="не можна скасувати"):
        cancel_order(order, request)


# ---------------------------------------------------------------------------
# SSE + Event log
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_edit_pushes_sse(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish()
    order = _make_order(status="submitted", visitor=visitor)
    item = _add_item(order, dish, qty=3)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_updated") as mock_updated,
        patch("orders.services.push_visitor_event") as mock_visitor,
    ):
        update_order_items(order, {item.id: 2}, request)

    mock_updated.assert_called_once_with(order.id)
    mock_visitor.assert_called_once()
    assert mock_visitor.call_args[1]["event_type"] == "order_updated"


@pytest.mark.django_db
def test_cancel_pushes_sse(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="submitted", visitor=visitor)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_cancelled") as mock_cancelled,
        patch("orders.services.push_visitor_event"),
    ):
        cancel_order(order, request)

    mock_cancelled.assert_called_once_with(order.id)


@pytest.mark.django_db
def test_edit_logs_order_event(django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish(title="Борщ")
    order = _make_order(status="submitted", visitor=visitor)
    item = _add_item(order, dish, qty=3)
    request = _make_request(user=visitor)

    with (
        patch("orders.services.push_order_updated"),
        patch("orders.services.push_visitor_event"),
        patch("orders.event_log.push_order_log_event"),
    ):
        update_order_items(order, {item.id: 1}, request)

    event = OrderEvent.objects.filter(order=order).last()
    assert event is not None
    assert "Борщ" in event.message
    assert "3 → 1" in event.message


# ---------------------------------------------------------------------------
# Visitor AJAX views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_visitor_edit_ajax(client: Client, django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    dish = _make_dish(price="10.00")
    order = _make_order(status="submitted", visitor=visitor)
    item = _add_item(order, dish, qty=3)

    # Set session token
    session = client.session
    session["my_orders"] = {str(order.id): str(order.access_token)}
    session.save()

    with (
        patch("orders.services.push_order_updated"),
        patch("orders.services.push_visitor_event"),
        patch("orders.event_log.push_order_log_event"),
    ):
        response = client.post(
            f"/order/{order.id}/edit/",
            data=json.dumps({"items": {str(item.id): 2}}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["total_price"] == "20.00"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2


@pytest.mark.django_db
def test_visitor_cancel_ajax(client: Client, django_user_model: Any) -> None:
    visitor = _make_visitor(django_user_model)
    order = _make_order(status="submitted", visitor=visitor)
    _add_item(order, _make_dish(), qty=1)

    session = client.session
    session["my_orders"] = {str(order.id): str(order.access_token)}
    session.save()

    with (
        patch("orders.services.push_order_cancelled"),
        patch("orders.services.push_visitor_event"),
        patch("orders.event_log.push_order_log_event"),
    ):
        response = client.post(f"/order/{order.id}/cancel/")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "cancelled"


@pytest.mark.django_db
def test_visitor_edit_forbidden_no_token(client: Client) -> None:
    order = _make_order(status="submitted")
    _add_item(order, _make_dish(), qty=1)

    response = client.post(
        f"/order/{order.id}/edit/",
        data=json.dumps({"items": {"1": 2}}),
        content_type="application/json",
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Waiter AJAX views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_waiter_edit_accepted(client: Client, django_user_model: Any) -> None:
    waiter = _make_waiter(django_user_model)
    dish = _make_dish(price="8.00")
    order = _make_order(status="accepted", waiter=waiter)
    item = _add_item(order, dish, qty=2)

    client.force_login(waiter)

    with (
        patch("orders.services.push_order_updated"),
        patch("orders.services.push_visitor_event"),
        patch("orders.event_log.push_order_log_event"),
    ):
        response = client.post(
            f"/waiter/order/{order.id}/edit-items/",
            data=json.dumps({"items": {str(item.id): 1}}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["total_price"] == "8.00"


@pytest.mark.django_db
def test_waiter_cannot_edit_submitted(client: Client, django_user_model: Any) -> None:
    waiter = _make_waiter(django_user_model)
    dish = _make_dish()
    order = _make_order(status="submitted", waiter=waiter)
    item = _add_item(order, dish, qty=2)

    client.force_login(waiter)

    with patch("orders.event_log.push_order_log_event"):
        response = client.post(
            f"/waiter/order/{order.id}/edit-items/",
            data=json.dumps({"items": {str(item.id): 1}}),
            content_type="application/json",
        )

    assert response.status_code == 400


@pytest.mark.django_db
def test_waiter_cancel_accepted(client: Client, django_user_model: Any) -> None:
    waiter = _make_waiter(django_user_model)
    order = _make_order(status="accepted", waiter=waiter)
    _add_item(order, _make_dish(), qty=1)

    client.force_login(waiter)

    with (
        patch("orders.services.push_order_cancelled"),
        patch("orders.services.push_visitor_event"),
        patch("orders.event_log.push_order_log_event"),
    ):
        response = client.post(f"/waiter/order/{order.id}/cancel/")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["status"] == "cancelled"
