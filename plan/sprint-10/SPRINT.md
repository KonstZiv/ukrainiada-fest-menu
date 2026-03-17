# Sprint 10 — Ескалація від відвідувача

## Board

**Мета:** відвідувач може повідомити про проблему із замовленням. Ескалація автоматично піднімається по ланцюжку: офіціант → старший офіціант → менеджер.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 9 завершений (visitor SSE channel)
**Пріоритет:** 🟡 Високий — підвищує довіру і контроль відвідувача

| # | Назва | Оцінка |
|---|---|---|
| 10.1 | Модель `VisitorEscalation` + сервісний шар | 2.5 год |
| 10.2 | Visitor UI: кнопка + вибір причини | 2 год |
| 10.3 | Celery task: авто-ескалація по ланцюжку | 2 год |
| 10.4 | Staff UI: отримання і resolve ескалації | 2 год |

---

## Архітектура

### Модель VisitorEscalation

```python
class VisitorEscalation(models.Model):
    class Reason(models.TextChoices):
        SLOW = "slow", "Довго чекаю"
        WRONG = "wrong", "Щось не те в замовленні"
        QUESTION = "question", "Маю питання"
        OTHER = "other", "Інше"

    class Level(models.IntegerChoices):
        WAITER = 1, "Офіціант"
        SENIOR = 2, "Старший офіціант"
        MANAGER = 3, "Менеджер"

    class Status(models.TextChoices):
        OPEN = "open", "Відкрита"
        ACKNOWLEDGED = "acknowledged", "Побачено"
        RESOLVED = "resolved", "Вирішено"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="escalations")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    message = models.TextField(blank=True, max_length=300)
    level = models.IntegerField(choices=Level.choices, default=Level.WAITER)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    resolution_note = models.TextField(blank=True, max_length=300)
```

### Ланцюжок ескалації

```
Відвідувач натискає "Є проблема" → VisitorEscalation(level=1, status=open)
    ↓ SSE push → waiter
    ↓ 3 хв без acknowledge → level=2
    ↓ SSE push → senior_waiter
    ↓ 3 хв без acknowledge → level=3
    ↓ SSE push → manager
```

### Anti-spam

- Одна відкрита ескалація на замовлення (не можна створити другу, поки перша не resolved)
- Кнопка "Є проблема" з'являється через 5 хв після approve (не раніше)
- Cooldown 5 хв між resolved і новою ескалацією

### SSE-інтеграція

Офіціант отримує push на свій `waiter-{id}` канал:
```json
{"type": "visitor_escalation", "order_id": 42, "reason": "slow", "level": 1}
```

Відвідувач отримує push на `visitor-order-{id}`:
```json
{"type": "escalation_acknowledged", "by": "Офіціант Дмитро"}
{"type": "escalation_resolved", "note": "Вибачте за затримку, вже несемо!"}
```

---

## Settings

```python
# core_settings/settings/base.py
ESCALATION_COOLDOWN: int = 5    # хв — мінімум між ескалаціями
ESCALATION_AUTO_LEVEL: int = 3  # хв — авто-підняття рівня
ESCALATION_MIN_WAIT: int = 5    # хв — після approve, перш ніж можна ескалювати
```

---

## Definition of Done

- [ ] `VisitorEscalation` модель з міграцією
- [ ] Сервіс: create, acknowledge, resolve з валідацією
- [ ] Anti-spam: одна відкрита на замовлення, cooldown, min wait
- [ ] Кнопка "Є проблема" на order_detail (з'являється через ESCALATION_MIN_WAIT)
- [ ] Форма з вибором причини + опціональним коментарем
- [ ] Celery task авто-ескалації кожну хвилину
- [ ] SSE push: офіціанту при створенні, senior при level 2, manager при level 3
- [ ] SSE push: відвідувачу при acknowledged і resolved
- [ ] Staff view: acknowledge і resolve з нотаткою
- [ ] Waiter/senior/manager dashboards показують кількість відкритих ескалацій
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені

## Відкладено

- [ ] Статистика ескалацій для менеджера (середній час реакції, розподіл причин)
- [ ] Автоматичний resolve при delivery (якщо причина "slow" і замовлення доставлено)
- [ ] Рейтинг офіціантів за швидкістю реакції на ескалації
