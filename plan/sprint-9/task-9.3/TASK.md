# Task 9.3 — order_detail: live UI з JS-клієнтом

## Мета

JS-клієнт `OrderTracker` слухає SSE і оновлює DOM на `order_detail.html` без перезавантаження.

## Що робити

### 1. Server-side rendering (initial state)

`order_detail` view повинен передати повний стан тікетів у template context:

```python
# orders/views.py — order_detail

def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items__dish",
            "items__kitchen_ticket",
            "items__kitchen_ticket__assigned_to",
        ),
        pk=order_id,
    )
    if not can_access_order(request, order):
        return HttpResponse(status=403)

    # Збагачення тікетів staff_label для SSR
    ticket_states = []
    for item in order.items.all():
        ticket = getattr(item, "kitchen_ticket", None)
        ticket_states.append({
            "item_id": item.id,
            "dish_title": item.dish.title,
            "quantity": item.quantity,
            "ticket_id": ticket.pk if ticket else None,
            "status": ticket.status if ticket else "pending",
            "cook_label": ticket.assigned_to.staff_label if ticket and ticket.assigned_to else None,
        })

    return render(request, "orders/order_detail.html", {
        "order": order,
        "ticket_states": ticket_states,
    })
```

### 2. Template: live tracking блок

```html
<!-- templates/orders/order_detail.html — всередині card-body -->

{% if order.status != 'draft' %}
<div id="order-tracker" class="mt-4">
  <h5>{% trans "Статус вашого замовлення" %}</h5>

  <div class="order-timeline">
    {% for ts in ticket_states %}
    <div class="ticket-status-row" data-ticket-id="{{ ts.ticket_id }}">
      <span class="ticket-icon" data-status="{{ ts.status }}">
        {% if ts.status == 'pending' %}⏳{% elif ts.status == 'taken' %}👩‍🍳{% elif ts.status == 'done' %}✅{% endif %}
      </span>
      <span class="ticket-dish">{{ ts.dish_title }} x{{ ts.quantity }}</span>
      <span class="ticket-detail">
        {% if ts.status == 'taken' and ts.cook_label %}
          {{ ts.cook_label }} {% trans "готує" %}
        {% elif ts.status == 'done' %}
          {% trans "Готово — чекає офіціанта" %}
        {% else %}
          {% trans "В черзі" %}
        {% endif %}
      </span>
    </div>
    {% endfor %}
  </div>

  <div id="order-global-status" class="mt-3 text-center d-none">
    <!-- JS заповнює при order_ready / order_delivered -->
  </div>
</div>
{% endif %}
```

### 3. JS-клієнт: order_tracker.js

```javascript
// staticfiles/js/order_tracker.js

class OrderTracker {
    constructor(orderId, sseUrl) {
        this.orderId = orderId;
        this.sseUrl = sseUrl;
        this.source = null;
        this.connect();
    }

    connect() {
        this.source = new EventSource(this.sseUrl);
        this.source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (e) {
                console.warn('OrderTracker: invalid event', e);
            }
        };
        this.source.onerror = () => {
            // EventSource auto-reconnects, just log
            console.info('OrderTracker: SSE reconnecting...');
        };
    }

    handleEvent(data) {
        switch (data.type) {
            case 'ticket_taken':
                this.setTicketStatus(data.ticket_id, 'taken', '👩‍🍳', `${data.cook_label} готує`);
                break;
            case 'ticket_done':
                this.setTicketStatus(data.ticket_id, 'done', '✅', 'Готово — чекає офіціанта');
                break;
            case 'dish_collecting':
                this.setTicketStatus(data.ticket_id, 'collecting', '🏃', `${data.waiter_label} забрав`);
                break;
            case 'order_ready':
                this.showGlobalMessage('🎉', 'Всі страви готові! Офіціант збирає замовлення.');
                break;
            case 'order_delivered':
                this.showGlobalMessage('✅', 'Замовлення доставлено! Смачного!');
                this.disconnect();
                break;
            case 'order_approved':
                this.showGlobalMessage('👍', `Офіціант ${data.waiter_label} прийняв замовлення`);
                break;
        }
    }

    setTicketStatus(ticketId, status, icon, text) {
        const row = document.querySelector(`[data-ticket-id="${ticketId}"]`);
        if (!row) return;
        const iconEl = row.querySelector('.ticket-icon');
        const detailEl = row.querySelector('.ticket-detail');
        if (iconEl) {
            iconEl.textContent = icon;
            iconEl.dataset.status = status;
        }
        if (detailEl) {
            detailEl.textContent = text;  // textContent, not innerHTML — XSS safe
        }
        // Pulse animation
        row.classList.add('status-updated');
        setTimeout(() => row.classList.remove('status-updated'), 2000);
    }

    showGlobalMessage(icon, text) {
        const el = document.getElementById('order-global-status');
        if (!el) return;
        el.textContent = `${icon} ${text}`;
        el.classList.remove('d-none');
        el.classList.add('animate-fade-in');
    }

    disconnect() {
        if (this.source) {
            this.source.close();
            this.source = null;
        }
    }
}

// Auto-init
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('order-tracker');
    if (!container) return;
    const orderId = parseInt(container.dataset.orderId, 10);
    const sseUrl = container.dataset.sseUrl;
    if (orderId && sseUrl) {
        window.orderTracker = new OrderTracker(orderId, sseUrl);
    }
});
```

### 4. CSS для tracking

```css
/* staticfiles/css/brand.css */

.ticket-status-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--bs-border-color);
    transition: background-color 0.3s;
}

.ticket-icon {
    font-size: 1.5rem;
    width: 2rem;
    text-align: center;
}

.ticket-icon[data-status="taken"] { animation: pulse-soft 2s infinite; }

.status-updated {
    background-color: rgba(25, 135, 84, 0.1);
}

@keyframes pulse-soft {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

.animate-fade-in {
    animation: fadeIn 0.5s ease-in;
}
```

## Graceful degradation

- **Без JS:** SSR показує поточний стан (повністю функціональна сторінка)
- **Без SSE:** Сторінка просто не оновлюється live — відвідувач може refresh
- **Повільна мережа:** Payload < 200 байт, keepalive 15с

## Тести

### Tier 1

```python
@pytest.mark.tier1
def test_order_detail_context_has_ticket_states():
    """order_detail view passes ticket_states to template."""
    ...
```

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
def test_order_detail_renders_ticket_rows(client, order_with_tickets):
    """order_detail template renders ticket-status-row for each item."""
    response = client.get(f"/order/{order.id}/detail/?token={order.access_token}")
    assert response.status_code == 200
    assert b'data-ticket-id' in response.content
```

## Оцінка: 2.5 години

## Acceptance Criteria

- [ ] order_detail передає ticket_states у context
- [ ] SSR рендерить кожну страву з поточним статусом
- [ ] JS OrderTracker підключається до SSE
- [ ] DOM оновлюється при отриманні подій (icon, text, animation)
- [ ] `textContent` замість `innerHTML` (XSS protection)
- [ ] Працює без JS (graceful degradation)
- [ ] Тести зелені
