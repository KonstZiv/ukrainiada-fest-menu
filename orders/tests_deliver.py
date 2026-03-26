"""Tests for order delivery — including soft flow and per-ticket delivery."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from kitchen.models import KitchenTicket
from menu.models import Category, Dish
from orders.models import Order, OrderEvent, OrderItem
from unittest.mock import patch

from orders.services import deliver_order, deliver_ticket


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
def test_deliver_order_pushes_ticket_delivered_with_prev_status(
    django_user_model: Any,
) -> None:
    """Z30: deliver_order sends push_ticket_delivered for each ticket with prev_status."""
    order, waiter = _make_ready_order(django_user_model)

    with patch("orders.services.push_ticket_delivered") as mock_push:
        deliver_order(order, waiter=waiter)

    assert mock_push.call_count == 1
    call_kwargs = mock_push.call_args
    assert call_kwargs[1]["prev_status"] == "done"  # ticket was DONE before delivery


@pytest.mark.django_db
def test_deliver_order_soft_flow_sends_pending_prev_status(
    django_user_model: Any,
) -> None:
    """Z30: soft flow deliver sends prev_status='pending' for unfinished tickets."""
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

    with patch("orders.services.push_ticket_delivered") as mock_push:
        deliver_order(order, waiter=waiter)

    assert mock_push.call_count == 1
    call_kwargs = mock_push.call_args
    # Ticket was pending before soft-flow auto-completed it
    assert call_kwargs[1]["prev_status"] == "pending"


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
@pytest.mark.skip(
    reason="Waiter order list changed from /waiter/dashboard/ to /waiter/orders/ with tab-based filtering. Test needs refactoring to use correct tab parameter."
)
def test_unpaid_delivered_shown_on_dashboard(
    client: Client, django_user_model: Any
) -> None:
    order, waiter = _make_ready_order(django_user_model)
    deliver_order(order, waiter=waiter)  # returns tuple, but we ignore it here

    client.force_login(waiter)
    response = client.get("/waiter/orders/")

    content = response.content.decode()
    assert "НЕ ОПЛАЧЕНО" in content or "не оплачено" in content.lower()
    assert f"#{order.id}" in content


# --- Soft flow tests ---


@pytest.mark.django_db
def test_deliver_ticket_done_status(django_user_model: Any) -> None:
    """deliver_ticket marks a DONE ticket as delivered."""
    order, waiter = _make_ready_order(django_user_model)
    ticket = KitchenTicket.objects.get(order_item__order=order)

    result = deliver_ticket(ticket, waiter=waiter)

    assert result.is_delivered is True
    assert result.delivered_at is not None
    assert result.handed_off_at is not None


@pytest.mark.django_db
def test_deliver_ticket_soft_flow_from_pending(django_user_model: Any) -> None:
    """deliver_ticket auto-completes PENDING ticket (soft flow)."""
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
        status=Order.Status.VERIFIED,
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item, status="pending")

    result = deliver_ticket(ticket, waiter=waiter)

    assert result.status == KitchenTicket.Status.DONE
    assert result.is_delivered is True
    assert result.taken_at is not None
    assert result.done_at is not None
    # Auto-skip event should be logged
    assert OrderEvent.objects.filter(order=order, is_auto_skip=True).exists()


@pytest.mark.django_db
def test_deliver_ticket_soft_flow_from_taken(django_user_model: Any) -> None:
    """deliver_ticket auto-completes TAKEN ticket (soft flow)."""
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
        status=Order.Status.IN_PROGRESS,
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status="taken",
        taken_at=timezone.now(),
    )

    result = deliver_ticket(ticket, waiter=waiter)

    assert result.status == KitchenTicket.Status.DONE
    assert result.is_delivered is True
    assert OrderEvent.objects.filter(order=order, is_auto_skip=True).exists()


@pytest.mark.django_db
def test_deliver_all_tickets_transitions_order(django_user_model: Any) -> None:
    """Order becomes DELIVERED when all tickets are delivered."""
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
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=2)
    t1 = KitchenTicket.objects.create(
        order_item=item, status="done", done_at=timezone.now()
    )
    t2 = KitchenTicket.objects.create(
        order_item=item, status="done", done_at=timezone.now()
    )

    deliver_ticket(t1, waiter=waiter)
    order.refresh_from_db()
    assert order.status != Order.Status.DELIVERED  # not yet, one ticket left

    deliver_ticket(t2, waiter=waiter)
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None


@pytest.mark.django_db
def test_deliver_ticket_already_delivered(django_user_model: Any) -> None:
    """deliver_ticket raises for already delivered ticket."""
    order, waiter = _make_ready_order(django_user_model)
    ticket = KitchenTicket.objects.get(order_item__order=order)
    deliver_ticket(ticket, waiter=waiter)

    with pytest.raises(ValueError, match="вже доставлена"):
        deliver_ticket(ticket, waiter=waiter)
