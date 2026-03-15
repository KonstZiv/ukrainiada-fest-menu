# Task 2.3 — Статистика throughput (детально)

## kitchen/stats.py

```python
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from menu.models import Dish
from kitchen.models import KitchenTicket


def get_dish_queue_stats() -> dict[int, dict[str, int]]:
    """Повертає статистику по кожній страві.

    Returns:
        {dish_id: {"pending": N, "done_recently": M}}

    "done_recently" — кількість виданих за останні SPEED_INTERVAL_KITCHEN хвилин.
    Використовується офіціантом для оцінки часу очікування.
    """
    window_start = timezone.now() - timedelta(minutes=settings.SPEED_INTERVAL_KITCHEN)

    stats_qs = (
        KitchenTicket.objects
        .values("order_item__dish_id")
        .annotate(
            pending=Count("id", filter=Q(status=KitchenTicket.Status.PENDING)),
            done_recently=Count(
                "id",
                filter=Q(status=KitchenTicket.Status.DONE, done_at__gte=window_start),
            ),
        )
    )

    return {
        row["order_item__dish_id"]: {
            "pending": row["pending"],
            "done_recently": row["done_recently"],
        }
        for row in stats_qs
    }
```

## Використання у view офіціанта

```python
# Додати до waiter_views.py::waiter_order_list
from kitchen.stats import get_dish_queue_stats

def waiter_order_list(request):
    orders = ...  # як і раніше
    dish_stats = get_dish_queue_stats()
    return render(request, "orders/waiter_order_list.html", {
        "orders": orders,
        "dish_stats": dish_stats,
    })
```

## Шаблон (фрагмент)

```html
{% for item in order.items.all %}
  <li>
    {{ item.dish.title }} x{{ item.quantity }}
    {% with stats=dish_stats|get_item:item.dish.id %}
      {% if stats %}
        <small class="text-muted">
          Черга: {{ stats.pending }} |
          Видано за {{ SPEED_INTERVAL_KITCHEN }} хв: {{ stats.done_recently }}
        </small>
      {% endif %}
    {% endwith %}
  </li>
{% endfor %}
```

## Тести

```python
# kitchen/tests/test_stats.py
import pytest
from decimal import Decimal


@pytest.mark.tier1
def test_get_dish_queue_stats_returns_dict():
    """Функція повертає dict — перевіряємо без БД через mock."""
    from unittest.mock import patch, MagicMock
    mock_qs = MagicMock()
    mock_qs.values.return_value.annotate.return_value = []
    with patch("kitchen.stats.KitchenTicket.objects", mock_qs):
        from kitchen.stats import get_dish_queue_stats
        result = get_dish_queue_stats()
        assert isinstance(result, dict)


@pytest.mark.tier2
@pytest.mark.django_db
def test_stats_counts_pending_correctly(django_user_model):
    from kitchen.stats import get_dish_queue_stats
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="Borsch", description="", price=Decimal("8.00"), weight=400, calorie=320, category=cat
    )
    order = Order.objects.create(status="approved")
    item1 = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    item2 = OrderItem.objects.create(order=order, dish=dish, quantity=2)  # same dish — other order
    order2 = Order.objects.create(status="approved")
    item3 = OrderItem.objects.create(order=order2, dish=dish, quantity=1)

    KitchenTicket.objects.create(order_item=item1, status="pending")
    KitchenTicket.objects.create(order_item=item3, status="pending")

    stats = get_dish_queue_stats()
    assert stats[dish.id]["pending"] == 2
```

## Acceptance criteria

- [ ] `get_dish_queue_stats()` — один SQL запит (annotate), не N+1
- [ ] Офіціант бачить `pending` і `done_recently` для кожної страви
- [ ] `SPEED_INTERVAL_KITCHEN` береться з settings
- [ ] Тести зелені
