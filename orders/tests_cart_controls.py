"""Tests for cart controls UI: AJAX JSON responses and template rendering."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.test import Client

from menu.models import Category, Dish


@pytest.fixture
def category() -> Category:
    return Category.objects.create(title="TestCat", description="", number_in_line=1)


@pytest.fixture
def dish(category: Category) -> Dish:
    return Dish.objects.create(
        title="TestDish",
        description="A test dish",
        price=Decimal("10.00"),
        weight=200,
        calorie=300,
        category=category,
        availability="available",
    )


@pytest.fixture
def dish2(category: Category) -> Dish:
    return Dish.objects.create(
        title="TestDish2",
        description="Another dish",
        price=Decimal("5.50"),
        weight=150,
        calorie=200,
        category=category,
        availability="available",
    )


# --- AJAX cart_add ---


@pytest.mark.django_db
def test_cart_add_ajax_returns_json(client: Client, dish: Dish) -> None:
    """AJAX POST to cart_add returns JSON with dish_id, dish_qty, cart_count, cart_total."""
    response = client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["dish_id"] == dish.id
    assert data["dish_qty"] == 1
    assert data["cart_count"] == 1
    assert Decimal(data["cart_total"]) == Decimal("10.00")


@pytest.mark.django_db
def test_cart_add_ajax_increments_quantity(client: Client, dish: Dish) -> None:
    """Adding the same dish twice increments quantity."""
    client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    response = client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    data = json.loads(response.content)
    assert data["dish_qty"] == 2
    assert data["cart_count"] == 2
    assert Decimal(data["cart_total"]) == Decimal("20.00")


@pytest.mark.django_db
def test_cart_add_non_ajax_redirects(client: Client, dish: Dish) -> None:
    """Non-AJAX POST to cart_add returns redirect."""
    response = client.post("/order/cart/add/", {"dish_id": dish.id, "quantity": 1})
    assert response.status_code == 302


# --- AJAX cart_decrease ---


@pytest.mark.django_db
def test_cart_decrease_ajax_returns_json(client: Client, dish: Dish) -> None:
    """AJAX POST to cart_decrease returns JSON with updated quantity."""
    # Add 2, decrease 1 → qty should be 1
    client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 2},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    response = client.post(
        f"/order/cart/decrease/{dish.id}/",
        {},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["dish_id"] == dish.id
    assert data["dish_qty"] == 1
    assert data["cart_count"] == 1


@pytest.mark.django_db
def test_cart_decrease_to_zero_removes_item(client: Client, dish: Dish) -> None:
    """Decreasing qty to 0 removes the dish from cart."""
    client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    response = client.post(
        f"/order/cart/decrease/{dish.id}/",
        {},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    data = json.loads(response.content)
    assert data["dish_qty"] == 0
    assert data["cart_count"] == 0


@pytest.mark.django_db
def test_cart_total_with_multiple_dishes(
    client: Client, dish: Dish, dish2: Dish
) -> None:
    """Cart total reflects all dishes."""
    client.post(
        "/order/cart/add/",
        {"dish_id": dish.id, "quantity": 2},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    response = client.post(
        "/order/cart/add/",
        {"dish_id": dish2.id, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    data = json.loads(response.content)
    assert data["cart_count"] == 3
    assert Decimal(data["cart_total"]) == Decimal("25.50")


# --- Template rendering: cart controls classes ---


@pytest.mark.django_db
def test_category_list_shows_cart_controls_hidden_when_empty(
    client: Client, dish: Dish
) -> None:
    """Category list renders cart-minus with d-none when dish is not in cart."""
    response = client.get("/menu/categories/")
    content = response.content.decode()
    # The minus form for this dish should have d-none
    assert "cart-minus" in content
    assert "d-none" in content


@pytest.mark.django_db
def test_category_list_shows_cart_qty_when_in_cart(client: Client, dish: Dish) -> None:
    """Category list renders cart-minus with d-inline when dish is in cart."""
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 3}]
    session.save()

    response = client.get("/menu/categories/")
    content = response.content.decode()
    # Should have d-inline (visible) minus button and quantity "3"
    assert "cart-minus d-inline" in content or "cart-minus  d-inline" in content
    assert ">3<" in content


@pytest.mark.django_db
def test_tag_list_uses_cart_controls_component(client: Client, dish: Dish) -> None:
    """Tag list page renders _cart_controls.html (has data-dish-id and cart-minus)."""
    from menu.models import Tag

    tag = Tag.objects.create(title="TestTag", description="test")
    dish.tags.add(tag)

    response = client.get("/menu/tags/")
    content = response.content.decode()
    assert f'data-dish-id="{dish.id}"' in content
    assert "cart-minus" in content


@pytest.mark.django_db
def test_tag_list_shows_qty_when_in_cart(client: Client, dish: Dish) -> None:
    """Tag list shows quantity for dishes already in cart."""
    from menu.models import Tag

    tag = Tag.objects.create(title="TestTag", description="test")
    dish.tags.add(tag)

    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 2}]
    session.save()

    response = client.get("/menu/tags/")
    content = response.content.decode()
    assert "cart-minus d-inline" in content or "cart-minus  d-inline" in content
    assert ">2<" in content


@pytest.mark.django_db
def test_dish_list_uses_cart_controls_component(client: Client, dish: Dish) -> None:
    """Dish list page renders _cart_controls.html."""
    response = client.get("/menu/dishes/")
    content = response.content.decode()
    assert f'data-dish-id="{dish.id}"' in content
    assert "cart-minus" in content


@pytest.mark.django_db
def test_dish_list_shows_qty_when_in_cart(client: Client, dish: Dish) -> None:
    """Dish list shows quantity for dishes already in cart."""
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 5}]
    session.save()

    response = client.get("/menu/dishes/")
    content = response.content.decode()
    assert "cart-minus d-inline" in content or "cart-minus  d-inline" in content
    assert ">5<" in content


# --- Back button component ---


@pytest.mark.django_db
def test_back_button_rendered_hidden_by_default(client: Client, dish: Dish) -> None:
    """Back button is present in HTML but hidden (d-none) by default."""
    for url in [
        "/menu/",
        "/menu/categories/",
        "/menu/tags/",
        "/menu/dishes/",
        f"/menu/dishes/{dish.id}/",
    ]:
        response = client.get(url)
        content = response.content.decode()
        assert "back-btn" in content, f"back-btn missing on {url}"
        assert "back-btn d-none" in content, f"back-btn not hidden on {url}"


@pytest.mark.django_db
def test_back_button_on_cart_page(client: Client) -> None:
    """Cart page includes the back button component."""
    response = client.get("/order/cart/")
    content = response.content.decode()
    assert "back-btn" in content
