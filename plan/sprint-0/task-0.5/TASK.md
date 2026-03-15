# Task 0.5 — Ролі і Dish.availability (детально)

## Що робимо

### 1. user/models.py — оновити Role

Замінити існуючий `Role` TextChoices:

```python
class Role(models.TextChoices):
    MANAGER = "manager", "Менеджер"
    KITCHEN_SUPERVISOR = "kitchen_supervisor", "Старший кухні"
    KITCHEN = "kitchen", "Виробництво"
    SENIOR_WAITER = "senior_waiter", "Старший офіціант"
    WAITER = "waiter", "Офіціант"
    VISITOR = "visitor", "Відвідувач"
```

**Видалені ролі:** `PRODUCTION` → `KITCHEN`, `FINANCE` → прибрано.
⚠️ Якщо в БД є користувачі з `role="production"` або `role="finance"` — написати data-міграцію.

**Data-міграція для існуючих даних:**
```python
# migrations/0004_migrate_legacy_roles.py
def migrate_roles(apps, schema_editor):
    User = apps.get_model("user", "User")
    User.objects.filter(role="production").update(role="kitchen")
    User.objects.filter(role="finance").update(role="visitor")

class Migration(migrations.Migration):
    dependencies = [("user", "0003_...")]
    operations = [migrations.RunPython(migrate_roles, migrations.RunPython.noop)]
```

### 2. menu/models.py — додати Dish.availability

```python
class Dish(ModelWithTitle):

    class Availability(models.TextChoices):
        AVAILABLE = "available", "В наявності"
        LOW = "low", "Закінчується — уточнюйте у офіціанта"
        OUT = "out", "Немає"

    # ... існуючі поля ...

    availability = models.CharField(
        max_length=16,
        choices=Availability.choices,
        default=Availability.AVAILABLE,
        db_index=True,
        verbose_name="Наявність",
    )
```

### 3. menu/admin.py — додати availability

```python
@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "price", "availability"]
    list_filter = ["availability", "category"]
    list_editable = ["availability"]  # швидка зміна прямо в списку
```

### 4. menu/views.py — фільтрація у відображенні для відвідувача

У `dish_list` і `category_list` — виключати `OUT` страви:

```python
# Для відвідувача — не показуємо OUT
def dish_list(request):
    dishes = Dish.objects.exclude(
        availability=Dish.Availability.OUT
    ).select_related(...).prefetch_related(...)
    ...
```

⚠️ Адмін і kitchen/waiter-ролі бачать ВСІ страви — фільтрація тільки для `visitor`.

### 5. Хелпер для перевірки ролі

```python
# user/roles.py
from django.contrib.auth import get_user_model

User = get_user_model()


def is_kitchen_staff(user: User) -> bool:  # type: ignore[valid-type]
    return user.role in (User.Role.KITCHEN, User.Role.KITCHEN_SUPERVISOR)


def is_waiter_staff(user: User) -> bool:  # type: ignore[valid-type]
    return user.role in (User.Role.WAITER, User.Role.SENIOR_WAITER)


def is_management(user: User) -> bool:  # type: ignore[valid-type]
    return user.role == User.Role.MANAGER
```

## Міграції

```bash
uv run python manage.py makemigrations user --name="update_roles"
uv run python manage.py makemigrations menu --name="add_dish_availability"
uv run python manage.py migrate
```

## Тести

```python
# tests/test_roles.py
import pytest
from django.test import TestCase

@pytest.mark.tier1
def test_all_roles_defined():
    from user.models import User
    roles = [r.value for r in User.Role]
    assert "manager" in roles
    assert "kitchen_supervisor" in roles
    assert "kitchen" in roles
    assert "senior_waiter" in roles
    assert "waiter" in roles
    assert "visitor" in roles
    # legacy roles видалені
    assert "production" not in roles
    assert "finance" not in roles

@pytest.mark.tier1
def test_dish_availability_choices():
    from menu.models import Dish
    values = [a.value for a in Dish.Availability]
    assert "available" in values
    assert "low" in values
    assert "out" in values

@pytest.mark.tier1
def test_dish_availability_default():
    from menu.models import Dish
    # Не зберігаємо в БД — перевіряємо дефолт поля
    dish = Dish(title="Test", description="", price=1, weight=100, calorie=100)
    assert dish.availability == Dish.Availability.AVAILABLE

@pytest.mark.tier2
@pytest.mark.django_db
def test_dish_list_excludes_out(client, django_user_model):
    from menu.models import Dish, Category
    cat = Category.objects.create(title="Test", description="", number_in_line=1)
    Dish.objects.create(title="Available", description="", price=1, weight=100,
                        calorie=100, category=cat, availability="available")
    Dish.objects.create(title="OutOfStock", description="", price=1, weight=100,
                        calorie=100, category=cat, availability="out")
    response = client.get("/menu/dishes/")
    assert response.status_code == 200
    assert "Available" in response.content.decode()
    assert "OutOfStock" not in response.content.decode()

@pytest.mark.tier1
def test_is_kitchen_staff():
    from user.roles import is_kitchen_staff
    from unittest.mock import MagicMock
    from user.models import User
    user = MagicMock()
    user.role = User.Role.KITCHEN
    assert is_kitchen_staff(user) is True
    user.role = User.Role.WAITER
    assert is_kitchen_staff(user) is False
```

## Acceptance criteria

- [ ] `User.Role` — 6 значень, немає `production` і `finance`
- [ ] `Dish.availability` — поле в моделі, міграція застосована
- [ ] Адмінка показує `availability` з `list_editable`
- [ ] Список страв для відвідувача не показує `out`
- [ ] `user/roles.py` — 3 хелпери
- [ ] `uv run pytest -m "tier1 or tier2" tests/test_roles.py` — зелені
