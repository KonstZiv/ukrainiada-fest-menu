"""Tests for Telegram bot webhook and verification logic."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client, override_settings

from telegram_bot.verification import generate_verification_code, verify_telegram
from user.models import CommunicationChannel, User


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------

_WEBHOOK_SECRET = "test-webhook-secret-42"


@pytest.mark.django_db
@override_settings(TG_TOKEN="fake:token", TG_WEBHOOK_SECRET=_WEBHOOK_SECRET)
def test_webhook_wrong_secret_returns_403(client: Client) -> None:
    response = client.post(
        "/bot/webhook/wrong-secret/",
        data=b"{}",
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(TG_TOKEN="fake:token", TG_WEBHOOK_SECRET=_WEBHOOK_SECRET)
def test_webhook_invalid_json_returns_400(client: Client) -> None:
    response = client.post(
        f"/bot/webhook/{_WEBHOOK_SECRET}/",
        data=b"not-json-at-all",
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Verification code tests
# ---------------------------------------------------------------------------


@pytest.fixture
def user(django_user_model: Any) -> User:
    return django_user_model.objects.create_user(
        email="tguser@test.com",
        username="tguser",
        password="testpass123",
        role="visitor",
    )


@pytest.mark.django_db
def test_verification_code_generate_and_verify(user: User) -> None:
    """Generate a verification code, then verify it — CommunicationChannel is created."""
    code = generate_verification_code(user.pk)
    assert isinstance(code, str)
    assert len(code) > 0

    chat_id = 123456789
    result = verify_telegram(chat_id, code)
    assert result is True

    channel = CommunicationChannel.objects.get(
        user=user,
        channel_type=CommunicationChannel.ChannelType.TELEGRAM,
    )
    assert channel.address == str(chat_id)
    assert channel.is_verified is True


@pytest.mark.django_db
def test_verification_code_cannot_be_reused(user: User) -> None:
    """After successful verification, the same code cannot be used again."""
    code = generate_verification_code(user.pk)
    verify_telegram(123456789, code)

    # Second attempt with the same code should fail.
    result = verify_telegram(999999999, code)
    assert result is False


@pytest.mark.django_db
def test_verification_with_invalid_code() -> None:
    """A completely fabricated code should be rejected."""
    result = verify_telegram(123456789, "nonexistent-code")
    assert result is False
