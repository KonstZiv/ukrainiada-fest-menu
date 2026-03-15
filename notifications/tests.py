from typing import Any
from unittest.mock import MagicMock

import pytest
from django.test import Client

from notifications.channels import (
    channels_for_user,
    kitchen_channel,
    manager_channel,
    waiter_channel,
)
from user.models import User


def test_channel_names() -> None:
    assert kitchen_channel(1) == "kitchen-1"
    assert waiter_channel(42) == "waiter-42"
    assert manager_channel() == "manager"


def test_channels_for_visitor_returns_empty() -> None:
    user = MagicMock(spec=User)
    user.role = User.Role.VISITOR
    assert channels_for_user(user) == []


def test_channels_for_kitchen() -> None:
    user = MagicMock(spec=User)
    user.id = 5
    user.role = User.Role.KITCHEN
    assert channels_for_user(user) == ["kitchen-5"]


def test_channels_for_kitchen_supervisor() -> None:
    user = MagicMock(spec=User)
    user.id = 3
    user.role = User.Role.KITCHEN_SUPERVISOR
    assert channels_for_user(user) == ["kitchen-3"]


def test_channels_for_waiter() -> None:
    user = MagicMock(spec=User)
    user.id = 7
    user.role = User.Role.WAITER
    assert channels_for_user(user) == ["waiter-7"]


def test_channels_for_senior_waiter() -> None:
    user = MagicMock(spec=User)
    user.id = 9
    user.role = User.Role.SENIOR_WAITER
    assert channels_for_user(user) == ["waiter-9"]


def test_channels_for_manager() -> None:
    user = MagicMock(spec=User)
    user.role = User.Role.MANAGER
    assert channels_for_user(user) == ["manager"]


# --- SSE view tests ---


@pytest.mark.django_db
def test_sse_requires_auth(client: Client) -> None:
    response = client.get("/events/stream/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_visitor_gets_403(client: Client, django_user_model: Any) -> None:
    visitor = django_user_model.objects.create_user(
        email="v@test.com", username="visitor", password="testpass123", role="visitor"
    )
    client.force_login(visitor)
    response = client.get("/events/stream/")
    assert response.status_code == 403
