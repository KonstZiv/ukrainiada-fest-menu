# Sprint 2 — Кухонний пайплайн

## Board

**Мета:** кухня бачить чергу, бере тікети в роботу, передає офіціанту, ескалація через Celery.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 1 завершений

| # | Назва | Оцінка |
|---|---|---|
| 2.1 | Kitchen dashboard — черга тікетів | 2 год |
| 2.2 | Взяти тікет в роботу і позначити готовим | 1.5 год |
| 2.3 | Статистика throughput для офіціанта | 1 год |
| 2.4 | Celery task: ескалація нічийних тікетів | 2 год |
| 2.5 | Waiter dashboard — стан моїх замовлень | 1.5 год |

---

## Детально для виконавця

### Концепція ескалації кухні

```
Тікет PENDING → через KITCHEN_TIMEOUT хв → зʼявляється у kitchen_supervisor
Тікет PENDING → через KITCHEN_TIMEOUT + MANAGER_TIMEOUT хв → зʼявляється у manager
```

Celery Beat перевіряє кожну хвилину. Замість видалення тікетів — додаємо поле `escalation_level`.

### Definition of Done

- [ ] Kitchen dashboard: черга pending, мій пул (taken), передані (done)
- [ ] Кухар може взяти тікет в роботу (`TAKEN`) і позначити готовим (`DONE`)
- [ ] Офіціант бачить для кожної страви: кількість в черзі + throughput за `SPEED_INTERVAL_KITCHEN` хв
- [ ] Celery task `escalate_kitchen_tickets` запускається кожну хвилину
- [ ] Ескальовані тікети зʼявляються у supervisor/manager dashboard
- [ ] Waiter бачить статус кожної страви у своєму замовленні (PENDING/TAKEN/DONE)
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені
