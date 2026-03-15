# Sprint 3 — Оплата і ескалація офіціанта

## Board

**Мета:** контроль оплати замовлень, ескалація несплачених, заглушка онлайн-оплати.
**Оцінка:** 6–8 годин
**Залежності:** Sprint 2 завершений

| # | Назва | Оцінка |
|---|---|---|
| 3.1 | Підтвердження оплати готівкою офіціантом | 1.5 год |
| 3.2 | Заглушка онлайн-оплати (інтерфейс) | 1.5 год |
| 3.3 | Celery task: ескалація несплачених замовлень | 2 год |
| 3.4 | Senior waiter dashboard | 1.5 год |

---

## Детально для виконавця

### Логіка ескалації оплати

```
Order.status = DELIVERED + payment_status = UNPAID
    → через PAY_TIMEOUT хв → зʼявляється у senior_waiter
    → через PAY_TIMEOUT * 2 хв → зʼявляється у manager
```

Нове поле: `Order.payment_escalation_level` (аналогічно до `KitchenTicket.escalation_level`).

### Definition of Done

- [ ] Офіціант підтверджує готівку кнопкою → `payment_status = PAID`
- [ ] Інтерфейс онлайн-оплати з заглушкою (кнопка → `payment_status = PAID`)
- [ ] Celery task `escalate_unpaid_orders` запускається кожну хвилину
- [ ] Senior waiter бачить ескальовані несплачені замовлення
- [ ] Manager бачить всі ескальовані (рівень 2)
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені
