# Sprint 4 — Real-time (SSE)

## Board

**Мета:** live-оновлення без перезавантаження сторінки для кухні, офіціанта і менеджера.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 3 завершений

| # | Назва | Оцінка |
|---|---|---|
| 4.1 | SSE view і підписка клієнта | 2 год |
| 4.2 | Push-події з сервісів | 2 год |
| 4.3 | JS клієнт — обробка подій і оновлення DOM | 2.5 год |
| 4.4 | Reconnect і стабільність на слабкому 3G | 1.5 год |

---

## Детально для виконавця

### Які події пушимо

| Подія | Канал | Тригер |
|---|---|---|
| `order_approved` | `kitchen-{id}` | approve_order() |
| `ticket_taken` | `waiter-{waiter_id}` | take_ticket() |
| `ticket_done` | `waiter-{waiter_id}` | mark_ticket_done() |
| `order_ready` | `waiter-{waiter_id}` | всі ticket DONE |
| `kitchen_escalation` | `kitchen-supervisor-{id}`, `manager` | escalate task |
| `payment_escalation` | `waiter-senior-{id}`, `manager` | escalate task |

### Мінімальний payload (стабільність на 3G)

```json
{"type": "ticket_done", "ticket_id": 42, "order_id": 7, "dish": "Борщ"}
```

Тільки IDs і мінімум тексту. Клієнт оновлює конкретний елемент DOM, не перезавантажує сторінку.

### Definition of Done

- [ ] SSE endpoint `/events/<channel>/` — authenticated, 200
- [ ] Кожен сервісний виклик (approve, take, done) пушить відповідну подію
- [ ] JS клієнт підключається, обробляє події, оновлює DOM без reload
- [ ] Reconnect автоматичний (вбудований в EventSource браузера + наш обробник)
- [ ] Payload кожної події < 200 байт
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені
