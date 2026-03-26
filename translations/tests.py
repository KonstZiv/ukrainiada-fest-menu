"""Tests for translation review and approval workflow."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from menu.models import Category
from translations.models import TranslationApproval
from user.models import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def corrector(django_user_model: Any) -> User:
    """User with corrector role (allowed to review translations)."""
    return django_user_model.objects.create_user(
        email="corrector@test.com",
        username="corrector",
        password="testpass123",
        role="corrector",
    )


@pytest.fixture
def visitor(django_user_model: Any) -> User:
    """User with visitor role (no review access)."""
    return django_user_model.objects.create_user(
        email="visitor@test.com",
        username="visitor",
        password="testpass123",
        role="visitor",
    )


@pytest.fixture
def pending_approval() -> TranslationApproval:
    """Create a Category with a pending translation approval."""
    cat = Category.objects.create(
        title="Test Cat",
        description="desc",
        number_in_line=1,
    )
    ct = ContentType.objects.get_for_model(Category)
    return TranslationApproval.objects.create(
        content_type=ct,
        object_id=cat.pk,
        language="en",
        status=TranslationApproval.Status.PENDING,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_page_requires_auth(client: Client) -> None:
    response = client.get("/translations/review/")
    assert response.status_code == 302
    assert (
        "/accounts/login/" in response["Location"] or "/login/" in response["Location"]
    )


@pytest.mark.django_db
def test_review_page_requires_role(client: Client, visitor: User) -> None:
    client.force_login(visitor)
    response = client.get("/translations/review/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_approve_single_changes_status(
    client: Client,
    corrector: User,
    pending_approval: TranslationApproval,
) -> None:
    client.force_login(corrector)
    response = client.post(f"/translations/approve/{pending_approval.pk}/")
    assert response.status_code == 302
    pending_approval.refresh_from_db()
    assert pending_approval.status == TranslationApproval.Status.APPROVED
    assert pending_approval.approved_by == corrector
    assert pending_approval.approved_at is not None
