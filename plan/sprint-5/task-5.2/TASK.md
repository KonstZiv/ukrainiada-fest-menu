# Task 5.2 — Офіціант підтверджує прийом по QR (детально)

## orders/waiter_views.py — додати

```python
import uuid
from kitchen.models import KitchenHandoff


@role_required(*WAITER_ROLES)
def handoff_confirm_view(request: HttpRequest, token: uuid.UUID) -> HttpResponse:
    """Офіціант підтверджує прийом страви після сканування QR.

    GET  — показує деталі передачі (що, від кого)
    POST — підтверджує прийом
    """
    handoff = get_object_or_404(KitchenHandoff, token=token)

    # Перевірка що цей QR призначений саме цьому офіціанту
    if handoff.target_waiter_id != request.user.id:
        return HttpResponse(
            "Цей QR-код призначений іншому офіціанту.", status=403
        )

    # Перевірка TTL
    if handoff.is_expired:
        return render(request, "orders/handoff_expired.html", {
            "handoff": handoff,
        }, status=400)

    # Вже підтверджено
    if handoff.is_confirmed:
        return render(request, "orders/handoff_already_confirmed.html", {
            "handoff": handoff,
        })

    if request.method == "POST":
        _confirm_handoff(handoff)
        messages.success(
            request,
            f"Прийом '{handoff.ticket.order_item.dish.title}' підтверджено."
        )
        return redirect("waiter:dashboard")

    return render(request, "orders/handoff_confirm.html", {"handoff": handoff})


def _confirm_handoff(handoff: KitchenHandoff) -> None:
    """Атомарне підтвердження передачі."""
    from django.utils import timezone
    from django.db import transaction

    with transaction.atomic():
        handoff.is_confirmed = True
        handoff.confirmed_at = timezone.now()
        handoff.save(update_fields=["is_confirmed", "confirmed_at"])
```

## Шаблон orders/handoff_confirm.html

```html
<div class="handoff-confirm text-center">
    <h2>Підтвердження прийому страви</h2>

    <div class="dish-info my-4">
        <h3>🍽 {{ handoff.ticket.order_item.dish.title }}</h3>
        <p>Кількість: <strong>{{ handoff.ticket.order_item.quantity }}</strong></p>
        <p>Від: <strong>{{ handoff.ticket.assigned_to.get_full_name }}</strong></p>
        <p>Замовлення: <strong>#{{ handoff.ticket.order_item.order.id }}</strong></p>
    </div>

    <form method="post">
        {% csrf_token %}
        <button type="submit" class="btn btn-success btn-lg w-100">
            ✓ Підтверджую прийом
        </button>
    </form>

    <p class="text-muted mt-3">
        <small>QR дійсний ще ~{{ ttl_remaining }} секунд</small>
    </p>
</div>
```

## Шаблон orders/handoff_expired.html

```html
<div class="alert alert-danger text-center">
    <h3>⏱ QR-код прострочений</h3>
    <p>Попросіть кухаря згенерувати новий QR-код.</p>
    <p>Або скористайтесь ручним підтвердженням.</p>
    <a href="{% url 'waiter:dashboard' %}" class="btn btn-primary">
        Повернутись до dashboard
    </a>
</div>
```

## URL в waiter_urls.py

```python
path(
    "handoff/<uuid:token>/confirm/",
    waiter_views.handoff_confirm_view,
    name="handoff_confirm",
),
```

## Тести

```python
# orders/tests/test_handoff_confirm.py
import pytest
import uuid
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_handoff_confirm_get(client, django_user_model):
    from kitchen.models import KitchenHandoff, KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="Борщ", description="", price=Decimal("8.00"), weight=400,
        calorie=320, category=cat
    )
    order = Order.objects.create(waiter=waiter, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status="done", assigned_to=kitchen_user
    )
    handoff = KitchenHandoff.objects.create(
        ticket=ticket, target_waiter=waiter
    )

    client.force_login(waiter)
    response = client.get(f"/order/waiter/handoff/{handoff.token}/confirm/")
    assert response.status_code == 200
    assert "Борщ" in response.content.decode()


@pytest.mark.tier2
@pytest.mark.django_db
def test_handoff_confirm_post(client, django_user_model):
    from kitchen.models import KitchenHandoff, KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status="done", assigned_to=kitchen_user
    )
    handoff = KitchenHandoff.objects.create(
        ticket=ticket, target_waiter=waiter
    )

    client.force_login(waiter)
    response = client.post(f"/order/waiter/handoff/{handoff.token}/confirm/")
    assert response.status_code == 302
    handoff.refresh_from_db()
    assert handoff.is_confirmed is True
    assert handoff.confirmed_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_wrong_waiter_gets_403(client, django_user_model):
    from kitchen.models import KitchenHandoff, KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter1 = django_user_model.objects.create_user(
        email="w1@test.com", password="pass", role="waiter"
    )
    waiter2 = django_user_model.objects.create_user(
        email="w2@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter1, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status="done", assigned_to=kitchen_user
    )
    handoff = KitchenHandoff.objects.create(ticket=ticket, target_waiter=waiter1)

    client.force_login(waiter2)
    response = client.get(f"/order/waiter/handoff/{handoff.token}/confirm/")
    assert response.status_code == 403


@pytest.mark.tier2
@pytest.mark.django_db
def test_expired_handoff_returns_400(client, django_user_model):
    from kitchen.models import KitchenHandoff, KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish
    from django.utils import timezone
    from datetime import timedelta

    kitchen_user = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    cat = Category.objects.create(title="C", description="", number_in_line=1)
    dish = Dish.objects.create(
        title="D", description="", price=Decimal("5.00"), weight=100,
        calorie=100, category=cat
    )
    order = Order.objects.create(waiter=waiter, status="approved")
    item = OrderItem.objects.create(order=order, dish=dish, quantity=1)
    ticket = KitchenTicket.objects.create(
        order_item=item, status="done", assigned_to=kitchen_user
    )
    handoff = KitchenHandoff.objects.create(ticket=ticket, target_waiter=waiter)
    old_time = timezone.now() - timedelta(seconds=300)
    KitchenHandoff.objects.filter(pk=handoff.pk).update(created_at=old_time)

    client.force_login(waiter)
    response = client.get(f"/order/waiter/handoff/{handoff.token}/confirm/")
    assert response.status_code == 400
```

## Acceptance criteria

- [ ] GET: офіціант бачить назву страви, кухаря, номер замовлення
- [ ] POST: `is_confirmed=True`, `confirmed_at` заповнено
- [ ] Чужий офіціант → 403
- [ ] Прострочений токен → 400 з зрозумілим повідомленням
- [ ] Вже підтверджений → показує "вже підтверджено" (не 400)
- [ ] Тести зелені
