# Task 9.1 — SSE-канал для відвідувача + авторизація

## Мета

Створити SSE-канал `visitor-order-{order_id}`, через який відвідувач отримує live-оновлення свого замовлення. Авторизація — через session token або access_token.

## Що робити

### 1. Новий канал

```python
# notifications/channels.py

def visitor_order_channel(order_id: int) -> str:
    """Return visitor channel for a specific order."""
    return f"visitor-order-{order_id}"

def channels_for_user(user: User) -> list[str]:
    """Return list of SSE channels the user should subscribe to."""
    # ... існуючий код ...
    # Visitor-каналів тут НЕ додаємо — вони per-order, не per-user
    return [...]
```

### 2. Авторизація SSE-підписки

django-eventstream підтримує channel-level permission через `EVENTSTREAM_ALLOW_ORIGIN` або кастомну логіку.

**Варіант A (рекомендований):** Custom view для SSE endpoint відвідувача:

```python
# notifications/views.py

from django_eventstream import get_current_event_id
from django.http import StreamingHttpResponse

def visitor_sse_view(request, order_id):
    """SSE endpoint for visitor order tracking.

    Authorization: session token or ?token= parameter.
    """
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return HttpResponse(status=403)

    channel = visitor_order_channel(order_id)
    # Delegate to django-eventstream
    return events_view(request, channels=[channel])
```

**URL:**
```python
# notifications/urls.py
path("visitor/<int:order_id>/", visitor_sse_view, name="visitor_sse"),
```

**Варіант B:** Використати `EVENTSTREAM_CHANNELMANAGER` для глобальної перевірки (складніше, менш явно).

### 3. Інтеграція з order_detail

```html
<!-- templates/orders/order_detail.html -->
{% if order.status != 'delivered' and order.status != 'draft' %}
<script>
  const ORDER_ID = {{ order.id }};
  const SSE_URL = "{% url 'notifications:visitor_sse' order.id %}";
</script>
<script src="{% static 'js/order_tracker.js' %}" defer></script>
{% endif %}
```

SSE-з'єднання відкривається тільки для активних замовлень (не draft, не delivered).

### 4. Lifecycle каналу

- **Створення:** канал "існує" коли хтось підписується (django-eventstream lazy)
- **Закриття:** після `order_delivered` — сервер пушить фінальну подію, JS закриває `EventSource`
- **Timeout:** django-eventstream сам закриває idle з'єднання через `EVENTSTREAM_KEEPALIVE`

## Тести

### Tier 1

```python
@pytest.mark.tier1
def test_visitor_order_channel_format():
    assert visitor_order_channel(42) == "visitor-order-42"

@pytest.mark.tier1
def test_visitor_channel_not_in_user_channels():
    """channels_for_user() does not include visitor channels."""
    user = User(role="visitor")
    assert not any(
        c.startswith("visitor-order-") for c in channels_for_user(user)
    )
```

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_sse_endpoint_authorized(client, order_with_token):
    """Authorized visitor gets 200 from SSE endpoint."""
    ...

@pytest.mark.tier2
@pytest.mark.django_db
def test_visitor_sse_endpoint_unauthorized(client, other_order):
    """Unauthorized visitor gets 403 from SSE endpoint."""
    ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] `visitor-order-{id}` канал існує і працює
- [ ] SSE endpoint перевіряє access через `can_access_order`
- [ ] 403 для неавторизованих
- [ ] Keepalive кожні 15 секунд
- [ ] SSE не відкривається для draft і delivered замовлень
- [ ] Тести зелені
