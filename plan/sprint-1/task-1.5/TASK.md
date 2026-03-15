# Task 1.5 — Waiter flow (детально)

## URL структура (waiter/urls.py — нова аплікація або в orders)

```python
# orders/urls.py — додати до існуючих
path("waiter/", include("orders.waiter_urls")),
```

```python
# orders/waiter_urls.py
from django.urls import path
from orders import waiter_views

app_name = "waiter"

urlpatterns = [
    path("orders/", waiter_views.waiter_order_list, name="order_list"),
    path("order/<int:order_id>/scan/", waiter_views.order_scan, name="order_scan"),
    path("order/<int:order_id>/approve/", waiter_views.order_approve, name="order_approve"),
]
```

## user/decorators.py

```python
from __future__ import annotations

from functools import wraps
from typing import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.contrib.auth.views import redirect_to_login


def role_required(*roles: str) -> Callable:  # type: ignore[type-arg]
    """Декоратор для обмеження доступу за роллю.

    Використання:
        @role_required("waiter", "senior_waiter", "manager")
        def my_view(request): ...
    """
    def decorator(view_func: Callable) -> Callable:  # type: ignore[type-arg]
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                return HttpResponseForbidden("Доступ заборонено")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

## orders/services.py — approve_order

```python
from django.utils import timezone
from django.db import transaction
from orders.models import Order
from kitchen.services import create_tickets_for_order


def approve_order(order: Order, waiter) -> Order:  # type: ignore[type-arg]
    """Офіціант підтверджує замовлення.

    Атомарно:
    1. Оновлює статус Order → APPROVED
    2. Прив'язує офіціанта
    3. Створює KitchenTicket для кожного OrderItem

    Raises:
        ValueError: якщо order не в статусі SUBMITTED.
    """
    if order.status != Order.Status.SUBMITTED:
        raise ValueError(f"Cannot approve order in status '{order.status}'")

    with transaction.atomic():
        order.status = Order.Status.APPROVED
        order.waiter = waiter
        order.approved_at = timezone.now()
        order.save(update_fields=["status", "waiter", "approved_at", "updated_at"])
        create_tickets_for_order(order)

    return order
```

## orders/waiter_views.py

```python
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from orders.models import Order
from orders.services import approve_order
from user.decorators import role_required

WAITER_ROLES = ("waiter", "senior_waiter", "manager")


@role_required(*WAITER_ROLES)
def waiter_order_list(request: HttpRequest) -> HttpResponse:
    """Список активних замовлень офіціанта."""
    orders = Order.objects.filter(
        waiter=request.user,
        status__in=[
            Order.Status.SUBMITTED,
            Order.Status.APPROVED,
            Order.Status.IN_PROGRESS,
            Order.Status.READY,
        ],
    ).prefetch_related("items__dish")
    return render(request, "orders/waiter_order_list.html", {"orders": orders})


@role_required(*WAITER_ROLES)
def order_scan(request: HttpRequest, order_id: int) -> HttpResponse:
    """Відкрити замовлення після сканування QR або введення номера."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items__dish"),
        pk=order_id,
        status=Order.Status.DRAFT,
    )
    return render(request, "orders/waiter_order_scan.html", {"order": order})


@role_required(*WAITER_ROLES)
def order_approve(request: HttpRequest, order_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("waiter:order_scan", order_id=order_id)

    order = get_object_or_404(Order, pk=order_id)
    try:
        approve_order(order, waiter=request.user)
        messages.success(request, f"Замовлення #{order_id} підтверджено.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("waiter:order_list")
```

## Тести

```python
# orders/tests/test_waiter_flow.py
import pytest
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_approve_order_changes_status(django_user_model):
    from orders.models import Order, OrderItem
    from orders.services import approve_order
    from menu.models import Category, Dish

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    OrderItem.objects.create(order=order, dish=dish, quantity=1)

    approved = approve_order(order, waiter=waiter)

    assert approved.status == Order.Status.APPROVED
    assert approved.waiter == waiter
    assert approved.approved_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_approve_creates_kitchen_tickets(django_user_model):
    from orders.models import Order, OrderItem
    from orders.services import approve_order
    from kitchen.models import KitchenTicket
    from menu.models import Category, Dish

    waiter = django_user_model.objects.create_user(
        email="w2@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish1 = Dish.objects.create(
        title="D1", description="", price=Decimal("5.00"), weight=100, calorie=100, category=cat
    )
    dish2 = Dish.objects.create(
        title="D2", description="", price=Decimal("3.00"), weight=100, calorie=100, category=cat
    )
    order = Order.objects.create(status=Order.Status.SUBMITTED)
    OrderItem.objects.create(order=order, dish=dish1, quantity=1)
    OrderItem.objects.create(order=order, dish=dish2, quantity=2)

    approve_order(order, waiter=waiter)

    assert KitchenTicket.objects.filter(order_item__order=order).count() == 2


@pytest.mark.tier2
@pytest.mark.django_db
def test_approve_raises_for_wrong_status(django_user_model):
    from orders.models import Order
    from orders.services import approve_order

    waiter = django_user_model.objects.create_user(
        email="w3@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(status=Order.Status.DRAFT)

    with pytest.raises(ValueError, match="Cannot approve"):
        approve_order(order, waiter=waiter)


@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_cannot_access_waiter_view(client, django_user_model):
    visitor = django_user_model.objects.create_user(
        email="v@test.com", password="pass", role="visitor"
    )
    client.force_login(visitor)
    response = client.get("/order/waiter/orders/")
    assert response.status_code == 403


@pytest.mark.tier2
@pytest.mark.django_db
def test_kitchen_cannot_access_waiter_view(client, django_user_model):
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/order/waiter/orders/")
    assert response.status_code == 403
```

## Acceptance criteria

- [ ] `role_required` декоратор — перевіряє роль, повертає 403 або redirect
- [ ] `approve_order` — атомарна, raises `ValueError` при неправильному статусі
- [ ] Офіціант відкриває замовлення по QR (`/waiter/order/<id>/scan/`)
- [ ] Після approve: `Order.status=APPROVED`, `KitchenTicket` для кожного item
- [ ] `visitor`, `kitchen` → 403 при доступі до waiter views
- [ ] `uv run pytest -m "tier1 or tier2" orders/tests/test_waiter_flow.py` — зелені
