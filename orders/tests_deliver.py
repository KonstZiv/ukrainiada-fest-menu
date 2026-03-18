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

    result, skipped = deliver_order(order, waiter=waiter)

    assert result.status == Order.Status.DELIVERED
    assert result.delivered_at is not None
    assert skipped == []


@pytest.mark.django_db
def test_deliver_auto_completes_unfinished_tickets(django_user_model: Any) -> None:
    """Soft flow: delivering a READY order with non-DONE tickets auto-completes them."""
    order, waiter = _make_ready_order(django_user_model, ticket_status="taken")

    result, skipped = deliver_order(order, waiter=waiter)

    assert result.status == Order.Status.DELIVERED
    assert len(skipped) == 1  # one ticket auto-completed
    ticket = KitchenTicket.objects.get(order_item__order=order)
    assert ticket.status == KitchenTicket.Status.DONE


@pytest.mark.django_db
def test_deliver_soft_flow_from_verified(django_user_model: Any) -> None:
    """Soft flow: delivering a VERIFIED order auto-completes tickets and sets READY."""
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
    order = Order.objects.create(waiter=waiter, status=Order.Status.VERIFIED)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(order_item=item, status="pending")

    result, skipped = deliver_order(order, waiter=waiter)

    assert result.status == Order.Status.DELIVERED
    assert len(skipped) >= 2  # ticket auto-completed + "Готово (кухня)"


@pytest.mark.django_db
def test_deliver_fails_if_not_sent_to_kitchen(django_user_model: Any) -> None:
    """Delivery should fail for orders not yet sent to kitchen (SUBMITTED/ACCEPTED)."""
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.ACCEPTED)

    with pytest.raises(ValueError, match="не передано на кухню"):
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
def test_deliver_view_shows_error_for_accepted_order(
    client: Client, django_user_model: Any
) -> None:
    """Delivery view should show error for orders not yet sent to kitchen."""
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="wtest", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.ACCEPTED)

    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/delivered/", follow=True)

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.ACCEPTED  # not changed


@pytest.mark.django_db
def test_unpaid_delivered_shown_on_dashboard(
    client: Client, django_user_model: Any
) -> None:
    order, waiter = _make_ready_order(django_user_model)
    deliver_order(order, waiter=waiter)  # returns tuple, but we ignore it here

    client.force_login(waiter)
    response = client.get("/waiter/dashboard/")

    content = response.content.decode()
    assert "НЕ ОПЛАЧЕНО" in content
    assert f"#{order.id}" in content
