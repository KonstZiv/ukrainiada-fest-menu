# Task 5.4 — Офіціант відмічає передачу відвідувачу (детально)

## Концепція

Відвідувачі на фестивалі — різні. Багато хто без смартфону або не захочуть встановлювати
щось. Тому підтвердження від відвідувача — НЕ обов'язкове.

Офіціант сам натискає кнопку "Передав відвідувачу" після вручення страви.
Ця функціональність частково реалізована в Task 2.5 (`order_mark_delivered`).
Тут — доточуємо і закріплюємо.

## Що вже є (з Task 2.5)

- `order_mark_delivered` view — переводить `Order.status → DELIVERED`
- Кнопка "Передав відвідувачу" в `waiter_dashboard.html`

## Що додаємо в цьому таску

### 1. Перевірка що всі тікети DONE перед DELIVERED

```python
# orders/services.py — оновити order_mark_delivered логіку

def deliver_order(order: Order, waiter) -> Order:  # type: ignore[type-arg]
    """Офіціант відмічає що передав замовлення відвідувачу.

    Raises:
        ValueError: якщо замовлення не в статусі READY.
        ValueError: якщо є непередані страви (KitchenTicket не DONE).
    """
    if order.status != Order.Status.READY:
        raise ValueError(f"Order #{order.id} is not ready (status: {order.status})")
    if order.waiter_id != waiter.id:
        raise ValueError("Only the assigned waiter can deliver the order")

    # Перевірка що всі тікети підтверджені кухнею
    from kitchen.models import KitchenTicket
    unconfirmed = KitchenTicket.objects.filter(
        order_item__order=order,
    ).exclude(status=KitchenTicket.Status.DONE).count()

    if unconfirmed > 0:
        raise ValueError(f"{unconfirmed} dish(es) not yet ready from kitchen")

    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at", "updated_at"])
    return order
```

### 2. Оновити view

```python
# orders/waiter_views.py — order_mark_delivered → використовує deliver_order

@role_required(*WAITER_ROLES)
def order_mark_delivered(request: HttpRequest, order_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        deliver_order(order, waiter=request.user)
        messages.success(request, f"Замовлення #{order_id} передано відвідувачу.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("waiter:dashboard")
```

### 3. Після DELIVERED — нагадування про оплату

Якщо `payment_status = UNPAID` — одразу показати попередження:

```html
<!-- waiter_dashboard.html — після успішного delivered -->
{% if order.status == 'delivered' and order.payment_status == 'unpaid' %}
<div class="alert alert-warning">
    ⚠️ Замовлення #{{ order.id }} передано, але НЕ ОПЛАЧЕНО!
    <form method="post" action="{% url 'waiter:confirm_payment' order.id %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-warning btn-sm">
            💵 Прийняв готівку
        </button>
    </form>
</div>
{% endif %}
```

## Тести

```python
# orders/tests/test_deliver.py
import pytest
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_deliver_order_success(django_user_model):
    from orders.services import deliver_order
    from orders.models import Order, OrderItem
    from kitchen.models import KitchenTicket
    from menu.models import Category, Dish

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.READY)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(order_item=item, status="done")

    result = deliver_order(order, waiter=waiter)
    assert result.status == Order.Status.DELIVERED
    assert result.delivered_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_deliver_fails_if_ticket_not_done(django_user_model):
    from orders.services import deliver_order
    from orders.models import Order, OrderItem
    from kitchen.models import KitchenTicket
    from menu.models import Category, Dish

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.READY)
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    KitchenTicket.objects.create(order_item=item, status="taken")  # ще не DONE

    with pytest.raises(ValueError, match="not yet ready"):
        deliver_order(order, waiter=waiter)


@pytest.mark.tier2
@pytest.mark.django_db
def test_deliver_fails_if_not_ready_status(django_user_model):
    from orders.services import deliver_order
    from orders.models import Order

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(waiter=waiter, status=Order.Status.APPROVED)
    with pytest.raises(ValueError, match="not ready"):
        deliver_order(order, waiter=waiter)
```

## Acceptance criteria

- [ ] `deliver_order` — перевіряє що всі KitchenTicket DONE
- [ ] Якщо є `taken` або `pending` тікети → ValueError, замовлення не переводиться
- [ ] Після DELIVERED + UNPAID → попередження з кнопкою оплати
- [ ] Тести зелені
