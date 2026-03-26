"""Tests for StepEscalation blame-tracking system."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.utils import timezone

from kitchen.models import KitchenTicket
from kitchen.services import manual_handoff, mark_ticket_done, take_ticket
from kitchen.tasks import escalate_cooking_tickets, escalate_handoff_tickets
from menu.models import Category, Dish
from orders.escalation_ownership import (
    create_step_escalation,
    promote_stale_seniors,
    resolve_step_escalations,
)
from orders.models import Order, OrderItem, StepEscalation
from orders.services import (
    accept_order,
    confirm_cash_payment,
    confirm_payment_by_senior,
    verify_order,
)
from orders.tasks import escalate_unaccepted_orders, escalate_unverified_orders


def _make_dish() -> Dish:
    cat = Category.objects.create(title="Test", description="", number_in_line=1)
    return Dish.objects.create(
        title="Borshch", description="", category=cat, price=10, weight=300, calorie=200
    )


def _make_order_with_ticket(
    django_user_model: Any,
) -> tuple[Order, KitchenTicket, Any, Any]:
    """Create a verified order with a kitchen ticket and cook/waiter users."""
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    cook = django_user_model.objects.create_user(
        email="c@test.com", username="c", password="testpass123", role="kitchen"
    )
    dish = _make_dish()
    order = Order.objects.create(
        status=Order.Status.VERIFIED,
        waiter=waiter,
        submitted_at=timezone.now() - timedelta(minutes=30),
        accepted_at=timezone.now() - timedelta(minutes=25),
        approved_at=timezone.now() - timedelta(minutes=20),
    )
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(order_item=item)
    return order, ticket, cook, waiter


# ==========================================================================
# Helper tests
# ==========================================================================


@pytest.mark.django_db
def test_create_and_resolve_step_escalation() -> None:
    order = Order.objects.create()
    esc = create_step_escalation(
        StepEscalation.Step.SUBMIT_ACCEPT,
        StepEscalation.Level.SENIOR,
        order=order,
        owner_role="senior_waiter",
    )
    assert esc.step == StepEscalation.Step.SUBMIT_ACCEPT
    assert esc.level == StepEscalation.Level.SENIOR
    assert esc.resolved_at is None

    count = resolve_step_escalations(StepEscalation.Step.SUBMIT_ACCEPT, order=order)
    assert count == 1
    esc.refresh_from_db()
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_promote_stale_seniors() -> None:
    order = Order.objects.create()
    esc = create_step_escalation(
        StepEscalation.Step.SUBMIT_ACCEPT,
        StepEscalation.Level.SENIOR,
        order=order,
        owner_role="senior_waiter",
    )
    # Backdate to 15 min ago
    StepEscalation.objects.filter(pk=esc.pk).update(
        created_at=timezone.now() - timedelta(minutes=15)
    )

    promoted = promote_stale_seniors(
        StepEscalation.Step.SUBMIT_ACCEPT,
        senior_timeout_minutes=10,
    )
    assert promoted == 1

    manager_esc = StepEscalation.objects.filter(
        step=StepEscalation.Step.SUBMIT_ACCEPT,
        level=StepEscalation.Level.MANAGER,
    ).first()
    assert manager_esc is not None
    assert manager_esc.order == order


@pytest.mark.django_db
def test_promote_stale_seniors_no_duplicate() -> None:
    order = Order.objects.create()
    esc = create_step_escalation(
        StepEscalation.Step.SUBMIT_ACCEPT,
        StepEscalation.Level.SENIOR,
        order=order,
        owner_role="senior_waiter",
    )
    StepEscalation.objects.filter(pk=esc.pk).update(
        created_at=timezone.now() - timedelta(minutes=15)
    )

    # First promotion
    promote_stale_seniors(StepEscalation.Step.SUBMIT_ACCEPT, 10)
    # Second promotion — should not create duplicate
    promoted = promote_stale_seniors(StepEscalation.Step.SUBMIT_ACCEPT, 10)
    assert promoted == 0

    assert (
        StepEscalation.objects.filter(
            step=StepEscalation.Step.SUBMIT_ACCEPT,
            level=StepEscalation.Level.MANAGER,
        ).count()
        == 1
    )


# ==========================================================================
# Task: escalate_unaccepted_orders
# ==========================================================================


@pytest.mark.django_db
def test_unaccepted_escalates() -> None:
    order = Order.objects.create(
        status=Order.Status.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=10),
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ACCEPT_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unaccepted_orders()

    assert result["senior"] == 1
    esc = StepEscalation.objects.filter(
        order=order, step=StepEscalation.Step.SUBMIT_ACCEPT
    ).first()
    assert esc is not None
    assert esc.owner_role == "senior_waiter"


@pytest.mark.django_db
def test_unaccepted_not_escalated_if_fresh() -> None:
    Order.objects.create(
        status=Order.Status.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=2),
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ACCEPT_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unaccepted_orders()

    assert result["senior"] == 0


@pytest.mark.django_db
def test_unaccepted_promotes_to_manager() -> None:
    order = Order.objects.create(
        status=Order.Status.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=20),
    )
    # Create stale senior escalation
    esc = create_step_escalation(
        StepEscalation.Step.SUBMIT_ACCEPT,
        StepEscalation.Level.SENIOR,
        order=order,
        owner_role="senior_waiter",
    )
    StepEscalation.objects.filter(pk=esc.pk).update(
        created_at=timezone.now() - timedelta(minutes=15)
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ACCEPT_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unaccepted_orders()

    assert result["promoted"] == 1


# ==========================================================================
# Task: escalate_unverified_orders
# ==========================================================================


@pytest.mark.django_db
def test_unverified_escalates(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        status=Order.Status.ACCEPTED,
        waiter=waiter,
        accepted_at=timezone.now() - timedelta(minutes=10),
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.VERIFY_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unverified_orders()

    assert result["senior"] == 1
    esc = StepEscalation.objects.filter(
        order=order, step=StepEscalation.Step.ACCEPT_VERIFY
    ).first()
    assert esc is not None
    assert esc.owner == waiter


@pytest.mark.django_db
def test_unverified_not_escalated_if_fresh(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    Order.objects.create(
        status=Order.Status.ACCEPTED,
        waiter=waiter,
        accepted_at=timezone.now() - timedelta(minutes=2),
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.VERIFY_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unverified_orders()

    assert result["senior"] == 0


@pytest.mark.django_db
def test_unverified_promotes_to_manager(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        status=Order.Status.ACCEPTED,
        waiter=waiter,
        accepted_at=timezone.now() - timedelta(minutes=20),
    )
    esc = create_step_escalation(
        StepEscalation.Step.ACCEPT_VERIFY,
        StepEscalation.Level.SENIOR,
        order=order,
        owner=waiter,
    )
    StepEscalation.objects.filter(pk=esc.pk).update(
        created_at=timezone.now() - timedelta(minutes=15)
    )

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.VERIFY_TIMEOUT = 5
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_unverified_orders()

    assert result["promoted"] == 1


# ==========================================================================
# Task: escalate_cooking_tickets
# ==========================================================================


@pytest.mark.django_db
def test_cooking_escalates(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.TAKEN
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now() - timedelta(minutes=20)
    ticket.save()

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.COOKING_TIMEOUT = 15
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_cooking_tickets()

    assert result["senior"] == 1
    esc = StepEscalation.objects.filter(
        ticket=ticket, step=StepEscalation.Step.TAKEN_DONE
    ).first()
    assert esc is not None
    assert esc.owner == cook


@pytest.mark.django_db
def test_cooking_not_escalated_if_fresh(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.TAKEN
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now() - timedelta(minutes=5)
    ticket.save()

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.COOKING_TIMEOUT = 15
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_cooking_tickets()

    assert result["senior"] == 0


@pytest.mark.django_db
def test_cooking_promotes_to_manager(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.TAKEN
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now() - timedelta(minutes=30)
    ticket.save()

    esc = create_step_escalation(
        StepEscalation.Step.TAKEN_DONE,
        StepEscalation.Level.SENIOR,
        ticket=ticket,
        order=ticket.order_item.order,
        owner=cook,
    )
    StepEscalation.objects.filter(pk=esc.pk).update(
        created_at=timezone.now() - timedelta(minutes=15)
    )

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.COOKING_TIMEOUT = 15
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_cooking_tickets()

    assert result["promoted"] == 1


# ==========================================================================
# Task: escalate_handoff_tickets
# ==========================================================================


@pytest.mark.django_db
def test_handoff_escalates(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.DONE
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now() - timedelta(minutes=30)
    ticket.done_at = timezone.now() - timedelta(minutes=15)
    ticket.save()

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.HANDOFF_TIMEOUT = 10
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_handoff_tickets()

    assert result["senior"] == 1
    esc = StepEscalation.objects.filter(
        ticket=ticket, step=StepEscalation.Step.DONE_HANDOFF
    ).first()
    assert esc is not None
    assert esc.owner == cook


@pytest.mark.django_db
def test_handoff_not_escalated_if_fresh(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.DONE
    ticket.assigned_to = cook
    ticket.done_at = timezone.now() - timedelta(minutes=3)
    ticket.save()

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.HANDOFF_TIMEOUT = 10
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_handoff_tickets()

    assert result["senior"] == 0


@pytest.mark.django_db
def test_handoff_not_escalated_if_already_handed_off(
    django_user_model: Any,
) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.DONE
    ticket.assigned_to = cook
    ticket.done_at = timezone.now() - timedelta(minutes=15)
    ticket.handed_off_at = timezone.now() - timedelta(minutes=5)
    ticket.save()

    with patch("kitchen.tasks.settings") as mock_settings:
        mock_settings.HANDOFF_TIMEOUT = 10
        mock_settings.SENIOR_RESPONSE_TIMEOUT = 10
        result = escalate_handoff_tickets()

    assert result["senior"] == 0


# ==========================================================================
# Auto-resolve in service functions
# ==========================================================================


@pytest.mark.django_db
def test_accept_order_resolves_submit_accept(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        status=Order.Status.SUBMITTED,
        submitted_at=timezone.now() - timedelta(minutes=10),
    )
    create_step_escalation(
        StepEscalation.Step.SUBMIT_ACCEPT,
        StepEscalation.Level.SENIOR,
        order=order,
        owner_role="senior_waiter",
    )

    accept_order(order, waiter)

    esc = StepEscalation.objects.get(order=order)
    assert esc.resolved_at is not None
    order.refresh_from_db()
    assert order.accepted_at is not None


@pytest.mark.django_db
def test_verify_order_resolves_accept_verify(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    dish = _make_dish()
    order = Order.objects.create(
        status=Order.Status.ACCEPTED,
        waiter=waiter,
        accepted_at=timezone.now() - timedelta(minutes=10),
    )
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    create_step_escalation(
        StepEscalation.Step.ACCEPT_VERIFY,
        StepEscalation.Level.SENIOR,
        order=order,
        owner=waiter,
    )

    verify_order(order, waiter)

    esc = StepEscalation.objects.get(order=order)
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_take_ticket_resolves_pending_taken(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    create_step_escalation(
        StepEscalation.Step.PENDING_TAKEN,
        StepEscalation.Level.SENIOR,
        ticket=ticket,
        order=ticket.order_item.order,
        owner_role="kitchen_supervisor",
    )

    take_ticket(ticket, cook)

    esc = StepEscalation.objects.get(ticket=ticket)
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_mark_done_resolves_taken_done(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.TAKEN
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now()
    ticket.save()

    create_step_escalation(
        StepEscalation.Step.TAKEN_DONE,
        StepEscalation.Level.SENIOR,
        ticket=ticket,
        order=ticket.order_item.order,
        owner=cook,
    )

    mark_ticket_done(ticket, cook)

    esc = StepEscalation.objects.get(ticket=ticket)
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_manual_handoff_resolves_done_handoff(django_user_model: Any) -> None:
    _, ticket, cook, _ = _make_order_with_ticket(django_user_model)
    ticket.status = KitchenTicket.Status.DONE
    ticket.assigned_to = cook
    ticket.taken_at = timezone.now() - timedelta(minutes=10)
    ticket.done_at = timezone.now()
    ticket.save()

    create_step_escalation(
        StepEscalation.Step.DONE_HANDOFF,
        StepEscalation.Level.SENIOR,
        ticket=ticket,
        order=ticket.order_item.order,
        owner=cook,
    )

    manual_handoff(ticket, cook)

    esc = StepEscalation.objects.get(ticket=ticket)
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_confirm_cash_payment_resolves_deliver_pay(
    django_user_model: Any,
) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    dish = _make_dish()
    order = Order.objects.create(
        status=Order.Status.DELIVERED,
        waiter=waiter,
        delivered_at=timezone.now() - timedelta(minutes=20),
    )
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    create_step_escalation(
        StepEscalation.Step.DELIVER_PAY,
        StepEscalation.Level.SENIOR,
        order=order,
        owner=waiter,
    )

    confirm_cash_payment(order, waiter)

    esc = StepEscalation.objects.get(order=order)
    assert esc.resolved_at is not None


@pytest.mark.django_db
def test_confirm_payment_by_senior_resolves_deliver_pay(
    django_user_model: Any,
) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    dish = _make_dish()
    order = Order.objects.create(
        status=Order.Status.DELIVERED,
        waiter=waiter,
        delivered_at=timezone.now() - timedelta(minutes=20),
    )
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    create_step_escalation(
        StepEscalation.Step.DELIVER_PAY,
        StepEscalation.Level.SENIOR,
        order=order,
        owner=waiter,
    )

    confirm_payment_by_senior(order, "cash")

    esc = StepEscalation.objects.get(order=order)
    assert esc.resolved_at is not None


# ==========================================================================
# Stats integration
# ==========================================================================


@pytest.mark.django_db
def test_waiter_stats_counts_errors(django_user_model: Any) -> None:
    from orders.stats import waiter_stats

    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter)

    # Create step escalation blamed on this waiter
    create_step_escalation(
        StepEscalation.Step.ACCEPT_VERIFY,
        StepEscalation.Level.SENIOR,
        order=order,
        owner=waiter,
    )

    since = timezone.now() - timedelta(hours=1)
    details, totals = waiter_stats(since)

    waiter_entry = next(d for d in details if d["user"].id == waiter.id)
    assert waiter_entry["errors"] == 1
    assert totals["errors"] == 1


@pytest.mark.django_db
def test_kitchen_stats_counts_errors(django_user_model: Any) -> None:
    from orders.stats import kitchen_stats

    cook = django_user_model.objects.create_user(
        email="c@test.com", username="c", password="testpass123", role="kitchen"
    )
    dish = _make_dish()
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item,
        status=KitchenTicket.Status.DONE,
        assigned_to=cook,
        taken_at=timezone.now() - timedelta(minutes=10),
        done_at=timezone.now(),
    )

    create_step_escalation(
        StepEscalation.Step.TAKEN_DONE,
        StepEscalation.Level.SENIOR,
        ticket=ticket,
        order=order,
        owner=cook,
    )

    since = timezone.now() - timedelta(hours=1)
    details, totals = kitchen_stats(since)

    cook_entry = next(d for d in details if d["user"].id == cook.id)
    assert cook_entry["errors"] == 1
    assert totals["errors"] == 1
