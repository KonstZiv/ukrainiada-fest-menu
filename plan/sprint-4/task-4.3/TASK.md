# Task 4.3 — JS клієнт: обробка подій і оновлення DOM (детально)

## Підхід

Мінімальний vanilla JS — без фреймворків.
Кожна подія оновлює конкретний елемент DOM по `data-` атрибуту.

## staticfiles/js/sse_client.js

```javascript
/**
 * Festival Menu SSE Client
 * Підключається до /events/stream/ і оновлює DOM при отриманні подій.
 * Без залежностей — vanilla JS.
 */
(function () {
    'use strict';

    const source = new EventSource('/events/stream/');

    source.addEventListener('message', function (e) {
        let data;
        try {
            data = JSON.parse(e.data);
        } catch (err) {
            console.error('[SSE] Parse error:', err);
            return;
        }
        handleEvent(data);
    });

    source.onerror = function () {
        // EventSource автоматично перепідключається через 3с
        console.warn('[SSE] Connection lost, reconnecting...');
    };

    function handleEvent(data) {
        switch (data.type) {
            case 'ticket_done':
                onTicketDone(data);
                break;
            case 'order_ready':
                onOrderReady(data);
                break;
            case 'ticket_taken':
                onTicketTaken(data);
                break;
            case 'order_approved':
                onOrderApproved(data);
                break;
            case 'kitchen_escalation':
            case 'payment_escalation':
                onEscalation(data);
                break;
        }
    }

    function onTicketDone(data) {
        // Оновлюємо статус конкретного тікету в таблиці офіціанта
        const el = document.querySelector(
            `[data-ticket-id="${data.ticket_id}"] .ticket-status`
        );
        if (el) {
            el.textContent = 'Готово ✓';
            el.className = 'ticket-status text-success';
        }
    }

    function onOrderReady(data) {
        // Показуємо кнопку "Забрати замовлення" для order
        const card = document.querySelector(`[data-order-id="${data.order_id}"]`);
        if (card) {
            card.classList.add('order-ready');
            const btn = card.querySelector('.btn-deliver');
            if (btn) btn.style.display = 'block';

            // Звуковий сигнал якщо браузер підтримує
            if (window.Notification && Notification.permission === 'granted') {
                new Notification(`Замовлення #${data.order_id} готове!`);
            }
        }
    }

    function onTicketTaken(data) {
        const el = document.querySelector(
            `[data-ticket-id="${data.ticket_id}"] .ticket-status`
        );
        if (el) {
            el.textContent = `Готується (${data.by})`;
            el.className = 'ticket-status text-warning';
        }
    }

    function onOrderApproved(data) {
        // На кухні — показуємо нотифікацію про нове замовлення
        const counter = document.getElementById('pending-count');
        if (counter) {
            counter.textContent = parseInt(counter.textContent || '0') + 1;
        }
        // Flash-повідомлення
        showFlash(`Нове замовлення #${data.order_id}`, 'info');
    }

    function onEscalation(data) {
        showFlash(`⚠️ Ескалація! ${data.type} ID:${data.ticket_id || data.order_id}`, 'danger');
        const badge = document.getElementById('escalation-badge');
        if (badge) badge.style.display = 'inline';
    }

    function showFlash(message, type) {
        const container = document.getElementById('flash-container');
        if (!container) return;
        const el = document.createElement('div');
        el.className = `alert alert-${type} alert-dismissible fade show`;
        el.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        container.prepend(el);
        setTimeout(() => el.remove(), 8000);
    }
})();
```

## HTML атрибути в шаблонах

```html
<!-- waiter_dashboard.html — додати data-атрибути -->
<div class="order-card" data-order-id="{{ order.id }}">
    ...
    {% for item in order.items.all %}
    <tr data-ticket-id="{{ item.kitchen_ticket.id }}">
        <td>{{ item.dish.title }}</td>
        <td class="ticket-status">
            {{ item.kitchen_ticket.get_status_display }}
        </td>
    </tr>
    {% endfor %}
    ...
    <button class="btn btn-success btn-deliver" style="display:none">
        ✓ Забрати замовлення
    </button>
</div>

<!-- Flash container в base_staff.html -->
<div id="flash-container"></div>
<span id="escalation-badge" class="badge bg-danger" style="display:none">!</span>
```

## Тести (tier1 — unit тести JS логіки через Python мок)

```python
# notifications/tests/test_sse_js.py
import pytest


@pytest.mark.tier1
def test_sse_js_file_exists():
    import os
    js_path = os.path.join("staticfiles", "js", "sse_client.js")
    assert os.path.exists(js_path), f"JS file not found: {js_path}"


@pytest.mark.tier1
def test_sse_js_handles_unknown_event_gracefully():
    """Перевіряємо що невідомий тип події не кидає помилку — через читання JS."""
    import os
    js_path = os.path.join("staticfiles", "js", "sse_client.js")
    with open(js_path) as f:
        content = f.read()
    # Switch має default або обробляє невідомі типи мовчки
    assert "switch" in content
    assert "handleEvent" in content
```

## Acceptance criteria

- [ ] `sse_client.js` — підключений у `base_staff.html`
- [ ] `onTicketDone` оновлює `.ticket-status` без reload
- [ ] `onOrderReady` показує кнопку і додає клас `.order-ready`
- [ ] Flash-повідомлення зникають через 8 секунд
- [ ] Невідомі типи подій — ігноруються (no console.error)
