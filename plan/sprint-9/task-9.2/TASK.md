# Task 9.2 — Push-події на visitor channel при зміні тікетів

## Мета

Кожна зміна стану KitchenTicket та Order пушить подію на visitor SSE-канал з `staff_label` кухаря/офіціанта.

## Що робити

### 1. Нові push-функції

```python
# notifications/events.py

from notifications.channels import visitor_order_channel

def push_visitor_ticket_update(
    order_id: int, event_type: str, data: dict[str, Any]
) -> None:
    """Push ticket status update to visitor watching this order."""
    _push(visitor_order_channel(order_id), event_type, data)
```

### 2. Інтеграція в kitchen/services.py

**`take_ticket()` — після збереження:**
```python
# Існуючий push для waiter
push_ticket_taken(ticket_id=ticket.pk, waiter_id=waiter_id, ...)

# НОВИЙ push для visitor
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

**`mark_ticket_done()` — після збереження:**
```python
push_visitor_ticket_update(
    order_id=ticket.order_item.order_id,
    event_type="ticket_done",
    data={
        "ticket_id": ticket.pk,
        "dish": ticket.order_item.dish.title[:40],
        "cook_label": kitchen_user.staff_label,
    },
)
```

**`_check_order_ready()` — коли всі тікети DONE:**
```python
if all_done:
    push_visitor_ticket_update(
        order_id=order.id,
        event_type="order_ready",
        data={"order_id": order.id},
    )
```

### 3. Інтеграція в orders/services.py

**`approve_order()` — після commit:**
```python
push_visitor_ticket_update(
    order_id=order.id,
    event_type="order_approved",
    data={
        "order_id": order.id,
        "waiter_label": waiter.staff_label,
    },
)
```

**`deliver_order()` — після збереження:**
```python
push_visitor_ticket_update(
    order_id=order.id,
    event_type="order_delivered",
    data={
        "order_id": order.id,
        "waiter_label": waiter.staff_label,
    },
)
```

### 4. Handoff push — коли офіціант підтверджує прийом страв

В `waiter_views.py::handoff_confirm_view()` після confirm:
```python
from notifications.events import push_visitor_ticket_update

push_visitor_ticket_update(
    order_id=handoff.ticket.order_item.order_id,
    event_type="dish_collecting",
    data={
        "ticket_id": handoff.ticket.pk,
        "dish": handoff.ticket.order_item.dish.title[:40],
        "waiter_label": request.user.staff_label,
    },
)
```

### 5. Повний список подій для visitor

| event_type | Коли | Payload |
|---|---|---|
| `order_approved` | Офіціант підтвердив | `{order_id, waiter_label}` |
| `ticket_taken` | Кухар взяв страву | `{ticket_id, dish, cook_label}` |
| `ticket_done` | Страва готова | `{ticket_id, dish, cook_label}` |
| `order_ready` | Всі страви готові | `{order_id}` |
| `dish_collecting` | Офіціант забрав страву | `{ticket_id, dish, waiter_label}` |
| `order_delivered` | Замовлення доставлено | `{order_id, waiter_label}` |

## Тести

### Tier 1

```python
@pytest.mark.tier1
def test_take_ticket_pushes_visitor_event(mocker):
    """take_ticket() calls push_visitor_ticket_update."""
    mock_push = mocker.patch("kitchen.services.push_visitor_ticket_update")
    ...
    assert mock_push.called
    call_args = mock_push.call_args
    assert call_args[1]["event_type"] == "ticket_taken"
    assert "cook_label" in call_args[1]["data"]

@pytest.mark.tier1
def test_visitor_event_payload_size():
    """Visitor event payload < 200 bytes."""
    import json
    payload = {"type": "ticket_taken", "ticket_id": 42, "dish": "Борщ", "cook_label": "Повариха Валентина"}
    assert len(json.dumps(payload).encode()) < 200
```

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
def test_full_pipeline_visitor_events(mocker):
    """Full order pipeline pushes all expected visitor events."""
    events = []
    mocker.patch(
        "notifications.events.push_visitor_ticket_update",
        side_effect=lambda **kw: events.append(kw),
    )
    # approve → take → done → deliver
    ...
    event_types = [e["event_type"] for e in events]
    assert "order_approved" in event_types
    assert "ticket_taken" in event_types
    assert "ticket_done" in event_types
    assert "order_delivered" in event_types
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Всі 6 типів подій пушаться на visitor channel
- [ ] `staff_label` використовується замість `get_full_name()`
- [ ] Payload < 200 байт для кожної події
- [ ] Push відбувається ПІСЛЯ успішної транзакції
- [ ] Тести tier1 + tier2 — зелені
