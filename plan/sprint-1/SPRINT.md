# Sprint 1 — Модель замовлення

## Board

**Мета:** ядро доменної логіки — Order, OrderItem, KitchenAssignment.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 0 завершений
**Результат:** відвідувач формує замовлення, офіціант підтверджує, kitchen tickets створені.

| # | Назва | Оцінка |
|---|---|---|
| 1.1 | Модель Order і OrderItem | 2 год |
| 1.2 | KitchenAssignment і KitchenTicket | 1.5 год |
| 1.3 | Visitor flow — меню і кошик | 2 год |
| 1.4 | QR-код для передачі замовлення офіціанту | 1 год |
| 1.5 | Waiter flow — перегляд і підтвердження | 2 год |

---

## Детально для виконавця

### Вхідні дані
Sprint 0 завершений: PostgreSQL, Celery, SSE-інфраструктура, 6 ролей, `Dish.availability`.

### Архітектурні рішення спрінту

**Кошик** — в Django session. Відвідувач не зобов'язаний мати акаунт.
**QR-код** — містить URL `/waiter/order/<id>/scan/`. Бібліотека `qrcode[pil]`.
**approve** — атомарна операція: `Order.status=APPROVED` + створення `KitchenTicket` для кожного `OrderItem`.
**Бізнес-логіка** — в `orders/services.py` і `kitchen/services.py`, НЕ у views.

### Порядок виконання
1.1 → 1.2 → 1.3 → 1.4 → 1.5. Кожна задача — окремий commit `[S1.N]`.

### Definition of Done
- [ ] `Order`, `OrderItem` — в БД, міграції застосовані
- [ ] `KitchenAssignment`, `KitchenTicket` — в БД
- [ ] Відвідувач: додати страву в кошик (сесія), сформувати замовлення (`DRAFT`)
- [ ] Відвідувач: бачить QR-код і номер замовлення після submit
- [ ] Офіціант: відкриває замовлення по QR або номеру, підтверджує (`APPROVED`)
- [ ] Після approve: `KitchenTicket` створені для кожного `OrderItem`
- [ ] Permission: visitor/kitchen не можуть approve — 403
- [ ] `uv run pytest -m "tier1 or tier2"` — всі тести зелені
- [ ] `uv run ruff check .` і `uv run mypy .` — 0 помилок
