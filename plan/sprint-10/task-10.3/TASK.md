# Task 10.3 — Celery task: авто-ескалація по ланцюжку

## Мета

Якщо офіціант не реагує на ескалацію протягом ESCALATION_AUTO_LEVEL хв — рівень піднімається автоматично.

## Що робити

### 1. Celery task

```python
# orders/tasks.py — додати

@shared_task(name="orders.escalate_visitor_issues")
def escalate_visitor_issues() -> dict[str, int]:
    """Auto-escalate unacknowledged visitor escalations.

    Logic:
        created_at + ESCALATION_AUTO_LEVEL → level 1→2 (senior_waiter)
        created_at + ESCALATION_AUTO_LEVEL*2 → level 2→3 (manager)

    Runs via Celery Beat every minute.
    """
    now = timezone.now()
    auto_delay = timedelta(minutes=settings.ESCALATION_AUTO_LEVEL)

    # Level 2→3 (manager) — OPEN/ACKNOWLEDGED older than 2x delay
    manager_threshold = now - (auto_delay * 2)
    to_manager = VisitorEscalation.objects.filter(
        status__in=["open", "acknowledged"],
        level__lt=VisitorEscalation.Level.MANAGER,
        created_at__lte=manager_threshold,
    )
    manager_ids = list(to_manager.values_list("id", flat=True))
    manager_count = VisitorEscalation.objects.filter(id__in=manager_ids).update(
        level=VisitorEscalation.Level.MANAGER,
    )

    # Level 1→2 (senior) — OPEN only, older than 1x delay
    senior_threshold = now - auto_delay
    to_senior = VisitorEscalation.objects.filter(
        status="open",  # тільки непобачені
        level=VisitorEscalation.Level.WAITER,
        created_at__lte=senior_threshold,
    )
    senior_ids = list(to_senior.values_list("id", flat=True))
    senior_count = VisitorEscalation.objects.filter(id__in=senior_ids).update(
        level=VisitorEscalation.Level.SENIOR,
    )

    # SSE pushes
    for esc_id in manager_ids:
        esc = VisitorEscalation.objects.select_related("order").get(id=esc_id)
        push_visitor_escalation_to_manager(
            escalation_id=esc.pk, order_id=esc.order_id,
            reason=esc.reason, level=3,
        )
        push_visitor_ticket_update(
            order_id=esc.order_id,
            event_type="escalation_level_up",
            data={"level": 3, "level_display": "Менеджер"},
        )

    for esc_id in senior_ids:
        esc = VisitorEscalation.objects.select_related("order").get(id=esc_id)
        push_visitor_escalation_to_senior(
            escalation_id=esc.pk, order_id=esc.order_id,
            reason=esc.reason, level=2,
        )
        push_visitor_ticket_update(
            order_id=esc.order_id,
            event_type="escalation_level_up",
            data={"level": 2, "level_display": "Старший офіціант"},
        )

    return {"to_senior": senior_count, "to_manager": manager_count}
```

### 2. Celery Beat schedule

```python
# core_settings/settings/base.py — додати в CELERY_BEAT_SCHEDULE

"escalate-visitor-issues": {
    "task": "orders.escalate_visitor_issues",
    "schedule": 60.0,
},
```

### 3. Нові push-функції

```python
# notifications/events.py

def push_visitor_escalation(waiter_id: int, escalation_id: int, order_id: int,
                            reason: str, level: int) -> None:
    """Notify waiter about visitor escalation."""
    _push(waiter_channel(waiter_id), "visitor_escalation", {
        "escalation_id": escalation_id,
        "order_id": order_id,
        "reason": reason,
        "level": level,
    })

def push_visitor_escalation_to_senior(escalation_id: int, order_id: int,
                                       reason: str, level: int) -> None:
    """Notify senior waiter about escalated visitor issue."""
    _push(manager_channel(), "visitor_escalation", {
        "escalation_id": escalation_id,
        "order_id": order_id,
        "reason": reason,
        "level": level,
    })

# manager channel already catches all escalations via manager_channel()
push_visitor_escalation_to_manager = push_visitor_escalation_to_senior
```

### 4. Settings

```python
# core_settings/settings/base.py
ESCALATION_AUTO_LEVEL: int = config("ESCALATION_AUTO_LEVEL", default=3, cast=int)
ESCALATION_COOLDOWN: int = config("ESCALATION_COOLDOWN", default=5, cast=int)
ESCALATION_MIN_WAIT: int = config("ESCALATION_MIN_WAIT", default=5, cast=int)
```

## Тести

### Tier 1

```python
@pytest.mark.tier1
def test_escalation_task_promotes_to_senior(mocker, freezer):
    """After ESCALATION_AUTO_LEVEL minutes, level 1 → 2."""
    ...

@pytest.mark.tier1
def test_escalation_task_promotes_to_manager(mocker, freezer):
    """After 2x ESCALATION_AUTO_LEVEL, level → 3."""
    ...

@pytest.mark.tier1
def test_acknowledged_not_promoted_to_senior():
    """Acknowledged escalations skip level 1→2 promotion."""
    ...

@pytest.mark.tier1
def test_acknowledged_still_promoted_to_manager():
    """Acknowledged but unresolved → still promoted to manager."""
    ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Task запускається кожну хвилину через Beat
- [ ] OPEN level 1 → 2 після ESCALATION_AUTO_LEVEL хв
- [ ] OPEN або ACKNOWLEDGED level <3 → 3 після 2x ESCALATION_AUTO_LEVEL хв
- [ ] SSE push при кожному підвищенні рівня
- [ ] Visitor отримує повідомлення про підвищення рівня
- [ ] Тести зелені
