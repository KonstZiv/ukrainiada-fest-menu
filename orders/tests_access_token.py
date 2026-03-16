"""Tests for Order.access_token and access control (Task 8.2)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.test import Client, RequestFactory

from orders.models import Order
from orders.services import can_access_order


@pytest.mark.django_db
def test_token_auto_generated() -> None:
    order = Order.objects.create()
    assert order.access_token is not None
    assert isinstance(order.access_token, uuid.UUID)


@pytest.mark.django_db
def test_token_unique() -> None:
    o1 = Order.objects.create()
    o2 = Order.objects.create()
    assert o1.access_token != o2.access_token


# --- can_access_order tests ---


@pytest.mark.django_db
def test_staff_always_has_access(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create()

    factory = RequestFactory()
    request = factory.get("/")
    request.user = waiter
    request.session = {}  # type: ignore[assignment]

    assert can_access_order(request, order) is True


@pytest.mark.django_db
def test_owner_has_access(django_user_model: Any) -> None:
    visitor = django_user_model.objects.create_user(
        email="v@test.com", username="v", password="testpass123", role="visitor"
    )
    order = Order.objects.create(visitor=visitor)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = visitor
    request.session = {}  # type: ignore[assignment]

    assert can_access_order(request, order) is True


@pytest.mark.django_db
def test_other_visitor_denied(django_user_model: Any) -> None:
    v1 = django_user_model.objects.create_user(
        email="v1@test.com", username="v1", password="testpass123", role="visitor"
    )
    v2 = django_user_model.objects.create_user(
        email="v2@test.com", username="v2", password="testpass123", role="visitor"
    )
    order = Order.objects.create(visitor=v1)

    factory = RequestFactory()
    request = factory.get("/")
    request.user = v2
    request.session = {}  # type: ignore[assignment]

    assert can_access_order(request, order) is False


@pytest.mark.django_db
def test_session_token_grants_access(django_user_model: Any) -> None:
    from django.contrib.auth.models import AnonymousUser

    order = Order.objects.create()

    factory = RequestFactory()
    request = factory.get("/")
    request.user = AnonymousUser()
    request.session = {"my_orders": {str(order.id): str(order.access_token)}}  # type: ignore[assignment]

    assert can_access_order(request, order) is True


@pytest.mark.django_db
def test_url_token_grants_access(django_user_model: Any) -> None:
    from django.contrib.auth.models import AnonymousUser

    order = Order.objects.create()

    factory = RequestFactory()
    request = factory.get(f"/?token={order.access_token}")
    request.user = AnonymousUser()
    request.session = {}  # type: ignore[assignment]

    assert can_access_order(request, order) is True


@pytest.mark.django_db
def test_wrong_token_denied(django_user_model: Any) -> None:
    from django.contrib.auth.models import AnonymousUser

    order = Order.objects.create()

    factory = RequestFactory()
    request = factory.get(f"/?token={uuid.uuid4()}")
    request.user = AnonymousUser()
    request.session = {}  # type: ignore[assignment]

    assert can_access_order(request, order) is False


# --- View integration tests ---


@pytest.mark.django_db
def test_order_detail_anonymous_without_token_403(client: Client) -> None:
    order = Order.objects.create()
    response = client.get(f"/order/{order.id}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_order_detail_with_url_token_200(client: Client) -> None:
    order = Order.objects.create()
    response = client.get(f"/order/{order.id}/?token={order.access_token}")
    assert response.status_code == 200


@pytest.mark.django_db
def test_order_detail_staff_200(client: Client, django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create()
    client.force_login(waiter)
    response = client.get(f"/order/{order.id}/")
    assert response.status_code == 200
