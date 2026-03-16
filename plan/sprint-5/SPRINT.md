# Sprint 5 — QR-флоу передачі страви

## Board

**Мета:** підтвердження передачі страви від кухні офіціанту через QR-код.
**Оцінка:** 6–8 годин
**Залежності:** Sprint 4 завершений
**Статус:** ✅ ЗАВЕРШЕНО, merged to main

| # | Назва | Оцінка | Статус |
|---|---|---|---|
| 5.1 | Кухня генерує QR для передачі офіціанту | 1.5 год | ✅ Done |
| 5.2 | Офіціант сканує QR і підтверджує прийом | 1.5 год | ✅ Done |
| 5.3 | Fallback: ручне підтвердження без QR | 1 год | ✅ Done |
| 5.4 | Офіціант вручну відмічає передачу відвідувачу | 1 год | ✅ Done |

---

## Що реалізовано

### Нова модель: `KitchenHandoff` (kitchen/models.py)
- UUID token (unique, db_indexed, auto-generated)
- OneToOneField → KitchenTicket
- ForeignKey → target_waiter (role-limited)
- `is_expired` property з `settings.HANDOFF_TOKEN_TTL` (default 120s)
- `created_at`, `confirmed_at`, `is_confirmed`

### Сервісний шар (kitchen/services.py)
- `create_handoff(ticket, target_waiter)` — створює handoff, видаляє старий unconfirmed
- `manual_handoff(ticket, kitchen_user)` — ідемпотентний fallback, скасовує pending QR handoffs

### Сервісний шар (orders/services.py)
- `deliver_order(order, waiter)` — перевіряє що всі KitchenTickets DONE перед delivery

### Views
- `generate_handoff_qr` (kitchen) — GET: форма вибору офіціанта, POST: PNG QR-код
- `handoff_confirm_view` (waiter) — GET: деталі страви/кухаря, POST: atomic confirm
- `ticket_manual_handoff` (kitchen) — POST-only, redirect на dashboard
- `order_mark_delivered` (waiter) — оновлено для використання `deliver_order` сервісу

### URLs
- `/kitchen/ticket/<id>/handoff/` — QR генерація
- `/kitchen/ticket/<id>/manual-handoff/` — ручне підтвердження
- `/waiter/handoff/<uuid:token>/confirm/` — waiter scan confirm

### Шаблони
- `kitchen/handoff_select_waiter.html` — вибір офіціанта для QR
- `orders/handoff_confirm.html` — підтвердження прийому (з TTL таймером)
- `orders/handoff_expired.html` — 400, прострочений токен
- `orders/handoff_already_confirmed.html` — info page
- Kitchen dashboard — кнопки "QR" та "Вручну" в секції "Готово"
- Waiter dashboard — блок "Передано, але не оплачено" з кнопкою оплати

### Settings
- `HANDOFF_TOKEN_TTL: int = 120` (seconds) в base.py

### Тести
- kitchen/tests_handoff.py — 13 тестів (модель, сервіс, view)
- kitchen/tests_manual_handoff.py — 8 тестів (сервіс, view)
- orders/tests_handoff_confirm.py — 6 тестів (confirm flow)
- orders/tests_deliver.py — 7 тестів (deliver_order сервіс + view)

### Архітектурні рішення
- PEP 758 (Python 3.14): використано `except X, Y:` без дужок — нативний синтаксис
- Валідація на рівні сервісного шару (не тільки у views) — service функції можуть викликатися з Celery tasks, management commands
- `get_object_or_404` для ticket lookup (assigned_to + status), `User.DoesNotExist` + `ValueError` для waiter validation

## Definition of Done ✅

- [x] `KitchenHandoff` модель з UUID token і TTL
- [x] Кухар генерує QR для конкретного офіціанта
- [x] Офіціант сканує QR → бачить деталі → підтверджує одним кліком
- [x] Fallback: кухар сам відмічає "передав" без сканування
- [x] Офіціант вручну відмічає "передав відвідувачу"
- [x] Token протермінований → 400 з зрозумілим повідомленням
- [x] Всі тести зелені
