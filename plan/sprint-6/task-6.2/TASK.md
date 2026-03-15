# Task 6.2 — Переклади в адмінці (детально)

## menu/admin.py — оновити з modeltranslation

```python
from modeltranslation.admin import TranslationAdmin, TabbedTranslationAdmin

from menu.models import Category, Dish, Tag


@admin.register(Category)
class CategoryAdmin(TabbedTranslationAdmin):
    """TabbedTranslationAdmin — вкладки для кожної мови в одній формі."""
    list_display = ["title", "number_in_line"]
    list_editable = ["number_in_line"]
    ordering = ["number_in_line", "title"]


@admin.register(Dish)
class DishAdmin(TabbedTranslationAdmin):
    list_display = ["title", "category", "price", "availability"]
    list_filter = ["availability", "category"]
    list_editable = ["availability"]
    search_fields = ["title_uk", "title_en"]

    # Показуємо поля по групах — спочатку основна мова
    fieldsets = [
        ("🇺🇦 Українська (обовʼязково)", {
            "fields": ["title_uk", "description_uk"]
        }),
        ("🇬🇧 English", {
            "fields": ["title_en", "description_en"],
            "classes": ["collapse"],
        }),
        ("🇲🇪 Crnogorski", {
            "fields": ["title_sr", "description_sr"],
            "classes": ["collapse"],
        }),
        ("🇩🇪 Deutsch", {
            "fields": ["title_de", "description_de"],
            "classes": ["collapse"],
        }),
        ("Деталі", {
            "fields": ["category", "price", "weight", "calorie", "tags", "availability"]
        }),
    ]


@admin.register(Tag)
class TagAdmin(TabbedTranslationAdmin):
    list_display = ["title"]
    search_fields = ["title_uk", "title_en"]
```

## Тести

```python
# menu/tests/test_admin_translation.py
import pytest


@pytest.mark.tier2
@pytest.mark.django_db
def test_admin_dish_create_with_translations(client, django_user_model):
    from menu.models import Category, Dish
    from decimal import Decimal

    superuser = django_user_model.objects.create_superuser(
        email="admin@test.com", password="pass", username="admin"
    )
    cat = Category.objects.create(
        title_uk="Тест", title_en="Test",
        description_uk="", description_en="", number_in_line=1,
    )

    client.force_login(superuser)
    response = client.post("/admin/menu/dish/add/", {
        "title_uk": "Борщ",
        "title_en": "Borscht",
        "title_sr": "",
        "title_de": "",
        "description_uk": "Суп",
        "description_en": "Soup",
        "description_sr": "",
        "description_de": "",
        "price": "8.00",
        "weight": "400",
        "calorie": "320",
        "category": cat.id,
        "availability": "available",
    })
    # Redirect після успішного створення
    assert response.status_code in (302, 200)
    assert Dish.objects.filter(title_uk="Борщ", title_en="Borscht").exists()
```

## Acceptance criteria

- [ ] Адмінка Dish: вкладки або fieldsets для кожної мови
- [ ] `title_uk` обовʼязковий (стандартна валідація Django)
- [ ] `title_en`, `title_sr`, `title_de` — необовʼязкові
- [ ] Search в адмінці шукає по `title_uk` і `title_en`
- [ ] Тести зелені
