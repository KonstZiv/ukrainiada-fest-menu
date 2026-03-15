# Task 3.1 — Підтвердження оплати готівкою (детально)

## Модель — додати до Order

```python
# orders/models.py

class PaymentMethod(models.TextChoices):
    CASH = "cash", "Готівка"
    ONLINE = "online", "Онлайн"
    NOT_SET = "not_set", "Не визначено"

payment_method = models.CharField(
    max_length=10,
    choices=PaymentMethod.choices,
    default=PaymentMethod.NOT_SET,
)

payment_escalation_level = models.IntegerField(
    default=0,
    db_index=True,
    help_text="0=none, 1=senior_waiter, 2=manager",
)
```

## orders/services.py — додати

```python
from django.utils import timezone
from orders.models import Order


def confirm_cash_payment(order: Order, waiter) -> Order:  # type: ignore[type-arg]
    """Офіціант підтверджує що прийняв готівку.

    Raises:
        ValueError: якщо замовлення вже оплачене.
        ValueError: якщо waiter не є офіціантом цього замовлення.
    """
    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValueError("Order is already paid")
    if order.waiter_id != waiter.id:
        raise ValueError("Only the assigned waiter can confirm payment")

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = Order.PaymentMethod.CASH
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(update_fields=[
        "payment_status", "payment_method",
        "payment_confirmed_at", "payment_escalation_level", "updated_at",
    ])
    return order
```

## orders/waiter_views.py — додати view

```python
from orders.services import confirm_cash_payment


@role_required(*WAITER_ROLES)
def order_confirm_payment(request: HttpRequest, order_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("waiter:dashboard")

    order = get_object_or_404(Order, pk=order_id, waiter=request.user)
    try:
        confirm_cash_payment(order, waiter=request.user)
        messages.success(request, f"Оплату замовлення #{order_id} підтверджено (готівка).")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("waiter:dashboard")
```

## Шаблон — кнопка в waiter_dashboard.html

```html
{% if order.payment_status == 'unpaid' %}
<div class="payment-block">
    <form method="post" action="{% url 'waiter:confirm_payment' order.id %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-warning">
            💵 Прийняв готівку
        </button>
    </form>
</div>
{% else %}
<span class="badge bg-success">✓ Оплачено ({{ order.get_payment_method_display }})</span>
{% endif %}
```

## Тести

```python
# orders/tests/test_payment.py
import pytest


@pytest.mark.tier1
def test_payment_method_choices():
    from orders.models import Order
    methods = {m.value for m in Order.PaymentMethod}
    assert methods == {"cash", "online", "not_set"}


@pytest.mark.tier2
@pytest.mark.django_db
def test_confirm_cash_payment_success(django_user_model):
    from orders.models import Order
    from orders.services import confirm_cash_payment

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
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


@pytest.mark.tier2
@pytest.mark.django_db
def test_confirm_payment_already_paid(django_user_model):
    from orders.models import Order
    from orders.services import confirm_cash_payment

    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(
        waiter=waiter,
        payment_status=Order.PaymentStatus.PAID,
    )
    with pytest.raises(ValueError, match="already paid"):
        confirm_cash_payment(order, waiter=waiter)


@pytest.mark.tier2
@pytest.mark.django_db
def test_confirm_payment_wrong_waiter(django_user_model):
    from orders.models import Order
    from orders.services import confirm_cash_payment

    waiter1 = django_user_model.objects.create_user(
        email="w1@test.com", password="pass", role="waiter"
    )
    waiter2 = django_user_model.objects.create_user(
        email="w2@test.com", password="pass", role="waiter"
    )
    order = Order.objects.create(waiter=waiter1, payment_status=Order.PaymentStatus.UNPAID)
    with pytest.raises(ValueError, match="Only the assigned waiter"):
        confirm_cash_payment(order, waiter=waiter2)
```

## Acceptance criteria

- [ ] `Order.payment_method` і `payment_escalation_level` — в БД, міграція
- [ ] `confirm_cash_payment` — raises ValueError при дублікаті або чужому офіціанті
- [ ] Кнопка "Прийняв готівку" — тільки для `UNPAID` замовлень
- [ ] Після підтвердження — кнопка зникає, зʼявляється бейдж "Оплачено (Готівка)"
- [ ] Тести зелені
