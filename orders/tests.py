import io
from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from django.utils import timezone
from django.db.models import ProtectedError
from django.test import Client
from PIL import Image

from menu.models import Category, Dish
from orders.cart import add_to_cart, cart_item_count, get_cart, remove_from_cart
from orders.models import Order, OrderItem
from orders.services import confirm_cash_payment, confirm_online_payment_stub
from orders.tasks import escalate_unpaid_orders


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
def test_submit_order_creates_order_and_clears_cart(client: Client) -> None:
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
def test_submit_excludes_out_of_stock_dishes(client: Client) -> None:
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
def test_cart_view_returns_200(client: Client) -> None:
    response = client.get("/order/cart/")
    assert response.status_code == 200


# --- QR tests ---


@pytest.mark.django_db
def test_order_qr_returns_png(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


@pytest.mark.django_db
def test_order_qr_not_available_for_approved(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.APPROVED)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_order_qr_is_valid_png(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    img = Image.open(io.BytesIO(response.content))
    assert img.format == "PNG"


# --- Waiter flow tests ---


@pytest.mark.django_db
def test_waiter_order_list_requires_login(client: Client) -> None:
    response = client.get("/waiter/orders/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_waiter_order_list_forbidden_for_visitor(
    client: Client,
    django_user_model: Any,
) -> None:
    user = django_user_model.objects.create_user(
        email="v@test.com", username="visitor", password="testpass123", role="visitor"
    )
    client.force_login(user)
    response = client.get("/waiter/orders/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_waiter_order_list_accessible_for_waiter(
    client: Client,
    django_user_model: Any,
) -> None:
    user = django_user_model.objects.create_user(
        email="w@test.com", username="waiter1", password="testpass123", role="waiter"
    )
    client.force_login(user)
    response = client.get("/waiter/orders/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_approve_order_creates_kitchen_tickets(
    client: Client,
    django_user_model: Any,
) -> None:
    from kitchen.models import KitchenTicket

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D",
        description="",
        price=Decimal("5.00"),
        weight=100,
        calorie=100,
        category=cat,
    )
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    OrderItem.objects.create(order=order, dish=dish, quantity=2)

    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="waiter1", password="testpass123", role="waiter"
    )
    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/approve/")

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED
    assert order.waiter == waiter
    assert KitchenTicket.objects.filter(order_item__order=order).count() == 1


@pytest.mark.django_db
def test_approve_rejects_non_submitted_order(
    client: Client,
    django_user_model: Any,
) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="waiter1", password="testpass123", role="waiter"
    )
    client.force_login(waiter)
    client.post(f"/waiter/order/{order.id}/approve/")
    order.refresh_from_db()
    assert order.status == Order.Status.DRAFT


@pytest.mark.django_db
def test_kitchen_role_cannot_approve(
    client: Client,
    django_user_model: Any,
) -> None:
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    user = django_user_model.objects.create_user(
        email="k@test.com", username="cook", password="testpass123", role="kitchen"
    )
    client.force_login(user)
    response = client.post(f"/waiter/order/{order.id}/approve/")
    assert response.status_code == 403


# --- Waiter dashboard tests ---


@pytest.mark.django_db
def test_waiter_dashboard_shows_only_own_orders(
    client: Client, django_user_model: Any
) -> None:
    w1 = django_user_model.objects.create_user(
        email="w1@test.com", username="w1", password="testpass123", role="waiter"
    )
    w2 = django_user_model.objects.create_user(
        email="w2@test.com", username="w2", password="testpass123", role="waiter"
    )
    Order.objects.create(waiter=w1, status=Order.Status.APPROVED)
    Order.objects.create(waiter=w2, status=Order.Status.APPROVED)

    client.force_login(w1)
    response = client.get("/waiter/dashboard/")

    assert response.status_code == 200
    orders_ctx = response.context["orders"]
    assert orders_ctx.count() == 1
    assert orders_ctx.first().waiter == w1


@pytest.mark.django_db
def test_mark_delivered_changes_status(client: Client, django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.READY)

    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/delivered/")

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None


@pytest.mark.django_db
def test_cannot_mark_delivered_if_not_ready(
    client: Client, django_user_model: Any
) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.APPROVED)

    client.force_login(waiter)
    client.post(f"/waiter/order/{order.id}/delivered/")

    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED


@pytest.mark.django_db
def test_waiter_cannot_deliver_others_order(
    client: Client, django_user_model: Any
) -> None:
    w1 = django_user_model.objects.create_user(
        email="w1@test.com", username="w1", password="testpass123", role="waiter"
    )
    w2 = django_user_model.objects.create_user(
        email="w2@test.com", username="w2", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=w2, status=Order.Status.READY)

    client.force_login(w1)
    response = client.post(f"/waiter/order/{order.id}/delivered/")
    assert response.status_code == 404


# --- Payment tests ---


def test_payment_method_choices() -> None:
    methods = {m.value for m in Order.PaymentMethod}
    assert methods == {"cash", "online", "not_set"}


@pytest.mark.django_db
def test_confirm_cash_payment_success(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    result = confirm_cash_payment(order, waiter=waiter)

    assert result.payment_status == Order.PaymentStatus.PAID
    assert result.payment_method == Order.PaymentMethod.CASH
    assert result.payment_confirmed_at is not None
    assert result.payment_escalation_level == 0


@pytest.mark.django_db
def test_confirm_payment_already_paid(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, payment_status=Order.PaymentStatus.PAID)
    with pytest.raises(ValueError, match="already paid"):
        confirm_cash_payment(order, waiter=waiter)


@pytest.mark.django_db
def test_confirm_payment_wrong_waiter(django_user_model: Any) -> None:
    w1 = django_user_model.objects.create_user(
        email="w1@test.com", username="w1", password="testpass123", role="waiter"
    )
    w2 = django_user_model.objects.create_user(
        email="w2@test.com", username="w2", password="testpass123", role="waiter"
    )
    order = Order.objects.create(waiter=w1, payment_status=Order.PaymentStatus.UNPAID)
    with pytest.raises(ValueError, match="assigned waiter"):
        confirm_cash_payment(order, waiter=w2)


@pytest.mark.django_db
def test_confirm_payment_view(client: Client, django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    client.force_login(waiter)
    response = client.post(f"/waiter/order/{order.id}/confirm-payment/")
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID


# --- Online payment tests ---


@pytest.mark.django_db
def test_online_payment_stub_marks_paid() -> None:
    order = Order.objects.create(payment_status=Order.PaymentStatus.UNPAID)
    result = confirm_online_payment_stub(order)

    assert result.payment_status == Order.PaymentStatus.PAID
    assert result.payment_method == Order.PaymentMethod.ONLINE
    assert result.payment_confirmed_at is not None


@pytest.mark.django_db
def test_online_payment_page_get(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/pay/")
    assert response.status_code == 200
    assert "Демо-режим" in response.content.decode()


@pytest.mark.django_db
def test_online_payment_page_post(client: Client) -> None:
    order = Order.objects.create(status=Order.Status.APPROVED)
    response = client.post(f"/order/{order.id}/pay/")
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
    assert order.payment_method == Order.PaymentMethod.ONLINE


# --- Payment escalation tests ---


def test_escalate_task_is_callable() -> None:
    assert callable(escalate_unpaid_orders)


@pytest.mark.django_db
def test_escalate_to_senior_waiter(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    # 12 min ago: past PAY_TIMEOUT (10) but before 2*PAY_TIMEOUT (20)
    old_time = timezone.now() - timedelta(minutes=12)
    Order.objects.filter(pk=order.pk).update(delivered_at=old_time)

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.PAY_TIMEOUT = 10
        result = escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 1
    assert result["senior_waiter"] >= 1


@pytest.mark.django_db
def test_escalate_to_manager(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    # 25 min ago: past 2*PAY_TIMEOUT (20)
    old_time = timezone.now() - timedelta(minutes=25)
    Order.objects.filter(pk=order.pk).update(delivered_at=old_time)

    with patch("orders.tasks.settings") as mock_settings:
        mock_settings.PAY_TIMEOUT = 10
        result = escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 2
    assert result["manager"] >= 1


@pytest.mark.django_db
def test_paid_orders_not_escalated(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.PAID,
    )
    old_time = timezone.now() - timedelta(minutes=30)
    Order.objects.filter(pk=order.pk).update(delivered_at=old_time)

    escalate_unpaid_orders()

    order.refresh_from_db()
    assert order.payment_escalation_level == 0


@pytest.mark.django_db
def test_not_delivered_orders_not_escalated(django_user_model: Any) -> None:
    waiter = django_user_model.objects.create_user(
        email="w@test.com", username="w", password="testpass123", role="waiter"
    )
    Order.objects.create(
        waiter=waiter,
        status=Order.Status.READY,
        payment_status=Order.PaymentStatus.UNPAID,
    )

    escalate_unpaid_orders()

    order = Order.objects.first()
    assert order is not None
    assert order.payment_escalation_level == 0
