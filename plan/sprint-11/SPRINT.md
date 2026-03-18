# Sprint 11 — Відгуки та Дошка повідомлень

## Board

**Мета:** відвідувач може залишити відгук після отримання замовлення. Кращі відгуки з'являються на публічній "Дошці повідомлень" фестивалю.
**Оцінка:** 6–8 годин
**Залежності:** Sprint 9 завершений (order tracking); Sprint 10 бажаний, але не обов'язковий
**Пріоритет:** 🟢 Середній — wow-фактор, але фестиваль працює і без цього

| # | Назва | Оцінка |
|---|---|---|
| 11.1 | Модель `GuestFeedback` + сервісний шар | 2 год |
| 11.2 | Форма відгуку (post-delivery) | 2 год |
| 11.3 | Публічна дошка + модерація | 2.5 год |

---

## Архітектура

### Модель GuestFeedback

```python
class GuestFeedback(models.Model):
    class Mood(models.TextChoices):
        LOVE = "love", "❤️ Чудово"
        GOOD = "good", "😊 Добре"
        OK = "ok", "😐 Нормально"
        BAD = "bad", "😕 Не дуже"

    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE,
        related_name="feedback",
    )
    visitor_name = models.CharField(
        max_length=50, blank=True,
        verbose_name="Ваше ім'я (необов'язково)",
    )
    mood = models.CharField(max_length=10, choices=Mood.choices)
    message = models.TextField(max_length=500, blank=True)
    # Модерація
    is_published = models.BooleanField(default=False, db_index=True)
    is_featured = models.BooleanField(default=False)  # для "кращих" на дошці
    # Мета
    created_at = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=5, blank=True)  # мова відвідувача
```

### Потік

```
Замовлення DELIVERED → на order_detail з'являється форма відгуку
    ↓
Відвідувач обирає mood emoji + пише повідомлення (optional)
    ↓
Feedback зберігається (is_published=False)
    ↓
Manager/admin модерує → is_published=True
    ↓
Відгук з'являється на /feedback/board/
```

### Дошка повідомлень

Публічна сторінка `/feedback/board/` — стрічка опублікованих відгуків.
Може бути на великому екрані на фестивалі.

Опціонально: SSE live-оновлення нових відгуків (нові з'являються з анімацією).

---

## Definition of Done

- [ ] `GuestFeedback` модель з міграцією
- [ ] Форма відгуку на order_detail (після delivery)
- [ ] OneToOne — один відгук на замовлення
- [ ] Mood вибір через emoji-кнопки (не dropdown)
- [ ] Модерація: admin або окремий manager view
- [ ] Публічна дошка `/feedback/board/`
- [ ] Featured відгуки виділені
- [ ] i18n: форма і дошка перекладені
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені

## Відкладено

- [ ] SSE live-feed нових відгуків на дошці
- [ ] Фільтр по mood на дошці
- [ ] Автоматична модерація (keyword blacklist)
- [ ] "Подякувати кухарю" — feedback прив'язаний до конкретного staff
- [ ] Статистика відгуків для менеджера (розподіл mood, середній рейтинг)
- [ ] QR-код на столі → прямий лінк на форму відгуку
