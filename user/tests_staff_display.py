"""Tests for staff display fields and staff_label property (Task 8.1)."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from user.models import User


def test_staff_label_full_display() -> None:
    user = User(display_title="Повариха", public_name="Валентина", role="kitchen")
    assert user.staff_label == "Повариха Валентина"


def test_staff_label_fallback_role_display() -> None:
    user = User(role="kitchen", first_name="Дмитро", email="d@test.com")
    assert user.staff_label == "Виробництво Дмитро"


def test_staff_label_fallback_email_prefix() -> None:
    user = User(role="waiter", email="john@fest.ua")
    assert user.staff_label == "Офіціант john"


def test_staff_label_empty_fields() -> None:
    user = User(role="visitor", email="guest@gmail.com")
    assert user.staff_label == "Відвідувач guest"


def test_staff_label_public_name_over_first_name() -> None:
    user = User(
        role="kitchen",
        first_name="Олена",
        public_name="Леночка",
        email="o@test.com",
    )
    assert "Леночка" in user.staff_label
    assert "Олена" not in user.staff_label


def test_staff_label_display_title_over_role() -> None:
    user = User(
        role="kitchen",
        display_title="Чарівниця борщу",
        public_name="Катя",
        email="k@test.com",
    )
    assert user.staff_label == "Чарівниця борщу Катя"


@pytest.mark.django_db
def test_staff_display_fields_saved(django_user_model: Any) -> None:
    user = django_user_model.objects.create_user(
        email="k@test.com",
        username="ktest",
        password="testpass123",
        role="kitchen",
        display_title="Бармен",
        public_name="Наталія",
    )
    user.refresh_from_db()
    assert user.display_title == "Бармен"
    assert user.public_name == "Наталія"


@pytest.mark.django_db
def test_admin_user_list_accessible(client: Client, django_user_model: Any) -> None:
    superuser = django_user_model.objects.create_superuser(
        email="admin@test.com", password="testpass123", username="admin"
    )
    client.force_login(superuser)
    response = client.get("/admin/user/user/")
    assert response.status_code == 200
