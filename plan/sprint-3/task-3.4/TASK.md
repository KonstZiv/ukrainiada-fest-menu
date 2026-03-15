# Task 3.4 — Senior waiter dashboard (детально)

## orders/waiter_views.py — додати

```python
SENIOR_ROLES = ("senior_waiter", "manager")


@role_required(*SENIOR_ROLES)
def senior_waiter_dashboard(request: HttpRequest) -> HttpResponse:
    """Dashboard старшого офіціанта — ескальовані несплачені замовлення."""
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    # Рівень 1 — для senior_waiter і вище
    escalated_orders = (
        Order.objects.filter(
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.UNPAID,
            payment_escalation_level__gte=1,
        )
        .select_related("waiter", "visitor")
        .prefetch_related("items__dish")
        .order_by("delivered_at")
    )

    # Розраховуємо скільки часу минуло з доставки
    now = timezone.now()
    orders_with_age = []
    for order in escalated_orders:
        age = now - order.delivered_at if order.delivered_at else None
        orders_with_age.append({
            "order": order,
            "minutes_since_delivery": int(age.total_seconds() / 60) if age else None,
            "escalation_level": order.payment_escalation_level,
        })

    return render(request, "orders/senior_waiter_dashboard.html", {
        "orders_with_age": orders_with_age,
        "pay_timeout": settings.PAY_TIMEOUT,
    })


@role_required(*SENIOR_ROLES)
def senior_confirm_payment(request: HttpRequest, order_id: int) -> HttpResponse:
    """Старший офіціант підтверджує оплату замість відповідального офіціанта."""
    if request.method != "POST":
        return redirect("waiter:senior_dashboard")

    order = get_object_or_404(
        Order,
        pk=order_id,
        payment_status=Order.PaymentStatus.UNPAID,
    )
    payment_type = request.POST.get("payment_type", "cash")

    order.payment_status = Order.PaymentStatus.PAID
    order.payment_method = (
        Order.PaymentMethod.CASH if payment_type == "cash" else Order.PaymentMethod.ONLINE
    )
    order.payment_confirmed_at = timezone.now()
    order.payment_escalation_level = 0
    order.save(update_fields=[
        "payment_status", "payment_method",
        "payment_confirmed_at", "payment_escalation_level", "updated_at",
    ])
    messages.success(request, f"Оплату замовлення #{order_id} підтверджено.")
    return redirect("waiter:senior_dashboard")
```

## Шаблон orders/senior_waiter_dashboard.html

```html
<h1>Ескальовані несплачені замовлення</h1>

{% if not orders_with_age %}
<p class="text-success">✓ Немає проблемних замовлень</p>
{% endif %}

{% for item in orders_with_age %}
<div class="card {% if item.escalation_level >= 2 %}border-danger{% else %}border-warning{% endif %}">
    <div class="card-header">
        <strong>Замовлення #{{ item.order.id }}</strong>
        <span class="badge {% if item.escalation_level >= 2 %}bg-danger{% else %}bg-warning{% endif %}">
            {% if item.escalation_level >= 2 %}
                🔴 Менеджер
            {% else %}
                🟡 Старший офіціант
            {% endif %}
        </span>
        <span>Доставлено {{ item.minutes_since_delivery }} хв тому</span>
    </div>
    <div class="card-body">
        <p>Офіціант: {{ item.order.waiter.get_full_name }}</p>
        <p>Сума: €{{ item.order.total_price }}</p>

        <form method="post" action="{% url 'waiter:senior_confirm_payment' item.order.id %}">
            {% csrf_token %}
            <select name="payment_type">
                <option value="cash">Готівка</option>
                <option value="online">Онлайн</option>
            </select>
            <button type="submit" class="btn btn-success">Підтвердити оплату</button>
        </form>
    </div>
</div>
{% endfor %}
```

## Тести

```python
# orders/tests/test_senior_waiter.py
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.tier2
@pytest.mark.django_db
def test_senior_dashboard_shows_escalated(client, django_user_model):
    from orders.models import Order

    senior = django_user_model.objects.create_user(
        email="sw@test.com", password="pass", role="senior_waiter"
    )
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    old_time = timezone.now() - timedelta(minutes=20)

    escalated = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
        payment_escalation_level=1,
    )
    Order.objects.filter(pk=escalated.pk).update(delivered_at=old_time)

    not_escalated = Order.objects.create(
        waiter=waiter,
        status=Order.Status.DELIVERED,
        payment_status=Order.PaymentStatus.UNPAID,
        payment_escalation_level=0,
    )

    client.force_login(senior)
    response = client.get("/order/waiter/senior/")
    assert response.status_code == 200
    orders_shown = [item["order"] for item in response.context["orders_with_age"]]
    assert escalated in orders_shown
    assert not_escalated not in orders_shown


@pytest.mark.tier2
@pytest.mark.django_db
def test_regular_waiter_cannot_access_senior_dashboard(client, django_user_model):
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    client.force_login(waiter)
    response = client.get("/order/waiter/senior/")
    assert response.status_code == 403
```

## Acceptance criteria

- [ ] Senior dashboard — тільки `payment_escalation_level >= 1`
- [ ] Regular waiter → 403 при доступі до senior dashboard
- [ ] Senior може підтвердити готівку або онлайн за будь-яке замовлення
- [ ] Після підтвердження — замовлення зникає з ескальованих
- [ ] Тести зелені
