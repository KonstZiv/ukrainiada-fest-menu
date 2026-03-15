# Task 2.5 — Waiter dashboard: стан моїх замовлень (детально)

## Концепція

Офіціант бачить таблицю своїх активних замовлень.
Для кожного замовлення — список страв з їх поточним статусом KitchenTicket.
Також бачить хто зі складу кухні взяв страву і коли.

Оновлення — через SSE (Sprint 4). Зараз: статичний рендеринг з кнопкою "оновити".

## orders/waiter_views.py — розширити waiter_order_list

```python
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from kitchen.stats import get_dish_queue_stats
from orders.models import Order, OrderItem
from kitchen.models import KitchenTicket
from user.decorators import role_required

WAITER_ROLES = ("waiter", "senior_waiter", "manager")


@role_required(*WAITER_ROLES)
def waiter_dashboard(request: HttpRequest) -> HttpResponse:
    """Головна сторінка офіціанта — всі активні замовлення зі станом страв."""
    active_statuses = [
        Order.Status.SUBMITTED,
        Order.Status.APPROVED,
        Order.Status.IN_PROGRESS,
        Order.Status.READY,
    ]

    orders = (
        Order.objects.filter(waiter=request.user, status__in=active_statuses)
        .prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
        )
        .order_by("created_at")
    )

    dish_stats = get_dish_queue_stats()

    return render(request, "orders/waiter_dashboard.html", {
        "orders": orders,
        "dish_stats": dish_stats,
    })


@role_required(*WAITER_ROLES)
def order_mark_delivered(request: HttpRequest, order_id: int) -> HttpResponse:
    """Офіціант відмічає що передав замовлення відвідувачу."""
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)

    if order.status != Order.Status.READY:
        messages.error(request, f"Замовлення #{order_id} ще не готове.")
        return redirect("waiter:dashboard")

    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at", "updated_at"])
    messages.success(request, f"Замовлення #{order_id} видано відвідувачу.")
    return redirect("waiter:dashboard")
```

## Шаблон orders/waiter_dashboard.html (ключова частина)

```html
{% for order in orders %}
<div class="order-card {% if order.status == 'ready' %}order-ready{% endif %}">
    <h3>Замовлення #{{ order.id }}</h3>
    <span class="badge">{{ order.get_status_display }}</span>

    <table>
        <thead>
            <tr>
                <th>Страва</th>
                <th>К-сть</th>
                <th>Статус кухні</th>
                <th>Кухар</th>
            </tr>
        </thead>
        <tbody>
        {% for item in order.items.all %}
            <tr>
                <td>{{ item.dish.title }}</td>
                <td>{{ item.quantity }}</td>
                <td>
                    {% if item.kitchen_ticket %}
                        {{ item.kitchen_ticket.get_status_display }}
                    {% else %}
                        —
                    {% endif %}
                </td>
                <td>
                    {% if item.kitchen_ticket.assigned_to %}
                        {{ item.kitchen_ticket.assigned_to.get_full_name }}
                        {% if item.kitchen_ticket.taken_at %}
                            ({{ item.kitchen_ticket.taken_at|timesince }} тому)
                        {% endif %}
                    {% else %}
                        —
                    {% endif %}
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>

    {% if order.status == 'ready' %}
    <form method="post" action="{% url 'waiter:order_delivered' order.id %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-success btn-lg">
            ✓ Передав відвідувачу
        </button>
    </form>
    {% endif %}

    <p>Сума: €{{ order.total_price }}</p>
    <p>Оплата: {{ order.get_payment_status_display }}</p>
</div>
{% empty %}
<p>Немає активних замовлень.</p>
{% endfor %}
```

## URL додати до waiter_urls.py

```python
path("dashboard/", waiter_views.waiter_dashboard, name="dashboard"),
path("order/<int:order_id>/delivered/", waiter_views.order_mark_delivered, name="order_delivered"),
```

## Тести

```python
# orders/tests/test_waiter_dashboard.py
import pytest
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_waiter_dashboard_shows_only_own_orders(client, django_user_model):
    from orders.models import Order

    waiter1 = django_user_model.objects.create_user(
        email="w1@test.com", password="pass", role="waiter"
    )
    waiter2 = django_user_model.objects.create_user(
        email="w2@test.com", password="pass", role="waiter"
    )
    Order.objects.create(waiter=waiter1, status="approved")
    Order.objects.create(waiter=waiter2, status="approved")

    client.force_login(waiter1)
    response = client.get("/order/waiter/dashboard/")

    assert response.status_code == 200
    orders_in_context = response.context["orders"]
    assert orders_in_context.count() == 1
    assert orders_in_context.first().waiter == waiter1


@pytest.mark.tier2
@pytest.mark.django_db
def test_mark_delivered_changes_status(client, django_user_model):
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.READY)

    client.force_login(waiter)
    response = client.post(f"/order/waiter/order/{order.id}/delivered/")

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert order.delivered_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_cannot_mark_delivered_if_not_ready(client, django_user_model):
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.APPROVED)

    client.force_login(waiter)
    client.post(f"/order/waiter/order/{order.id}/delivered/")

    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED  # не змінився


@pytest.mark.tier2
@pytest.mark.django_db
def test_waiter_cannot_mark_others_order(client, django_user_model):
    from orders.models import Order

    waiter1 = django_user_model.objects.create_user(
        email="w1@test.com", password="pass", role="waiter"
    )
    waiter2 = django_user_model.objects.create_user(
        email="w2@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(waiter=waiter2, status=Order.Status.READY)

    client.force_login(waiter1)
    response = client.post(f"/order/waiter/order/{order.id}/delivered/")
    assert response.status_code == 404
```

## Acceptance criteria

- [ ] Waiter dashboard показує тільки власні активні замовлення
- [ ] Для кожної страви: статус KitchenTicket + ім'я кухаря + "N хвилин тому"
- [ ] Кнопка "Передав відвідувачу" — тільки для `READY` замовлень
- [ ] `order_mark_delivered` — перевіряє `waiter=request.user` (404 для чужих)
- [ ] `uv run pytest -m "tier1 or tier2" orders/tests/test_waiter_dashboard.py` — зелені
