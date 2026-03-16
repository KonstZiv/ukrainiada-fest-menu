# Task 6.1 — django-modeltranslation: налаштування (детально)

## pyproject.toml — додати

```toml
dependencies = [
    ...
    "django-modeltranslation",
]
```

## settings/base.py

```python
# Додати до INSTALLED_APPS — ПЕРЕД "menu" (важливо для modeltranslation)
INSTALLED_APPS = [
    "modeltranslation",  # ← має бути перед django.contrib.admin
    "django.contrib.admin",
    ...
    "menu",
    ...
]

# Підтримувані мови (7 мов, прапорці в назвах для UI switcher)
LANGUAGES = [
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
    ("cnr", "🇲🇪 Crnogorski"),   # ISO 639-3 — чорногорська (не sr!)
    ("hr", "🇭🇷 Hrvatski"),
    ("bs", "🇧🇦 Bosanski"),
    ("it", "🇮🇹 Italiano"),
    ("de", "🇩🇪 Deutsch"),
]

LANGUAGE_CODE = "uk"  # основна мова

USE_I18N = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# Fallback: якщо переклад відсутній — використовуємо основну мову
MODELTRANSLATION_DEFAULT_LANGUAGE = "uk"
MODELTRANSLATION_FALLBACK_LANGUAGES = ("uk",)
```

## menu/translation.py — новий файл

```python
from modeltranslation.translator import register, TranslationOptions
from menu.models import Category, Dish, Tag


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Dish)
class DishTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("title", "description")
```

## Міграції

```bash
# modeltranslation додає нові поля (title_uk, title_en, title_cnr, title_hr, title_bs, title_it, title_de)
uv run python manage.py makemigrations menu --name="add_translation_fields"
uv run python manage.py migrate

# Синхронізувати існуючі дані: копіює title → title_uk
uv run python manage.py update_translation_fields
```

## Тести

```python
# menu/tests/test_translation.py
import pytest


@pytest.mark.tier1
def test_dish_has_translation_fields():
    from menu.models import Dish
    assert hasattr(Dish, "title_uk")
    assert hasattr(Dish, "title_en")
    assert hasattr(Dish, "description_uk")
    assert hasattr(Dish, "description_en")


@pytest.mark.tier2
@pytest.mark.django_db
def test_translation_fallback_to_uk():
    """Якщо EN переклад відсутній — повертаємо UK."""
    from menu.models import Category, Dish
    from modeltranslation.utils import auto_populate
    from django.utils import translation

    cat = Category.objects.create(
        title_uk="Перші страви",
        title_en="",  # немає EN перекладу
        description_uk="Супи",
        description_en="",
        number_in_line=1,
    )
    with translation.override("en"):
        # Fallback до uk
        assert cat.title  # не порожній рядок


@pytest.mark.tier2
@pytest.mark.django_db
def test_dish_title_in_different_languages():
    from menu.models import Category, Dish
    from django.utils import translation
    from decimal import Decimal

    cat = Category.objects.create(
        title_uk="Перші страви", title_en="First courses",
        description_uk="", description_en="", number_in_line=1,
    )
    dish = Dish.objects.create(
        title_uk="Борщ", title_en="Borscht",
        description_uk="Традиційний суп", description_en="Traditional soup",
        price=Decimal("8.00"), weight=400, calorie=320, category=cat,
    )

    with translation.override("uk"):
        assert dish.title == "Борщ"

    with translation.override("en"):
        assert dish.title == "Borscht"
```

## Acceptance criteria

- [ ] `modeltranslation` в INSTALLED_APPS перед `admin`
- [ ] `menu/translation.py` з реєстрацією трьох моделей
- [ ] Міграції застосовані: поля `title_uk`, `title_en`, `title_cnr`, `title_hr`, `title_bs`, `title_it`, `title_de` в БД
- [ ] `update_translation_fields` виконано — існуючі дані скопійовані в `title_uk`
- [ ] Тести зелені
