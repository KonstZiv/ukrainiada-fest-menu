import io
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from menu.models import Category, Dish
from orders.cart import add_to_cart, cart_item_count, get_cart, remove_from_cart
from orders.models import Order, OrderItem


class _FakeSession(dict):  # type: ignore[type-arg]
    """Dict-like session mock that supports .modified attribute."""

    modified: bool = False

    def pop(self, key: str, *args: object) -> object:
        return super().pop(key, *args)


def test_order_status_flow_values() -> None:
    statuses = {s.value for s in Order.Status}
    expected = {"draft", "submitted", "approved", "in_progress", "ready", "delivered"}
    assert statuses == expected


def test_order_default_status_and_payment() -> None:
    order = Order()
    assert order.status == Order.Status.DRAFT
    assert order.payment_status == Order.PaymentStatus.UNPAID


@pytest.mark.django_db
def test_order_total_price() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    dish2 = Dish.objects.create(
        title="D2",
        description="",
        price=Decimal("3.50"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish1, quantity=2)
    OrderItem.objects.create(order=order, dish=dish2, quantity=1)
    assert order.total_price == Decimal("13.50")


@pytest.mark.django_db
def test_order_item_unique_per_dish() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(IntegrityError):
        OrderItem.objects.create(order=order, dish=dish, quantity=2)


@pytest.mark.django_db
def test_cannot_delete_dish_with_active_order() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    OrderItem.objects.create(order=order, dish=dish, quantity=1)
    with pytest.raises(ProtectedError):
        dish.delete()


@pytest.mark.django_db
def test_order_str() -> None:
    order = Order.objects.create()
    assert f"Order #{order.pk}" in str(order)
    assert "Чернетка" in str(order)


@pytest.mark.django_db
def test_order_item_subtotal() -> None:
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("7.50"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create()
    item = OrderItem.objects.create(order=order, dish=dish, quantity=3)
    assert item.subtotal == Decimal("22.50")


# --- Cart tests ---


def test_add_to_cart_new_item() -> None:
    request = MagicMock()
    request.session = _FakeSession()
    add_to_cart(request, dish_id=1, quantity=2)
    cart = get_cart(request)
    assert len(cart) == 1
    assert cart[0] == {"dish_id": 1, "quantity": 2}


def test_add_same_dish_increments_quantity() -> None:
    request = MagicMock()
    request.session = _FakeSession()
    add_to_cart(request, dish_id=5, quantity=1)
    add_to_cart(request, dish_id=5, quantity=3)
    cart = get_cart(request)
    assert cart[0]["quantity"] == 4


def test_remove_from_cart() -> None:
    request = MagicMock()
    request.session = _FakeSession()
    add_to_cart(request, dish_id=1)
    add_to_cart(request, dish_id=2)
    remove_from_cart(request, dish_id=1)
    cart = get_cart(request)
    assert len(cart) == 1
    assert cart[0]["dish_id"] == 2


def test_cart_item_count() -> None:
    request = MagicMock()
    request.session = _FakeSession()
    add_to_cart(request, dish_id=1, quantity=3)
    add_to_cart(request, dish_id=2, quantity=2)
    assert cart_item_count(request) == 5


@pytest.mark.django_db
def test_submit_order_creates_order_and_clears_cart(client) -> None:  # type: ignore[no-untyped-def]
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
        availability="available",
    )
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 2}]
    session.save()

    response = client.post("/order/submit/")
    assert response.status_code == 302
    assert Order.objects.filter(status="draft").count() == 1
    assert client.session.get("festival_cart") is None


@pytest.mark.django_db
def test_submit_excludes_out_of_stock_dishes(client) -> None:  # type: ignore[no-untyped-def]
    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    Dish.objects.create(
        title="Out",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
        availability="out",
    )
    session = client.session
    session["festival_cart"] = [{"dish_id": 1, "quantity": 1}]
    session.save()

    client.post("/order/submit/")
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_cart_view_returns_200(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/order/cart/")
    assert response.status_code == 200


# --- QR tests ---


@pytest.mark.django_db
def test_order_qr_returns_png(client) -> None:  # type: ignore[no-untyped-def]
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


@pytest.mark.django_db
def test_order_qr_not_available_for_approved(client) -> None:  # type: ignore[no-untyped-def]
    order = Order.objects.create(status=Order.Status.APPROVED)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_order_qr_is_valid_png(client) -> None:  # type: ignore[no-untyped-def]
    from PIL import Image

    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    img = Image.open(io.BytesIO(response.content))
    assert img.format == "PNG"
