"""Tests for model translation setup (Task 6.1) and admin (Task 6.2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import translation

from menu.models import Category, Dish, Tag


# --- Task 6.1: translation fields exist ---


def test_dish_has_translation_fields() -> None:
    assert hasattr(Dish, "title_uk")
    assert hasattr(Dish, "title_en")
    assert hasattr(Dish, "title_cnr")
    assert hasattr(Dish, "title_de")
    assert hasattr(Dish, "description_uk")
    assert hasattr(Dish, "description_en")


def test_category_has_translation_fields() -> None:
    assert hasattr(Category, "title_uk")
    assert hasattr(Category, "title_en")
    assert hasattr(Category, "description_uk")
    assert hasattr(Category, "description_en")


def test_tag_has_translation_fields() -> None:
    assert hasattr(Tag, "title_uk")
    assert hasattr(Tag, "title_en")
    assert hasattr(Tag, "description_uk")
    assert hasattr(Tag, "description_en")


@pytest.mark.django_db
def test_dish_title_in_different_languages() -> None:
    cat = Category.objects.create(
        title_uk="Перші страви",
        title_en="First courses",
        description_uk="",
        description_en="",
        number_in_line=1,
    )
    dish = Dish.objects.create(
        title_uk="Борщ",
        title_en="Borscht",
        description_uk="Традиційний суп",
        description_en="Traditional soup",
        price=Decimal("8.00"),
        weight=400,
        calorie=320,
        category=cat,
    )

    with translation.override("uk"):
        assert dish.title == "Борщ"

    with translation.override("en"):
        assert dish.title == "Borscht"


@pytest.mark.django_db
def test_translation_fallback_to_uk() -> None:
    cat = Category.objects.create(
        title_uk="Перші страви",
        title_en="",
        description_uk="Супи",
        description_en="",
        number_in_line=1,
    )
    with translation.override("en"):
        cat.refresh_from_db()
        assert cat.title == "Перші страви"


# --- Task 6.2: admin with translations ---


@pytest.mark.django_db
def test_admin_dish_list_accessible(client: Client, django_user_model: Any) -> None:
    superuser = django_user_model.objects.create_superuser(
        email="admin@test.com", password="testpass123", username="admin"
    )
    client.force_login(superuser)
    response = client.get("/admin/menu/dish/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_category_list_accessible(client: Client, django_user_model: Any) -> None:
    superuser = django_user_model.objects.create_superuser(
        email="admin@test.com", password="testpass123", username="admin"
    )
    client.force_login(superuser)
    response = client.get("/admin/menu/category/")
    assert response.status_code == 200
