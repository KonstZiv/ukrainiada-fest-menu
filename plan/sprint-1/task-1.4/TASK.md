# Task 1.4 — QR-код (детально)

## Залежність

```toml
# pyproject.toml
dependencies = [
    ...
    "qrcode[pil]",
]
```

## Підхід

QR генерується на сервері як PNG і повертається як `image/png`.
QR містить абсолютний URL: `https://<host>/waiter/order/<id>/scan/`
Офіціант сканує → відкривається сторінка замовлення на його пристрої.

На сторінці підтвердження замовлення — завжди дублюємо номер текстом (fallback для відвідувачів без телефону або при поганому сканері).

## orders/views.py — додати

```python
import io
import qrcode
from django.http import HttpResponse, HttpRequest
from django.shortcuts import get_object_or_404
from orders.models import Order


def order_qr(request: HttpRequest, order_id: int) -> HttpResponse:
    """Генерує QR-код PNG для замовлення.

    QR містить URL для сканування офіціантом.
    Доступний лише для DRAFT замовлень (ще не прийнятих офіціантом).
    """
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.DRAFT)

    scan_url = request.build_absolute_uri(f"/waiter/order/{order_id}/scan/")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")
```

## Шаблон orders/order_detail.html (ключова частина)

```html
{% if order.status == 'draft' %}
<div class="qr-section">
    <h2>Покажіть офіціанту</h2>

    <!-- QR-код -->
    <img src="{% url 'orders:order_qr' order.id %}"
         alt="QR замовлення #{{ order.id }}"
         width="256" height="256"
         loading="eager">

    <!-- Fallback: номер текстом — завжди видимий -->
    <p class="order-number">
        Або назвіть номер: <strong>#{{ order.id }}</strong>
    </p>
</div>
{% endif %}
```

## Мінімізація payload

На фестивалі може бути слабкий 3G. QR-зображення:
- `box_size=8` → невеликий розмір PNG (~3-5KB для короткого URL)
- Без зайвих метаданих
- `loading="eager"` — завантажуємо одразу (не lazy)

## Тести

```python
# orders/tests/test_qr.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_order_qr_returns_png(client):
    from orders.models import Order
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"


@pytest.mark.tier2
@pytest.mark.django_db
def test_order_qr_not_available_for_approved(client):
    from orders.models import Order
    order = Order.objects.create(status=Order.Status.APPROVED)
    response = client.get(f"/order/{order.id}/qr/")
    assert response.status_code == 404


@pytest.mark.tier2
@pytest.mark.django_db
def test_order_qr_response_is_valid_png(client):
    from orders.models import Order
    import io
    from PIL import Image
    order = Order.objects.create(status=Order.Status.DRAFT)
    response = client.get(f"/order/{order.id}/qr/")
    img = Image.open(io.BytesIO(response.content))
    assert img.format == "PNG"
```

## Acceptance criteria

- [ ] `GET /order/<id>/qr/` → 200, `Content-Type: image/png`
- [ ] QR для `APPROVED` замовлення → 404
- [ ] Сторінка замовлення показує QR і номер текстом одночасно
- [ ] PNG розмір < 10KB для стандартного URL
- [ ] `uv run pytest -m tier2 orders/tests/test_qr.py` — зелені
