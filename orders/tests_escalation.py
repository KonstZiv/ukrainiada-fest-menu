"""Tests for VisitorEscalation model, services, and Celery task (Tasks 10.1+10.3)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.utils import timezone

from orders.escalation_services import (
    acknowledge_escalation,
    create_escalation,
    resolve_escalation,
)
from orders.models import Order, VisitorEscalation
from orders.tasks import escalate_visitor_issues


# --- Model tests ---


@pytest.mark.django_db
def test_escalation_str() -> None:
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(order=order, reason="slow")
    assert "Escalation" in str(esc)
    assert "open" in str(esc).lower()


# --- Service: create ---


@pytest.mark.django_db
def test_create_escalation_success() -> None:
    order = Order.objects.create(
        status=Order.Status.VERIFIED,
        approved_at=timezone.now() - timedelta(minutes=10),
    )
    esc = create_escalation(order, reason="slow", message="Дуже довго")
    assert esc.reason == "slow"
    assert esc.level == VisitorEscalation.Level.WAITER
    assert esc.status == VisitorEscalation.Status.OPEN


@pytest.mark.django_db
def test_cannot_create_duplicate_open() -> None:
    order = Order.objects.create(
        status=Order.Status.VERIFIED,
        approved_at=timezone.now() - timedelta(minutes=10),
    )
    create_escalation(order, reason="slow")
    with pytest.raises(ValueError, match="вже є активне"):
        create_escalation(order, reason="wrong")


@pytest.mark.django_db
def test_min_wait_enforced() -> None:
    order = Order.objects.create(
        status=Order.Status.VERIFIED,
        approved_at=timezone.now() - timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="Зачекайте"):
        create_escalation(order, reason="slow")


@pytest.mark.django_db
def test_cooldown_after_resolved() -> None:
    order = Order.objects.create(
        status=Order.Status.VERIFIED,
        approved_at=timezone.now() - timedelta(minutes=10),
    )
    esc = create_escalation(order, reason="slow")
    esc.status = VisitorEscalation.Status.RESOLVED
    esc.resolved_at = timezone.now()
    esc.save()

    with pytest.raises(ValueError, match="щойно вирішено"):
        create_escalation(order, reason="wrong")


# --- Service: acknowledge + resolve ---


@pytest.mark.django_db
def test_acknowledge_updates_status(django_user_model: Any) -> None:
    staff = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(order=order, reason="slow")

    acknowledge_escalation(esc, staff)
    esc.refresh_from_db()
    assert esc.status == VisitorEscalation.Status.ACKNOWLEDGED
    assert esc.acknowledged_at is not None


@pytest.mark.django_db
def test_resolve_sets_fields(django_user_model: Any) -> None:
    staff = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(order=order, reason="slow")

    resolve_escalation(esc, staff, note="Вибачте!")
    esc.refresh_from_db()
    assert esc.status == VisitorEscalation.Status.RESOLVED
    assert esc.resolved_by == staff
    assert esc.resolution_note == "Вибачте!"


@pytest.mark.django_db
def test_cannot_resolve_already_resolved(django_user_model: Any) -> None:
    staff = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(
        order=order, reason="slow", status=VisitorEscalation.Status.RESOLVED
    )
    with pytest.raises(ValueError, match="вже вирішена"):
        resolve_escalation(esc, staff)


# --- Celery task ---


@pytest.mark.django_db
def test_auto_escalation_to_senior() -> None:
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(order=order, reason="slow")
    old_time = timezone.now() - timedelta(minutes=5)
    VisitorEscalation.objects.filter(pk=esc.pk).update(created_at=old_time)

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ESCALATION_AUTO_LEVEL = 3
        result = escalate_visitor_issues()

    esc.refresh_from_db()
    assert esc.level == VisitorEscalation.Level.SENIOR
    assert result["to_senior"] >= 1


@pytest.mark.django_db
def test_auto_escalation_to_manager() -> None:
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(order=order, reason="slow")
    old_time = timezone.now() - timedelta(minutes=10)
    VisitorEscalation.objects.filter(pk=esc.pk).update(created_at=old_time)

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ESCALATION_AUTO_LEVEL = 3
        result = escalate_visitor_issues()

    esc.refresh_from_db()
    assert esc.level == VisitorEscalation.Level.MANAGER
    assert result["to_manager"] >= 1


@pytest.mark.django_db
def test_resolved_not_escalated() -> None:
    order = Order.objects.create()
    esc = VisitorEscalation.objects.create(
        order=order, reason="slow", status=VisitorEscalation.Status.RESOLVED
    )
    old_time = timezone.now() - timedelta(minutes=10)
    VisitorEscalation.objects.filter(pk=esc.pk).update(created_at=old_time)

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.ESCALATION_AUTO_LEVEL = 3
        escalate_visitor_issues()

    esc.refresh_from_db()
    assert esc.level == VisitorEscalation.Level.WAITER
