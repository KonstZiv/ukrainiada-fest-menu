# Task 4.2 — Push-події з сервісів (детально)

## Принцип

Кожна зміна стану — пушимо подію в потрібний канал.
Payload — мінімальний (тільки IDs і критичний текст).

## notifications/events.py — розширити типізованими функціями

```python
from __future__ import annotations

from typing import Any
from django_eventstream import send_event
from notifications.channels import kitchen_channel, waiter_channel, manager_channel


def _push(channel: str, event_type: str, data: dict[str, Any]) -> None:
    """Внутрішній helper. Ніколи не кидає виключення — логуємо і йдемо далі."""
    try:
        send_event(channel, "message", {"type": event_type, **data})
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("notifications").warning(
            "SSE push failed: channel=%s type=%s error=%s", channel, event_type, e
        )


def push_order_approved(order_id: int, waiter_id: int) -> None:
    """Нове замовлення зʼявилось у черзі кухні."""
    # Повідомляємо всіх кухарів — вони підписані на свій канал,
    # фільтрація по KitchenAssignment відбувається на стороні view
    # TODO Sprint 4: якщо кухарів багато — можна пушити тільки відповідним
    send_event("kitchen-broadcast", "message", {
        "type": "order_approved",
        "order_id": order_id,
    })


def push_ticket_taken(ticket_id: int, waiter_id: int, kitchen_user_name: str) -> None:
    """Офіціанту: хтось взяв його страву в роботу."""
    _push(waiter_channel(waiter_id), "ticket_taken", {
        "ticket_id": ticket_id,
        "by": kitchen_user_name,
    })


def push_ticket_done(ticket_id: int, order_id: int, waiter_id: int, dish_title: str) -> None:
    """Офіціанту: страва готова."""
    _push(waiter_channel(waiter_id), "ticket_done", {
        "ticket_id": ticket_id,
        "order_id": order_id,
        "dish": dish_title[:40],  # обрізаємо для мінімального payload
    })


def push_order_ready(order_id: int, waiter_id: int) -> None:
    """Офіціанту: всі страви замовлення готові."""
    _push(waiter_channel(waiter_id), "order_ready", {
        "order_id": order_id,
    })


def push_kitchen_escalation(ticket_id: int, level: int) -> None:
    """Ескалація тікету до supervisor або manager."""
    _push(manager_channel(), "kitchen_escalation", {
        "ticket_id": ticket_id,
        "level": level,
    })


def push_payment_escalation(order_id: int, level: int) -> None:
    """Ескалація несплаченого замовлення."""
    _push(manager_channel(), "payment_escalation", {
        "order_id": order_id,
        "level": level,
    })
```

## Вбудовуємо push у сервіси

```python
# orders/services.py — approve_order — додати після збереження
from notifications.events import push_order_approved

def approve_order(order, waiter):
    with transaction.atomic():
        # ... існуючий код ...
        pass
    # push ПІСЛЯ транзакції — щоб не пушити якщо транзакція відкотилась
    push_order_approved(order_id=order.id, waiter_id=waiter.id)
    return order


# kitchen/services.py — mark_ticket_done — додати
from notifications.events import push_ticket_done, push_order_ready

def mark_ticket_done(ticket, kitchen_user):
    # ... існуючий код ...
    waiter_id = ticket.order_item.order.waiter_id
    push_ticket_done(
        ticket_id=ticket.id,
        order_id=ticket.order_item.order_id,
        waiter_id=waiter_id,
        dish_title=ticket.order_item.dish.title,
    )
    if order_just_became_ready:  # перевіряємо _check_order_ready
        push_order_ready(order_id=ticket.order_item.order_id, waiter_id=waiter_id)
    return ticket
```

## Тести

```python
# notifications/tests/test_events.py
import pytest
from unittest.mock import patch, call


@pytest.mark.tier1
def test_push_ticket_done_calls_send_event():
    from notifications.events import push_ticket_done
    with patch("notifications.events.send_event") as mock_send:
        push_ticket_done(
            ticket_id=1, order_id=2, waiter_id=3, dish_title="Борщ"
        )
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert args[0][0] == "waiter-3"  # правильний канал
        data = args[0][2]
        assert data["type"] == "ticket_done"
        assert data["order_id"] == 2


@pytest.mark.tier1
def test_push_does_not_raise_on_error():
    """SSE push не повинен ламати основний flow при помилці."""
    from notifications.events import push_ticket_done
    with patch("notifications.events.send_event", side_effect=Exception("Redis down")):
        # Не повинно кинути виключення
        push_ticket_done(ticket_id=1, order_id=2, waiter_id=3, dish_title="Test")


@pytest.mark.tier1
def test_dish_title_truncated_to_40_chars():
    from notifications.events import push_ticket_done
    with patch("notifications.events.send_event") as mock_send:
        long_title = "A" * 100
        push_ticket_done(ticket_id=1, order_id=2, waiter_id=3, dish_title=long_title)
        data = mock_send.call_args[0][2]
        assert len(data["dish"]) <= 40
```

## Acceptance criteria

- [ ] Всі push-функції в `notifications/events.py` з type annotations
- [ ] Push відбувається ПІСЛЯ транзакції (не всередині `with transaction.atomic()`)
- [ ] SSE push ніколи не кидає виключення — логуємо і продовжуємо
- [ ] Payload кожної події ≤ 200 байт (перевірити через `len(json.dumps(data))`)
- [ ] Тести зелені (мокуємо `send_event`)
