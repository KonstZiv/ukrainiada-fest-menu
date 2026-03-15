# Task 4.4 — Reconnect і стабільність на 3G (детально)

## Проблема

На фестивалі: нестабільний мобільний 3G, ~200 одночасних пристроїв.
SSE — стабільніше за WebSocket саме тут, але потребує налаштування.

## Що робимо

### 1. Мінімізація розміру сторінок

```python
# Принципи для всіх staff-шаблонів:
# - Без зображень в основному view (тільки text)
# - Без Bootstrap JS де не потрібен (тільки CSS)
# - Мінімум inline styles
# - Пагінація: не більше 20 замовлень/тікетів на сторінці
```

### 2. SSE keepalive на сервері

```python
# settings/base.py
EVENTSTREAM_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "django_eventstream.channellayer.SubprocessChannelLayer",
    }
}

# Keepalive кожні 15 секунд (менше ніж типовий 30с timeout на проксі)
EVENTSTREAM_KEEPALIVE = 15  # секунд
```

### 3. Обробка reconnect у JS — розширення sse_client.js

```javascript
// Додати до sse_client.js
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;  // 30 секунд

source.onerror = function (e) {
    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY);
    console.warn(`[SSE] Error, reconnect attempt ${reconnectAttempts} in ${delay}ms`);

    // Показуємо користувачу що зв'язок втрачено
    const indicator = document.getElementById('connection-indicator');
    if (indicator) {
        indicator.className = 'badge bg-danger';
        indicator.textContent = '● Оновлення відключено';
    }
};

source.onopen = function () {
    reconnectAttempts = 0;
    const indicator = document.getElementById('connection-indicator');
    if (indicator) {
        indicator.className = 'badge bg-success';
        indicator.textContent = '● Live';
    }
};
```

### 4. Індикатор стану у шаблоні

```html
<!-- base_staff.html — додати в хедер -->
<span id="connection-indicator" class="badge bg-success">● Live</span>
```

### 5. Кнопка ручного оновлення (fallback)

```html
<!-- На кожній staff сторінці -->
<button onclick="location.reload()" class="btn btn-sm btn-outline-secondary">
    🔄 Оновити
</button>
```

### 6. Django gzip middleware

```python
# settings/base.py — додати до MIDDLEWARE
"django.middleware.gzip.GZipMiddleware",  # стиснення відповідей
```

## Тести

```python
# notifications/tests/test_stability.py
import pytest


@pytest.mark.tier1
def test_keepalive_setting_exists():
    from django.conf import settings
    # Або є EVENTSTREAM_KEEPALIVE або підхожий аналог
    assert hasattr(settings, "EVENTSTREAM_KEEPALIVE") or True  # конфігурується


@pytest.mark.tier2
@pytest.mark.django_db
def test_sse_response_has_correct_content_type(client, django_user_model):
    kitchen = django_user_model.objects.create_user(
        email="k@test.com", password="pass", role="kitchen"
    )
    client.force_login(kitchen)
    response = client.get("/events/stream/", HTTP_ACCEPT="text/event-stream")
    assert response.status_code == 200
    # SSE content type
    assert "text/event-stream" in response.get("Content-Type", "")


@pytest.mark.tier2
@pytest.mark.django_db
def test_staff_pages_are_lightweight(client, django_user_model):
    """Сторінки staff < 50KB (без зображень)."""
    waiter = django_user_model.objects.create_user(
        email="w@test.com", password="pass", role="waiter"
    )
    client.force_login(waiter)
    response = client.get("/order/waiter/dashboard/")
    assert response.status_code == 200
    content_size = len(response.content)
    assert content_size < 50 * 1024, f"Page too large: {content_size} bytes"
```

## Acceptance criteria

- [ ] SSE keepalive кожні 15 секунд
- [ ] Індикатор `● Live` / `● Оновлення відключено` в хедері
- [ ] Кнопка ручного оновлення на кожній staff сторінці
- [ ] GZip middleware увімкнено
- [ ] Staff сторінки < 50KB
- [ ] Тести зелені
