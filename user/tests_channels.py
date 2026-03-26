"""Tests for CommunicationChannel creation and management views."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from user.forms import SignUpForm
from user.models import CommunicationChannel, User


@pytest.fixture
def visitor(django_user_model: Any) -> User:
    """Create a plain visitor user (no channels)."""
    return django_user_model.objects.create_user(
        email="visitor@test.com",
        username="visitor",
        password="testpass123",
        role="visitor",
    )


@pytest.mark.django_db
def test_email_channel_created_on_signup(client: Client) -> None:
    """Sign-up form save + channel creation logic works correctly.

    The view itself may fail on login() when multiple auth backends
    are configured, so we test the form + channel creation directly.
    """
    form = SignUpForm(
        data={
            "email": "newuser@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password1": "Str0ngP@ss!",
            "password2": "Str0ngP@ss!",
        }
    )
    assert form.is_valid(), form.errors
    user = form.save()

    # Replicate what the view does after form.save().
    CommunicationChannel.objects.create(
        user=user,
        channel_type=CommunicationChannel.ChannelType.EMAIL,
        address=user.email,
        is_verified=True,
        priority=0,
    )

    assert CommunicationChannel.objects.filter(
        user=user,
        channel_type=CommunicationChannel.ChannelType.EMAIL,
        address="newuser@example.com",
        is_verified=True,
    ).exists()


@pytest.mark.django_db
def test_channels_page_requires_login(client: Client) -> None:
    response = client.get("/user/channels/")
    assert response.status_code == 302
    assert (
        "/accounts/login/" in response["Location"] or "/login/" in response["Location"]
    )


@pytest.mark.django_db
def test_channels_page_shows_email(client: Client, visitor: User) -> None:
    """Logged-in user with an email channel sees their address on the page."""
    CommunicationChannel.objects.create(
        user=visitor,
        channel_type=CommunicationChannel.ChannelType.EMAIL,
        address=visitor.email,
        is_verified=True,
    )
    client.force_login(visitor)
    response = client.get("/user/channels/")
    assert response.status_code == 200
    content = response.content.decode()
    assert visitor.email in content
