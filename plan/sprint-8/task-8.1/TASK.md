# Task 8.1 — Staff display: `display_title` + `public_name`

## Мета

Додати на модель `User` два поля для персоналізованого відображення staff у відвідувача: весела посада та публічне ім'я.

## Що робити

### 1. Міграція: нові поля User

```python
# user/migrations/0006_add_staff_display_fields.py

class Migration(migrations.Migration):
    dependencies = [("user", "0005_migrate_legacy_roles")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="display_title",
            field=models.CharField(
                max_length=60,
                blank=True,
                verbose_name="Посада для відвідувачів",
                help_text="Наприклад: Повариха, Бармен, Майстер десертів, Чарівниця борщу",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="public_name",
            field=models.CharField(
                max_length=50,
                blank=True,
                verbose_name="Публічне ім'я",
                help_text="Ім'я без прізвища, яке бачитиме відвідувач. Fallback: first_name",
            ),
        ),
    ]
```

### 2. Модель User — нові поля + property

```python
# user/models.py — додати до класу User

display_title = models.CharField(
    max_length=60,
    blank=True,
    verbose_name="Посада для відвідувачів",
    help_text="Наприклад: Повариха, Бармен, Майстер десертів",
)

public_name = models.CharField(
    max_length=50,
    blank=True,
    verbose_name="Публічне ім'я",
    help_text="Ім'я без прізвища для відвідувачів",
)

@property
def staff_label(self) -> str:
    """Human-friendly label for visitor-facing displays.

    Examples:
        'Повариха Валентина'  — display_title + public_name
        'Виробництво Дмитро'  — role display + first_name (fallback)
        'Офіціант john'       — role display + email prefix (last fallback)
    """
    title = self.display_title or self.get_role_display()
    name = self.public_name or self.first_name or self.email.split("@")[0]
    return f"{title} {name}"
```

### 3. Admin

```python
# user/admin.py — додати у fieldsets або list_display

fieldsets = (
    ...
    ("Профіль для відвідувачів", {
        "fields": ("display_title", "public_name"),
        "description": "Ці поля бачитимуть відвідувачі при відстеженні замовлення.",
    }),
)

list_display = [..., "display_title", "public_name"]
```

### 4. Використання в notifications/events.py

Замінити `kitchen_user.get_full_name() or kitchen_user.email` на `kitchen_user.staff_label` у:
- `push_ticket_taken` (kitchen/services.py, рядок ~74)
- Будь-які інші місця, де ім'я staff передається відвідувачу

**Важливо:** для внутрішніх staff notifications (waiter↔kitchen) залишити `get_full_name()` — там повне ім'я доречне.

## Тести

### Tier 1

```python
@pytest.mark.tier1
class TestStaffLabel:
    def test_full_display(self):
        """display_title + public_name → 'Повариха Валентина'"""
        user = User(display_title="Повариха", public_name="Валентина", role="kitchen")
        assert user.staff_label == "Повариха Валентина"

    def test_fallback_role_display(self):
        """No display_title → role display name."""
        user = User(role="kitchen", first_name="Дмитро")
        assert user.staff_label == "Виробництво Дмитро"

    def test_fallback_email_prefix(self):
        """No public_name, no first_name → email prefix."""
        user = User(role="waiter", email="john@fest.ua")
        assert user.staff_label == "Офіціант john"

    def test_empty_fields(self):
        """All fallbacks → role + email prefix."""
        user = User(role="visitor", email="guest@gmail.com")
        assert user.staff_label == "Відвідувач guest"
```

### Tier 2

```python
@pytest.mark.tier2
@pytest.mark.django_db
def test_staff_display_fields_in_admin(admin_client):
    """Admin can set display_title and public_name."""
    ...
```

## Оцінка: 2 години

## Acceptance Criteria

- [ ] Міграція створена і застосовується без помилок
- [ ] `staff_label` повертає коректний рядок для всіх комбінацій полів
- [ ] Admin показує і дозволяє редагувати обидва поля
- [ ] Тести tier1 — зелені
