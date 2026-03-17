# Task 10.1 — Модель `VisitorEscalation` + сервісний шар

## Мета

Модель для ескалації від відвідувача та сервісні функції з валідацією (anti-spam, cooldown, min wait).

## Що робити

### 1. Нова app або в `orders/`?

**Рішення:** в `orders/` — ескалація тісно пов'язана із замовленням. Нова модель в `orders/models.py`.

### 2. Модель

```python
# orders/models.py

class VisitorEscalation(models.Model):
    class Reason(models.TextChoices):
        SLOW = "slow", "Довго чекаю"
        WRONG = "wrong", "Щось не те"
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

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="escalations",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    message = models.TextField(blank=True, max_length=300, verbose_name="Коментар")
    level = models.IntegerField(
        choices=Level.choices, default=Level.WAITER, db_index=True,
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.OPEN, db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="resolved_escalations",
    )
    resolution_note = models.TextField(blank=True, max_length=300)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Escalation #{self.pk} Order#{self.order_id} [{self.get_status_display()}]"
```

### 3. Міграція

```python
# orders/migrations/0006_visitor_escalation.py
```

### 4. Сервісний шар

```python
# orders/escalation_services.py

from django.conf import settings as django_settings

def create_escalation(order: Order, reason: str, message: str = "") -> VisitorEscalation:
    """Visitor creates an escalation for their order.

    Raises:
        ValueError: if anti-spam rules are violated.
    """
    now = timezone.now()

    # Rule 1: одна відкрита ескалація на замовлення
    open_exists = VisitorEscalation.objects.filter(
        order=order, status__in=["open", "acknowledged"],
    ).exists()
    if open_exists:
        raise ValueError("У вас вже є активне звернення по цьому замовленню")

    # Rule 2: min wait після approve
    if order.approved_at:
        min_wait = timedelta(minutes=django_settings.ESCALATION_MIN_WAIT)
        if now - order.approved_at < min_wait:
            raise ValueError("Зачекайте ще трохи — ваше замовлення щойно прийнято")

    # Rule 3: cooldown після останнього resolved
    last_resolved = VisitorEscalation.objects.filter(
        order=order, status="resolved",
    ).order_by("-resolved_at").first()
    if last_resolved and last_resolved.resolved_at:
        cooldown = timedelta(minutes=django_settings.ESCALATION_COOLDOWN)
        if now - last_resolved.resolved_at < cooldown:
            raise ValueError("Ваше попереднє звернення щойно вирішено — зачекайте трохи")

    escalation = VisitorEscalation.objects.create(
        order=order, reason=reason, message=message[:300],
    )

    # Push SSE to waiter
    if order.waiter_id:
        push_visitor_escalation(
            waiter_id=order.waiter_id,
            escalation_id=escalation.pk,
            order_id=order.id,
            reason=reason,
            level=1,
        )

    # Push SSE to visitor — confirmation
    push_visitor_ticket_update(
        order_id=order.id,
        event_type="escalation_created",
        data={"escalation_id": escalation.pk, "level": 1},
    )

    return escalation


def acknowledge_escalation(escalation: VisitorEscalation, staff_user: User) -> None:
    """Staff acknowledges they've seen the escalation."""
    if escalation.status != VisitorEscalation.Status.OPEN:
        raise ValueError("Ескалація вже оброблена")

    escalation.status = VisitorEscalation.Status.ACKNOWLEDGED
    escalation.acknowledged_at = timezone.now()
    escalation.save(update_fields=["status", "acknowledged_at"])

    push_visitor_ticket_update(
        order_id=escalation.order_id,
        event_type="escalation_acknowledged",
        data={"by": staff_user.staff_label},
    )


def resolve_escalation(
    escalation: VisitorEscalation, staff_user: User, note: str = "",
) -> None:
    """Staff resolves the escalation."""
    if escalation.status == VisitorEscalation.Status.RESOLVED:
        raise ValueError("Ескалація вже вирішена")

    escalation.status = VisitorEscalation.Status.RESOLVED
    escalation.resolved_at = timezone.now()
    escalation.resolved_by = staff_user
    escalation.resolution_note = note[:300]
    escalation.save(update_fields=[
        "status", "resolved_at", "resolved_by", "resolution_note",
    ])

    push_visitor_ticket_update(
        order_id=escalation.order_id,
        event_type="escalation_resolved",
        data={"note": note[:100] if note else "Ваше питання вирішено"},
    )
```

## Тести

### Tier 1 (~8 тестів)

```python
@pytest.mark.tier1
class TestEscalationAntiSpam:
    def test_cannot_create_duplicate_open(self): ...
    def test_min_wait_enforced(self): ...
    def test_cooldown_after_resolved(self): ...
    def test_can_create_after_cooldown(self): ...

class TestEscalationLifecycle:
    def test_acknowledge_updates_status(self): ...
    def test_resolve_sets_resolved_by(self): ...
    def test_cannot_resolve_already_resolved(self): ...
    def test_resolution_note_truncated(self): ...
```

## Оцінка: 2.5 години

## Acceptance Criteria

- [ ] Модель з міграцією
- [ ] create / acknowledge / resolve сервісні функції
- [ ] Anti-spam: одна відкрита, min wait, cooldown
- [ ] SSE push при create, acknowledge, resolve
- [ ] Тести tier1 — зелені
