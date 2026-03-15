# Task 3.2 — Заглушка онлайн-оплати (детально)

## Концепція

Реальний платіжний шлюз — рішення в майбутньому (Stripe / Revolut / PayPal).
Зараз: повний UI з кнопкою "Оплатити онлайн" → заглушка що симулює успіх.

Офіціант бачить індикатор "Оплачено онлайн" автоматично (без ручного підтвердження).

## orders/services.py — додати

```python
def confirm_online_payment_stub(order: Order) -> Order:
    """Заглушка онлайн-оплати.

    УВАГА: це заглушка — реальний платіжний шлюз інтегрується пізніше.
    Поточна поведінка: завжди успішно підтверджує оплату.

    В майбутньому: замінити на виклик payment gateway API,
    обробку webhook підтвердження, зберігання transaction_id.
    """
    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValueError("Order is already paid")

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = Order.PaymentMethod.ONLINE
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(update_fields=[
        "payment_status", "payment_method",
        "payment_confirmed_at", "payment_escalation_level", "updated_at",
    ])
    return order
```

## orders/views.py — додати для відвідувача

```python
def order_pay_online(request: HttpRequest, order_id: int) -> HttpResponse:
    """Сторінка онлайн-оплати (заглушка)."""
    order = get_object_or_404(Order, pk=order_id)

    if request.method == "POST":
        try:
            confirm_online_payment_stub(order)
            messages.success(request, "Оплату підтверджено!")
            return redirect("orders:order_detail", order_id=order_id)
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, "orders/pay_online.html", {"order": order})
```

## Шаблон orders/pay_online.html

```html
<div class="payment-page">
    <h2>Оплата замовлення #{{ order.id }}</h2>
    <p class="total">Сума: <strong>€{{ order.total_price }}</strong></p>

    {% if order.payment_status == 'unpaid' %}
    <div class="alert alert-info">
        <strong>⚠️ Демо-режим:</strong>
        Реальна оплата ще не підключена. Кнопка симулює успішну оплату.
    </div>

    <form method="post">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary btn-lg">
            💳 Оплатити онлайн (демо)
        </button>
    </form>
    {% else %}
    <div class="alert alert-success">
        ✓ Замовлення оплачено ({{ order.get_payment_method_display }})
    </div>
    {% endif %}
</div>
```

## Тести

```python
# orders/tests/test_online_payment.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_online_payment_stub_marks_paid(django_user_model):
    from orders.models import Order
    from orders.services import confirm_online_payment_stub

    order = Order.objects.create(payment_status=Order.PaymentStatus.UNPAID)
    result = confirm_online_payment_stub(order)

    assert result.payment_status == Order.PaymentStatus.PAID
    assert result.payment_method == Order.PaymentMethod.ONLINE
    assert result.payment_confirmed_at is not None


@pytest.mark.tier2
@pytest.mark.django_db
def test_online_payment_page_get(client):
    from orders.models import Order
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/pay/")
    assert response.status_code == 200
    assert "Демо-режим" in response.content.decode()


@pytest.mark.tier2
@pytest.mark.django_db
def test_online_payment_page_post(client):
    from orders.models import Order
    order = Order.objects.create(status=Order.Status.APPROVED)
    response = client.post(f"/order/{order.id}/pay/")
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.payment_status == Order.PaymentStatus.PAID
```

## Acceptance criteria

- [ ] `confirm_online_payment_stub` — чітко позначена як заглушка в docstring
- [ ] Сторінка `/order/<id>/pay/` — відображає попередження "Демо-режим"
- [ ] POST на сторінку → `payment_status = PAID`, `payment_method = ONLINE`
- [ ] Офіціант у dashboard бачить "Оплачено (Онлайн)" без ручного підтвердження
- [ ] Тести зелені
