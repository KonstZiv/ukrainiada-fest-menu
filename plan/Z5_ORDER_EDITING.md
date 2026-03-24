# Z5: Edit/Cancel замовлення до верифікації

## Суть

Замовлення може бути змінено або скасовано **до верифікації** (поки тікети не пішли на кухню).

## Хто може

| Статус | Visitor (власник) | Waiter (призначений) |
|--------|:-:|:-:|
| SUBMITTED | edit + cancel | — |
| ACCEPTED | edit + cancel | edit + cancel |
| VERIFIED+ | — | — |

## Дії

### Edit (зміна кількості)
- Кожна позиція має кнопки `[−] [кількість] [+]`
- Кількість 0 → позиція видаляється
- Всі позиції видалені → замовлення скасовується
- Total перераховується
- SSE `order_updated` → waiter dashboards + visitor page

### Cancel (скасування)
- Кнопка "Скасувати замовлення"
- Новий статус: `CANCELLED`
- SSE `order_cancelled` → waiter dashboards (прибрати картку) + visitor page ("Скасовано")

## Backend

### Сервіси (`orders/services.py`)

```python
def update_order_items(order, changes: dict[int, int], actor: User) -> Order:
    """Update item quantities. changes = {item_id: new_qty}."""
    # Validate status, actor rights
    # Update quantities, delete zero-qty items
    # Recalculate total
    # Log OrderEvent
    # Push SSE order_updated
    # If empty → cancel_order()

def cancel_order(order, actor: User) -> Order:
    """Cancel order (set CANCELLED status)."""
    # Validate status
    # Set CANCELLED
    # Log OrderEvent
    # Push SSE order_cancelled
```

### Views

| URL | Метод | Хто | Що |
|-----|-------|-----|-----|
| `POST /order/<id>/edit/` | AJAX | Visitor (token) | Зміна кількості |
| `POST /order/<id>/cancel/` | AJAX | Visitor (token) | Скасування |
| `POST /waiter/order/<id>/edit-items/` | AJAX | Waiter | Зміна кількості |
| `POST /waiter/order/<id>/cancel/` | AJAX | Waiter | Скасування |

### SSE events (`notifications/events.py`)

```python
push_order_updated(order_id, items_summary, actor_label)
# → waiter-broadcast + visitor-order-{id}

push_order_cancelled(order_id, actor_label)
# → waiter-broadcast + visitor-order-{id}
```

### Model

- Додати `CANCELLED = "cancelled", "Скасовано"` до `Order.Status`

## Frontend

### Visitor order page (`order_detail.html`)
- `[−][qty][+]` per item (visible when status in SUBMITTED, ACCEPTED)
- "Скасувати замовлення" кнопка
- AJAX submit з debounce
- SSE handler `order_updated` → оновити items + total в DOM

### Waiter order detail (`waiter_order_detail.html`)
- Аналогічний UI коли status == ACCEPTED
- AJAX
- **Варіант B (Z10):** замінити `scheduleReload` на AJAX DOM-patch для waiter сторінок:
  - Додати `data-ticket-id` + `.ticket-status` до кожного item
  - Queryset: `prefetch_related('items__tickets')` для доступу до тікетів
  - Шаблон: показувати статус готування кожної страви (Черга/Готується/Готово)
  - JS: inline DOM-update замість reload (як у kitchen)
  - **UX-проблема**: reload закриває всі відкриті акордеони на дашборді — неприйнятно при кількох замовленнях. AJAX DOM-patch вирішує це повністю

### SSE handlers
- `sse_client.js`: `onOrderUpdated` — waiter dashboards (reload або DOM patch)
- `sse_client.js`: `onOrderCancelled` — waiter dashboards (remove card + badges)
- `order_tracker.js`: `onOrderUpdated` — visitor page (update items + total)
- `order_tracker.js`: `onOrderCancelled` — visitor page ("Скасовано", disconnect)

## Тести (~12)

### Visitor
- `test_visitor_edit_reduces_quantity` — qty 3→2, total recalculated
- `test_visitor_edit_removes_item` — qty→0, item deleted
- `test_visitor_edit_all_items_cancels_order` — all qty=0 → CANCELLED
- `test_visitor_edit_blocked_after_verified` — 403/400
- `test_visitor_cancel_submitted_order` — status → CANCELLED
- `test_visitor_cancel_blocked_after_verified` — 403/400

### Waiter
- `test_waiter_edit_accepted_order` — qty change works
- `test_waiter_edit_blocked_for_submitted` — only accepted
- `test_waiter_cancel_accepted_order` — status → CANCELLED

### SSE + Events
- `test_cancel_pushes_sse_event` — mock push_order_cancelled called
- `test_edit_pushes_sse_event` — mock push_order_updated called
- `test_edit_logs_order_event` — OrderEvent with change details

## Додатково: SSE архітектура review

Під час Z5 пройтись по структурі SSE цілісно:
- Як побудована "шина" (Redis pub-sub channels) — один `events_channel` з фільтрацією по logical channel vs окремі Redis channels
- Чи потрібно декілька шин (staff, visitor, manager)
- Контрольованість: які events ходять, хто підписаний, як дебажити
- Документація event flow (хто публікує → яка шина → хто слухає → що робить)
- Мета: підтримуваність і прозорість SSE інфраструктури

## Оцінка

1.5–2 робочі сесії.
