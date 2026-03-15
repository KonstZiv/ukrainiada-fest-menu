# Task 5.3 — Fallback: ручне підтвердження (детально)

## Концепція

Якщо офіціант не може відсканувати QR (немає телефону, сів акумулятор, поганий сигнал)
— кухар може натиснути "Передав без сканування". Це одностороннє підтвердження.

На UI кухні поруч з кнопкою "Генерувати QR" є кнопка "Передав вручну".

## kitchen/services.py — додати

```python
def manual_handoff(ticket: KitchenTicket, kitchen_user) -> None:  # type: ignore[type-arg]
    """Ручне підтвердження передачі страви без QR-сканування.

    Кухар відмічає що передав страву офіціанту — без підтвердження офіціантом.
    Використовується як fallback коли QR-флоу недоступний.

    Ticket вже повинен бути DONE. Операція ідемпотентна.
    """
    if ticket.status != KitchenTicket.Status.DONE:
        raise ValueError(f"Cannot handoff ticket in status '{ticket.status}'")
    if ticket.assigned_to_id != kitchen_user.id:
        raise ValueError("Only the assigned cook can confirm handoff")

    from kitchen.models import KitchenHandoff
    from django.utils import timezone

    # Якщо є незавершений QR-handoff — скасовуємо
    KitchenHandoff.objects.filter(
        ticket=ticket, is_confirmed=False
    ).update(is_confirmed=True, confirmed_at=timezone.now())

    # Якщо handoff взагалі не існує — просто позначаємо через флаг на ticket
    # (не створюємо handoff, бо тут немає target_waiter)
    ticket.save(update_fields=["updated_at"])  # touch для updated_at
```

## kitchen/views.py — додати

```python
@role_required(*KITCHEN_ROLES)
@require_POST
def ticket_manual_handoff(request: HttpRequest, ticket_id: int) -> HttpResponse:
    """Кухар вручну відмічає що передав страву (fallback без QR)."""
    ticket = get_object_or_404(
        KitchenTicket,
        pk=ticket_id,
        assigned_to=request.user,
        status=KitchenTicket.Status.DONE,
    )
    try:
        manual_handoff(ticket, kitchen_user=request.user)
        messages.success(
            request,
            f"Передачу '{ticket.order_item.dish.title}' відмічено вручну."
        )
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("kitchen:dashboard")
```

## Шаблон kitchen/dashboard.html — кнопки передачі

```html
<!-- В секції "my_done" для кожного тікету -->
{% for ticket in my_done %}
<div class="ticket-row">
    <span>{{ ticket.order_item.dish.title }}</span>
    <span>Офіціант: {{ ticket.order_item.order.waiter.get_full_name }}</span>

    {% if not ticket.handoff.is_confirmed %}
    <div class="handoff-actions">
        <!-- Основний шлях: QR -->
        <a href="{% url 'kitchen:handoff_qr' ticket.id %}"
           class="btn btn-primary btn-sm">
            📱 Генерувати QR
        </a>
        <!-- Fallback -->
        <form method="post" action="{% url 'kitchen:manual_handoff' ticket.id %}"
              style="display:inline">
            {% csrf_token %}
            <button type="submit" class="btn btn-outline-secondary btn-sm">
                ✋ Передав вручну
            </button>
        </form>
    </div>
    {% else %}
    <span class="badge bg-success">✓ Передано</span>
    {% endif %}
</div>
{% endfor %}
```

## Тести

```python
# kitchen/tests/test_manual_handoff.py
import pytest
from decimal import Decimal


@pytest.mark.tier2
@pytest.mark.django_db
def test_manual_handoff_success(client, django_user_model):
    from kitchen.services import manual_handoff
    from kitchen.models import KitchenTicket
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
        order_item=item, status=KitchenTicket.Status.DONE,
        assigned_to=kitchen_user
    )
    # Не повинно кинути виключення
    manual_handoff(ticket, kitchen_user=kitchen_user)


@pytest.mark.tier2
@pytest.mark.django_db
def test_manual_handoff_wrong_cook(django_user_model):
    from kitchen.services import manual_handoff
    from kitchen.models import KitchenTicket
    from orders.models import Order, OrderItem
    from menu.models import Category, Dish

    k1 = django_user_model.objects.create_user(
        email="k1@test.com", password="pass", role="kitchen"
    )
    k2 = django_user_model.objects.create_user(
        email="k2@test.com", password="pass", role="kitchen"
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
        order_item=item, status=KitchenTicket.Status.DONE, assigned_to=k1
    )
    with pytest.raises(ValueError, match="Only the assigned cook"):
        manual_handoff(ticket, kitchen_user=k2)
```

## Acceptance criteria

- [ ] Обидві кнопки ("QR" і "Передав вручну") видно в секції `my_done`
- [ ] `manual_handoff` — ідемпотентна, скасовує незавершені QR-handoff
- [ ] Тільки `assigned_to` кухар може зробити manual_handoff → ValueError
- [ ] Тести зелені
