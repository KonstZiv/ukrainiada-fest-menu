# Task 8.2 — Безпека доступу до замовлень (access token)

## Мета

Захистити `order_detail`, `order_qr`, `order_pay_online` від несанкціонованого доступу. Зараз будь-хто, знаючи `order_id`, бачить чуже замовлення.

## Що робити

### 1. Міграція: `Order.access_token`

```python
# orders/migrations/0004_add_access_token.py

import uuid
from django.db import migrations, models

def populate_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(access_token__isnull=True):
        order.access_token = uuid.uuid4()
        order.save(update_fields=["access_token"])

class Migration(migrations.Migration):
    dependencies = [("orders", "0003_increase_payment_method_max_length")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(null=True, unique=True, db_index=True),
        ),
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False),
        ),
    ]
```

### 2. Session-based tracking

```python
# orders/services.py — в submit_order_from_cart(), після створення order:

# Store token in session for anonymous access
if "my_orders" not in request.session:
    request.session["my_orders"] = {}
request.session["my_orders"][str(order.id)] = str(order.access_token)
request.session.modified = True
```

### 3. Helper для перевірки доступу

```python
# orders/services.py

def can_access_order(request: HttpRequest, order: Order) -> bool:
    """Check if the current user/session has access to this order.

    Access granted if:
    1. User is authenticated AND is the order's visitor, OR
    2. User is staff (waiter/kitchen/manager), OR
    3. Session contains matching access_token, OR
    4. GET parameter 'token' matches order.access_token.
    """
    # Staff always has access
    if request.user.is_authenticated and request.user.role != "visitor":
        return True

    # Owner access
    if request.user.is_authenticated and order.visitor_id == request.user.id:
        return True

    # Session token
    session_orders = request.session.get("my_orders", {})
    if session_orders.get(str(order.id)) == str(order.access_token):
        return True

    # URL token
    url_token = request.GET.get("token", "")
    if url_token and str(order.access_token) == url_token:
        return True

    return False
```

### 4. Оновити views

```python
# orders/views.py — order_detail, order_qr, order_pay_online

def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.prefetch_related("items__dish"),
        pk=order_id,
    )
    if not can_access_order(request, order):
        return HttpResponse("Доступ заборонено", status=403)
    ...
```

Аналогічно для `order_qr` і `order_pay_online`.

### 5. QR-код з token

В `order_detail.html` — QR тепер містить URL з token:

```python
# orders/views.py — order_qr
scan_url = request.build_absolute_uri(
    reverse("waiter:order_scan", args=[order.id])
)
# QR для офіціанта — без token (waiter має role-based доступ)
```

Для sharing URL відвідувачем (показати другу):
```
/order/42/detail/?token=550e8400-e29b-41d4-a716-446655440000
```

## Тести

### Tier 1

```python
@pytest.mark.tier1
class TestOrderAccessToken:
    def test_token_auto_generated(self):
        """Order.access_token is auto-generated UUID."""
        ...

    def test_can_access_own_order(self):
        """Authenticated visitor can access own order."""
        ...

    def test_cannot_access_other_order(self):
        """Authenticated visitor cannot access another's order."""
        ...

    def test_session_token_grants_access(self):
        """Anonymous with matching session token can access."""
        ...

    def test_url_token_grants_access(self):
        """Anonymous with correct ?token= can access."""
        ...

    def test_staff_always_has_access(self):
        """Waiter/kitchen/manager can access any order."""
        ...
```

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
class TestOrderDetailSecurity:
    def test_anonymous_without_token_403(self, client):
        """GET /order/N/detail/ without token → 403."""
        ...

    def test_anonymous_with_token_200(self, client):
        """GET /order/N/detail/?token=... → 200."""
        ...
```

## Оцінка: 2.5 години

## Acceptance Criteria

- [ ] `Order.access_token` — UUID, auto-generated, unique, indexed
- [ ] Існуючі замовлення отримують token через data migration
- [ ] `order_detail` повертає 403 для неавторизованого доступу
- [ ] Session-based і URL-based token працюють
- [ ] Staff (waiter/kitchen/manager) мають доступ до всіх замовлень
- [ ] Тести tier1 + tier2 — зелені
