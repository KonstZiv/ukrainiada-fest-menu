# Sprint 9 — Live Order Tracking для відвідувача

## Board

**Мета:** відвідувач бачить в реальному часі, хто готує кожну страву, коли вона готова, і коли офіціант несе замовлення. Персоналізовані повідомлення з іменами та посадами staff.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 8 завершений (display_title, access_token)
**Пріоритет:** 🟡 Високий — ключова фіча інтерактивності

| # | Назва | Оцінка |
|---|---|---|
| 9.1 | SSE-канал для відвідувача + авторизація | 2 год |
| 9.2 | Push-події на visitor channel при зміні тікетів | 2 год |
| 9.3 | order_detail: live UI з JS-клієнтом | 2.5 год |
| 9.4 | Візуальний timeline прогресу замовлення | 2 год |

---

## Архітектура

### SSE-канал для відвідувача

```
visitor-order-{order_id}
```

Чому по `order_id`, а не по `user_id`:
1. Анонімні відвідувачі не мають `user_id`
2. Один канал = одне замовлення = простіший payload
3. Канал "живе" від submit до delivery+payment — потім можна закрити

**Авторизація SSE:** django-eventstream підтримує `channels_for_user`. Для visitor каналу — перевірка через session token або access_token у query string.

### Які події пушимо відвідувачу

| Подія | Тригер | Payload |
|---|---|---|
| `ticket_taken` | Кухар взяв тікет | `{dish, cook_label, ticket_id}` |
| `ticket_done` | Страва готова | `{dish, cook_label, ticket_id}` |
| `order_ready` | Всі страви готові | `{order_id}` |
| `order_collecting` | Офіціант забрав страви | `{waiter_label}` |
| `order_delivered` | Замовлення доставлено | `{order_id}` |
| `status_changed` | Будь-яка зміна статусу | `{status, status_display}` |

**Payload мінімальний** (<200 байт) — лише те, що потрібно для оновлення DOM.

### Приклад повідомлень для відвідувача

```
Замовлення #42 — прийнято офіціантом ✓
├── 🕐 Борщ — в черзі
├── 👩‍🍳 Повариха Валентина готує ваші вареники
├── ✅ Чай готовий — чекає офіціанта
└── 🏃 Офіціант Дмитро збирає ваше замовлення!
```

---

## Детально для виконавця

### 9.1 — SSE-канал + авторизація

Новий канал `visitor-order-{order_id}`.

**notifications/channels.py:**
```python
def visitor_order_channel(order_id: int) -> str:
    return f"visitor-order-{order_id}"
```

**Авторизація SSE для відвідувача:**
django-eventstream перевіряє доступ через `EVENTSTREAM_ALLOW_ORIGIN` або middleware. Для visitor — перевірка session або token:

```python
# notifications/views.py або middleware
def can_subscribe_visitor_channel(request, channel_name):
    """Allow visitor to subscribe only to their own order channel."""
    if not channel_name.startswith("visitor-order-"):
        return True  # інші канали — стандартна логіка
    order_id = int(channel_name.split("-")[-1])
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return False
    return can_access_order(request, order)
```

### 9.2 — Push-події

Розширити існуючі сервісні функції в `kitchen/services.py` і `orders/services.py`:

```python
# kitchen/services.py — take_ticket(), після збереження:
from notifications.events import push_visitor_ticket_update

push_visitor_ticket_update(
    order_id=ticket.order_item.order_id,
    event_type="ticket_taken",
    data={
        "ticket_id": ticket.pk,
        "dish": ticket.order_item.dish.title[:40],
        "cook_label": kitchen_user.staff_label,
    },
)
```

Аналогічно для `mark_ticket_done`, `deliver_order`, `approve_order`.

**notifications/events.py — нові функції:**
```python
def push_visitor_ticket_update(order_id: int, event_type: str, data: dict) -> None:
    """Push ticket status update to visitor watching this order."""
    _push(visitor_order_channel(order_id), event_type, data)

def push_visitor_order_update(order_id: int, event_type: str, data: dict) -> None:
    """Push order-level update to visitor."""
    _push(visitor_order_channel(order_id), event_type, data)
```

### 9.3 — JS-клієнт для order_detail

```javascript
// staticfiles/js/order_tracker.js

class OrderTracker {
    constructor(orderId, accessToken) {
        this.orderId = orderId;
        this.accessToken = accessToken;
        this.connect();
    }

    connect() {
        const url = `/events/visitor-order-${this.orderId}/`;
        // accessToken для авторизації — через cookie або query
        this.source = new EventSource(url);
        this.source.onmessage = (e) => this.handleEvent(JSON.parse(e.data));
        this.source.onerror = () => this.reconnect();
    }

    handleEvent(data) {
        switch(data.type) {
            case 'ticket_taken':
                this.updateTicketStatus(data.ticket_id, 'cooking', data.cook_label, data.dish);
                break;
            case 'ticket_done':
                this.updateTicketStatus(data.ticket_id, 'ready', data.cook_label, data.dish);
                break;
            case 'order_ready':
                this.showOrderReady();
                break;
            case 'order_collecting':
                this.showCollecting(data.waiter_label);
                break;
            case 'order_delivered':
                this.showDelivered();
                break;
        }
    }

    updateTicketStatus(ticketId, status, cookLabel, dish) {
        const el = document.querySelector(`[data-ticket-id="${ticketId}"]`);
        if (!el) return;
        // Оновити іконку, текст, анімація
        ...
    }
}
```

### 9.4 — Візуальний timeline

Вертикальний timeline на `order_detail.html`:

```
[●] Замовлення створено — 14:23
[●] Офіціант прийняв — 14:25
[◐] Готується...
    ├── 👩‍🍳 Повариха Валентина: Борщ
    ├── ⏳ Вареники — в черзі
    └── ✅ Чай — готовий
[○] Збирається
[○] Доставляється
```

CSS анімація для поточного кроку (пульсація). Кольори: зелений (done), жовтий (in progress), сірий (pending).

---

## Обробка edge cases

1. **Сторінку відкрили після деяких подій** — початковий стан рендериться сервером (SSR), JS підхоплює тільки нові події
2. **Відвідувач закрив і відкрив сторінку** — SSR показує поточний стан, SSE підключається заново
3. **Мережа пропала** — `offline_detector.js` показує banner, SSE reconnect автоматичний
4. **Замовлення доставлено** — SSE-з'єднання можна закрити, показати фінальний стан + посилання на відгук (Sprint 11)

---

## Definition of Done

- [ ] SSE-канал `visitor-order-{id}` — створюється, авторизується
- [ ] Кожна зміна тікета пушить подію відвідувачу з `staff_label`
- [ ] `order_detail.html` — live timeline з JS-клієнтом
- [ ] Timeline показує поточний стан кожної страви з іменем кухаря
- [ ] Reconnect працює при втраті мережі
- [ ] Payload кожної події < 200 байт
- [ ] Початковий стан рендериться сервером (працює без JS)
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені

## Відкладено

- [ ] Push notifications (Web Push API) — коли order_ready, навіть якщо вкладка закрита
- [ ] Звукове оповіщення при зміні статусу
- [ ] Estimated time — "ваше замовлення буде готове через ~10 хвилин" (потребує ML або статистику)
- [ ] Анімований progress bar (% готовності = done_tickets / total_tickets)
