# Task 1.3 — Visitor flow: меню і кошик (детально)

## Концепція

Відвідувач НЕ зобов'язаний мати акаунт — кошик зберігається в Django session.
При submit — `Order` зі статусом `DRAFT` і `visitor=None` (або з акаунтом якщо залогінений).

## URL структура (orders/urls.py)

```python
from django.urls import path
from orders import views

app_name = "orders"

urlpatterns = [
    path("menu/", views.visitor_menu, name="visitor_menu"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:dish_id>/", views.cart_remove, name="cart_remove"),
    path("submit/", views.order_submit, name="order_submit"),
    path("<int:order_id>/qr/", views.order_qr, name="order_qr"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
]
```

## orders/cart.py

```python
from __future__ import annotations

from typing import TypedDict
from django.http import HttpRequest

CART_SESSION_KEY = "festival_cart"


class CartItem(TypedDict):
    dish_id: int
    quantity: int


def get_cart(request: HttpRequest) -> list[CartItem]:
    return list(request.session.get(CART_SESSION_KEY, []))


def add_to_cart(request: HttpRequest, dish_id: int, quantity: int = 1) -> None:
    cart = get_cart(request)
    for item in cart:
        if item["dish_id"] == dish_id:
            item["quantity"] += quantity
            request.session[CART_SESSION_KEY] = cart
            request.session.modified = True
            return
    cart.append({"dish_id": dish_id, "quantity": quantity})
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def remove_from_cart(request: HttpRequest, dish_id: int) -> None:
    cart = [item for item in get_cart(request) if item["dish_id"] != dish_id]
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def clear_cart(request: HttpRequest) -> None:
    request.session.pop(CART_SESSION_KEY, None)
    request.session.modified = True


def cart_item_count(request: HttpRequest) -> int:
    return sum(item["quantity"] for item in get_cart(request))
```

## orders/services.py (частина — submit)

```python
from django.http import HttpRequest
from django.db import transaction
from orders.models import Order, OrderItem
from orders.cart import get_cart, clear_cart
from menu.models import Dish


def submit_order_from_cart(request: HttpRequest) -> Order | None:
    """Створити Order зі статусом DRAFT з вмісту кошика.

    Повертає None якщо кошик порожній або є недоступні страви.
    """
    cart = get_cart(request)
    if not cart:
        return None

    dish_ids = [item["dish_id"] for item in cart]
    dishes = {
        d.id: d
        for d in Dish.objects.filter(id__in=dish_ids).exclude(availability="out")
    }

    # Фільтруємо позиції де страва недоступна
    valid_items = [item for item in cart if item["dish_id"] in dishes]
    if not valid_items:
        return None

    with transaction.atomic():
        order = Order.objects.create(
            visitor=request.user if request.user.is_authenticated else None,
        )
        OrderItem.objects.bulk_create([
            OrderItem(order=order, dish=dishes[item["dish_id"]], quantity=item["quantity"])
            for item in valid_items
        ])

    clear_cart(request)
    return order
```

## orders/views.py (visitor частина)

```python
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from menu.models import Dish, Category
from orders.cart import add_to_cart, remove_from_cart, get_cart
from orders.models import Order
from orders.services import submit_order_from_cart


def visitor_menu(request: HttpRequest) -> HttpResponse:
    """Меню для відвідувача — тільки available та low страви."""
    categories = (
        Category.objects.prefetch_related(
            "dishes"
        ).exclude(dishes__availability="out")
    )
    return render(request, "orders/visitor_menu.html", {"categories": categories})


def cart_add(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        dish_id = int(request.POST.get("dish_id", 0))
        quantity = int(request.POST.get("quantity", 1))
        if dish_id:
            add_to_cart(request, dish_id, quantity)
    return redirect("orders:cart")


def cart_remove(request: HttpRequest, dish_id: int) -> HttpResponse:
    remove_from_cart(request, dish_id)
    return redirect("orders:cart")


def cart_view(request: HttpRequest) -> HttpResponse:
    cart = get_cart(request)
    dish_ids = [item["dish_id"] for item in cart]
    dishes = {d.id: d for d in Dish.objects.filter(id__in=dish_ids)}
    enriched = [
        {"dish": dishes[item["dish_id"]], "quantity": item["quantity"]}
        for item in cart
        if item["dish_id"] in dishes
    ]
    total = sum(e["dish"].price * e["quantity"] for e in enriched)
    return render(request, "orders/cart.html", {"items": enriched, "total": total})


def order_submit(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        order = submit_order_from_cart(request)
        if order:
            return redirect("orders:order_detail", order_id=order.id)
        messages.error(request, "Кошик порожній або страви недоступні.")
    return redirect("orders:cart")


def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/order_detail.html", {"order": order})
```

## Тести

```python
# orders/tests/test_cart.py
import pytest


@pytest.mark.tier1
def test_add_to_cart_new_item():
    from orders.cart import add_to_cart, get_cart
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    add_to_cart(request, dish_id=1, quantity=2)
    cart = get_cart(request)
    assert len(cart) == 1
    assert cart[0] == {"dish_id": 1, "quantity": 2}


@pytest.mark.tier1
def test_add_same_dish_increments_quantity():
    from orders.cart import add_to_cart, get_cart
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    add_to_cart(request, dish_id=5, quantity=1)
    add_to_cart(request, dish_id=5, quantity=3)
    cart = get_cart(request)
    assert cart[0]["quantity"] == 4


@pytest.mark.tier1
def test_remove_from_cart():
    from orders.cart import add_to_cart, remove_from_cart, get_cart
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    add_to_cart(request, dish_id=1)
    add_to_cart(request, dish_id=2)
    remove_from_cart(request, dish_id=1)
    cart = get_cart(request)
    assert len(cart) == 1
    assert cart[0]["dish_id"] == 2


@pytest.mark.tier1
def test_cart_item_count():
    from orders.cart import add_to_cart, cart_item_count
    from unittest.mock import MagicMock
    request = MagicMock()
    request.session = {}
    add_to_cart(request, dish_id=1, quantity=3)
    add_to_cart(request, dish_id=2, quantity=2)
    assert cart_item_count(request) == 5


@pytest.mark.tier2
@pytest.mark.django_db
def test_submit_order_creates_order_and_clears_cart(client):
    from menu.models import Category, Dish
    from orders.models import Order
    from decimal import Decimal

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat, availability="available"
    )
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 2}]
    session.save()

    response = client.post("/order/submit/")
    assert response.status_code == 302
    assert Order.objects.filter(status="draft").count() == 1
    # Кошик очищено
    assert client.session.get("festival_cart", []) == []


@pytest.mark.tier2
@pytest.mark.django_db
def test_submit_excludes_out_of_stock_dishes(client):
    from menu.models import Category, Dish
    from orders.models import Order
    from decimal import Decimal

    cat = Category.objects.create(title="Cat", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="Out", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat, availability="out"
    )
    session = client.session
    session["festival_cart"] = [{"dish_id": dish.id, "quantity": 1}]
    session.save()

    client.post("/order/submit/")
    assert Order.objects.count() == 0
```

## Acceptance criteria

- [ ] `orders/cart.py` — 5 функцій з type annotations
- [ ] `submit_order_from_cart` — атомарна, фільтрує `out` страви, очищає кошик
- [ ] Visitor menu — не показує `out` страви, `low` — з попередженням
- [ ] `uv run pytest -m "tier1 or tier2" orders/tests/test_cart.py` — зелені
