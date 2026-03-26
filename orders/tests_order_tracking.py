"""Tests for order detail live tracking UI (Tasks 9.3+9.4)."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from kitchen.models import KitchenTicket
from menu.models import Category, Dish
from orders.models import Order, OrderEvent, OrderItem
from orders.views import _build_progress_steps


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
    order = Order.objects.create(waiter=waiter, status=Order.Status.VERIFIED)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.TAKEN,
        assigned_to=cook,
    )
    # Template requires at least one event to show tracking section.
    OrderEvent.objects.create(order=order, message="Замовлення прийнято")
    return order, waiter


@pytest.mark.django_db
def test_order_detail_has_ticket_states(client: Client, django_user_model: Any) -> None:
    order, waiter = _make_approved_order(django_user_model)
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "order-progress" in content


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
def test_draft_order_no_progress_bar(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/?token={order.access_token}")
    content = response.content.decode()
    # Draft orders have no event log → no progress bar section.
    assert "order-progress" not in content
    assert "order-progress" not in content


def test_order_tracker_js_exists() -> None:
    assert os.path.exists(os.path.join("staticfiles", "js", "order_tracker.js"))


# ---------------------------------------------------------------------------
# _build_progress_steps() unit tests — Z23/Z24/Z25 regression prevention
# ---------------------------------------------------------------------------


class TestBuildProgressSteps:
    """Verify pipeline step calculation for partial progress (PWM)."""

    def test_cooking_uses_taken_count_not_done(self) -> None:
        """Z23: cooking progress must reflect taken/total, not done/total."""
        steps = _build_progress_steps(
            "in_progress",
            taken_count=5,
            done_count=1,
            total_tickets=5,
        )
        cooking = next(s for s in steps if s["step_key"] == "cooking")
        assert cooking["progress"] == 1.0
        assert cooking["done"] is True

    def test_cooking_partial_when_some_taken(self) -> None:
        """Cooking progress is partial when only some dishes taken."""
        steps = _build_progress_steps(
            "in_progress",
            taken_count=2,
            done_count=0,
            total_tickets=5,
        )
        cooking = next(s for s in steps if s["step_key"] == "cooking")
        assert cooking["progress"] == pytest.approx(0.4)
        assert cooking["active"] is True
        assert cooking["done"] is False

    def test_ready_uses_picked_up_count(self) -> None:
        """Ready progress reflects picked_up/total."""
        steps = _build_progress_steps(
            "in_progress",
            taken_count=5,
            done_count=5,
            picked_up_count=3,
            total_tickets=5,
        )
        ready = next(s for s in steps if s["step_key"] == "ready")
        assert ready["progress"] == pytest.approx(0.6)
        assert ready["active"] is True

    def test_delivered_uses_delivered_count(self) -> None:
        """Delivered progress reflects delivered/total."""
        steps = _build_progress_steps(
            "delivered",
            taken_count=5,
            done_count=5,
            picked_up_count=5,
            delivered_count=5,
            total_tickets=5,
        )
        delivered = next(s for s in steps if s["step_key"] == "delivered")
        assert delivered["progress"] == 1.0
        assert delivered["done"] is True

    def test_zero_tickets_no_division_error(self) -> None:
        """No ZeroDivisionError when order has no tickets."""
        steps = _build_progress_steps("submitted", total_tickets=0)
        cooking = next(s for s in steps if s["step_key"] == "cooking")
        assert cooking["progress"] == 0.0

    def test_binary_steps_done_up_to_current(self) -> None:
        """Non-partial steps are done if index <= current step."""
        steps = _build_progress_steps("verified", total_tickets=0)
        created = next(s for s in steps if s["step_key"] == "created")
        accepted = next(s for s in steps if s["step_key"] == "accepted")
        verified = next(s for s in steps if s["step_key"] == "verified")
        assert created["done"] is True
        assert accepted["done"] is True
        assert verified["done"] is True

    def test_all_complete_when_delivered(self) -> None:
        """All steps done when order is fully delivered with all tickets."""
        steps = _build_progress_steps(
            "delivered",
            taken_count=3,
            done_count=3,
            picked_up_count=3,
            delivered_count=3,
            total_tickets=3,
        )
        for s in steps:
            assert s["done"] is True, f"step {s['step_key']} should be done"
            assert s["active"] is False, f"step {s['step_key']} should not be active"


@pytest.mark.django_db
def test_pipeline_counts_in_template(client: Client, django_user_model: Any) -> None:
    """Verify data-taken-count attribute is rendered in HTML."""
    order, waiter = _make_approved_order(django_user_model)
    # OrderEvent required for tracking section to render
    OrderEvent.objects.create(order=order, message="Замовлення створено")
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    content = response.content.decode()
    assert 'data-taken-count="1"' in content
    assert 'data-total-tickets="1"' in content


@pytest.mark.django_db
def test_waiter_detail_single_payment_button(
    client: Client, django_user_model: Any
) -> None:
    """Z7: waiter order detail shows exactly one payment button, not two."""
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
        status=Order.Status.VERIFIED,
        payment_status="unpaid",
    )
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    client.force_login(waiter)
    response = client.get(f"/waiter/order/{order.id}/scan/")
    assert response.status_code == 200
    content = response.content.decode()
    # Template should render payment section
    assert "Оплату прийнято" in content
    # Only one payment form should exist (not two)
    assert content.count("confirm-payment") == 1
