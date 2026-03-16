"""Tests for language switcher (Task 6.3) and allergens (Task 6.4)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from django.utils import translation

from menu.models import Allergen, Category, Dish


# --- Task 6.3: language switcher ---


@pytest.mark.django_db
def test_set_language_endpoint(client: Client) -> None:
    response = client.post(
        "/i18n/setlang/",
        {"language": "en", "next": "/menu/"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_menu_respects_language_override() -> None:
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
        description_uk="Суп",
        description_en="Soup",
        price=Decimal("8.00"),
        weight=400,
        calorie=320,
        category=cat,
    )
    with translation.override("en"):
        dish.refresh_from_db()
        assert dish.title == "Borscht"
        cat.refresh_from_db()
        assert cat.title == "First courses"

    with translation.override("uk"):
        dish.refresh_from_db()
        assert dish.title == "Борщ"


@pytest.mark.django_db
def test_navbar_has_language_selector(client: Client) -> None:
    response = client.get("/menu/")
    content = response.content.decode()
    assert "set_language" in content or "setlang" in content


# --- Task 6.4: allergens ---


def test_allergen_model_has_icon_field() -> None:
    allergen = Allergen()
    allergen.icon = "🌾"
    assert allergen.icon == "🌾"


def test_allergen_has_translation_fields() -> None:
    assert hasattr(Allergen, "title_uk")
    assert hasattr(Allergen, "title_en")


@pytest.mark.django_db
def test_allergen_title_translated() -> None:
    allergen = Allergen.objects.create(title_uk="Глютен", title_en="Gluten", icon="🌾")
    with translation.override("en"):
        allergen.refresh_from_db()
        assert allergen.title == "Gluten"

    with translation.override("uk"):
        allergen.refresh_from_db()
        assert allergen.title == "Глютен"


@pytest.mark.django_db
def test_dish_allergens_m2m() -> None:
    cat = Category.objects.create(
        title_uk="Cat",
        description_uk="",
        number_in_line=1,
    )
    dish = Dish.objects.create(
        title_uk="D",
        description_uk="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    allergen = Allergen.objects.create(title_uk="Лактоза", icon="🥛")
    dish.allergens.add(allergen)

    assert dish.allergens.count() == 1
    assert dish.allergens.first() == allergen


@pytest.mark.django_db
def test_dish_card_shows_allergens(client: Client) -> None:
    cat = Category.objects.create(
        title_uk="Cat",
        description_uk="",
        number_in_line=1,
    )
    dish = Dish.objects.create(
        title_uk="Борщ",
        description_uk="Суп",
        price=Decimal("8.00"),
        weight=400,
        calorie=320,
        category=cat,
    )
    allergen = Allergen.objects.create(title_uk="Глютен", title_en="Gluten", icon="🌾")
    dish.allergens.add(allergen)

    response = client.get("/menu/dishes/")
    content = response.content.decode()
    assert "Глютен" in content


@pytest.mark.django_db
def test_admin_allergen_accessible(client: Client, django_user_model: Any) -> None:
    superuser = django_user_model.objects.create_superuser(
        email="admin@test.com", password="testpass123", username="admin"
    )
    client.force_login(superuser)
    response = client.get("/admin/menu/allergen/")
    assert response.status_code == 200
