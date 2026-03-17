# Task 11.1 — Модель `GuestFeedback` + сервісний шар

## Мета

Модель для зберігання відгуків відвідувачів та сервісні функції.

## Що робити

### 1. Нова app `feedback/`

Відгуки — окрема відповідальність від замовлень. Створити `feedback/` app.

```
feedback/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── services.py
├── urls.py
├── views.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial_feedback.py
└── tests.py
```

### 2. Модель

```python
# feedback/models.py

class GuestFeedback(models.Model):
    class Mood(models.TextChoices):
        LOVE = "love", "❤️ Чудово"
        GOOD = "good", "😊 Добре"
        OK = "ok", "😐 Нормально"
        BAD = "bad", "😕 Не дуже"

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name="Замовлення",
    )
    visitor_name = models.CharField(
        max_length=50, blank=True,
        verbose_name="Ім'я відвідувача",
        help_text="Необов'язкове. Відображається на дошці.",
    )
    mood = models.CharField(
        max_length=10, choices=Mood.choices,
        verbose_name="Настрій",
    )
    message = models.TextField(
        max_length=500, blank=True,
        verbose_name="Повідомлення",
    )

    # Модерація
    is_published = models.BooleanField(
        default=False, db_index=True,
        verbose_name="Опубліковано",
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name="Виділений відгук",
    )

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=5, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Відгук"
        verbose_name_plural = "Відгуки"

    def __str__(self) -> str:
        name = self.visitor_name or "Анонім"
        return f"{name}: {self.get_mood_display()} — Order #{self.order_id}"
```

### 3. Сервісний шар

```python
# feedback/services.py

def create_feedback(
    order: Order, mood: str, message: str = "", visitor_name: str = "",
) -> GuestFeedback:
    """Create feedback for a delivered order.

    Raises:
        ValueError: if order is not delivered or feedback already exists.
    """
    if order.status != Order.Status.DELIVERED:
        raise ValueError("Відгук можна залишити тільки після отримання замовлення")

    if hasattr(order, "feedback"):
        raise ValueError("Ви вже залишили відгук для цього замовлення")

    if mood not in dict(GuestFeedback.Mood.choices):
        raise ValueError(f"Невідомий настрій: {mood}")

    from django.utils.translation import get_language
    return GuestFeedback.objects.create(
        order=order,
        mood=mood,
        message=message[:500],
        visitor_name=visitor_name[:50],
        language=get_language() or "uk",
    )


def publish_feedback(feedback: GuestFeedback) -> None:
    """Moderator publishes feedback to public board."""
    feedback.is_published = True
    feedback.save(update_fields=["is_published"])


def feature_feedback(feedback: GuestFeedback) -> None:
    """Moderator marks feedback as featured."""
    feedback.is_featured = True
    feedback.is_published = True
    feedback.save(update_fields=["is_featured", "is_published"])


def get_public_feedback(limit: int = 50) -> QuerySet:
    """Return published feedback for public board, featured first."""
    return GuestFeedback.objects.filter(
        is_published=True,
    ).order_by("-is_featured", "-created_at")[:limit]
```

### 4. Admin

```python
# feedback/admin.py

@admin.register(GuestFeedback)
class GuestFeedbackAdmin(admin.ModelAdmin):
    list_display = ["visitor_name", "mood", "order", "is_published", "is_featured", "created_at"]
    list_filter = ["mood", "is_published", "is_featured", "language"]
    list_editable = ["is_published", "is_featured"]
    search_fields = ["visitor_name", "message"]
    readonly_fields = ["order", "mood", "message", "visitor_name", "created_at", "language"]
    ordering = ["-created_at"]
```

## Тести

### Tier 1

```python
@pytest.mark.tier1
class TestGuestFeedback:
    def test_create_feedback(self): ...
    def test_cannot_feedback_non_delivered(self): ...
    def test_cannot_duplicate_feedback(self): ...
    def test_invalid_mood_rejected(self): ...
    def test_message_truncated(self): ...
    def test_public_feedback_featured_first(self): ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Модель з міграцією
- [ ] create_feedback з валідацією
- [ ] publish / feature / get_public_feedback
- [ ] Admin з list_editable для швидкої модерації
- [ ] Тести tier1 — зелені
