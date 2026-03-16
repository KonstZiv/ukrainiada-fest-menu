"""Tests for manual handoff fallback (Task 5.3)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from kitchen.models import KitchenHandoff, KitchenTicket
from kitchen.services import manual_handoff
from menu.models import Category, Dish
from orders.models import Order, OrderItem


def _make_done_ticket(
    django_user_model: Any,
) -> tuple[KitchenTicket, Any, Any]:
    """Create a DONE ticket with kitchen user and waiter."""
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="TestDish",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
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
    return ticket, kitchen_user, waiter


@pytest.mark.django_db
def test_manual_handoff_success(django_user_model: Any) -> None:
    ticket, kitchen_user, _ = _make_done_ticket(django_user_model)
    manual_handoff(ticket, kitchen_user=kitchen_user)


@pytest.mark.django_db
def test_manual_handoff_cancels_pending_qr(django_user_model: Any) -> None:
    ticket, kitchen_user, waiter = _make_done_ticket(django_user_model)
    handoff = KitchenHandoff.objects.create(ticket=ticket, target_waiter=waiter)

    manual_handoff(ticket, kitchen_user=kitchen_user)

    handoff.refresh_from_db()
    assert handoff.is_confirmed is True
    assert handoff.confirmed_at is not None


@pytest.mark.django_db
def test_manual_handoff_wrong_cook(django_user_model: Any) -> None:
    ticket, _, _ = _make_done_ticket(django_user_model)
    other_cook = django_user_model.objects.create_user(
        email="k2@test.com", username="k2", password="testpass123", role="kitchen"
    )

    with pytest.raises(ValueError, match="Only the assigned cook"):
        manual_handoff(ticket, kitchen_user=other_cook)


@pytest.mark.django_db
def test_manual_handoff_wrong_status(django_user_model: Any) -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", username="ktest", password="testpass123", role="kitchen"
    )
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=kitchen_user,
    )

    with pytest.raises(ValueError, match="Cannot handoff ticket"):
        manual_handoff(ticket, kitchen_user=kitchen_user)


@pytest.mark.django_db
def test_manual_handoff_idempotent(django_user_model: Any) -> None:
    ticket, kitchen_user, _ = _make_done_ticket(django_user_model)
    manual_handoff(ticket, kitchen_user=kitchen_user)
    manual_handoff(ticket, kitchen_user=kitchen_user)


# --- View tests ---


@pytest.mark.django_db
def test_manual_handoff_view_post(client: Client, django_user_model: Any) -> None:
    ticket, kitchen_user, _ = _make_done_ticket(django_user_model)

    client.force_login(kitchen_user)
    response = client.post(f"/kitchen/ticket/{ticket.id}/manual-handoff/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_manual_handoff_view_requires_post(
    client: Client, django_user_model: Any
) -> None:
    ticket, kitchen_user, _ = _make_done_ticket(django_user_model)

    client.force_login(kitchen_user)
    response = client.get(f"/kitchen/ticket/{ticket.id}/manual-handoff/")

    assert response.status_code == 405


@pytest.mark.django_db
def test_manual_handoff_view_wrong_cook_404(
    client: Client, django_user_model: Any
) -> None:
    ticket, _, _ = _make_done_ticket(django_user_model)
    other_cook = django_user_model.objects.create_user(
        email="k2@test.com", username="k2", password="testpass123", role="kitchen"
    )

    client.force_login(other_cook)
    response = client.post(f"/kitchen/ticket/{ticket.id}/manual-handoff/")

    assert response.status_code == 404
