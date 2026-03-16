# Sprint 6 — Багатомовність

## Board

**Мета:** меню відображається мовою відвідувача (UK, EN, CNR, HR, BS, IT, DE).
**Оцінка:** 8–10 годин
**Залежності:** Sprint 1 завершений (базові моделі меню)
**Статус:** ✅ ЗАВЕРШЕНО, merged to main

| # | Назва | Оцінка | Статус |
|---|---|---|---|
| 6.1 | django-modeltranslation: налаштування і міграції | 2 год | ✅ Done |
| 6.2 | Переклади Dish і Category в адмінці | 2 год | ✅ Done |
| 6.3 | Language switcher і middleware | 1.5 год | ✅ Done |
| 6.4 | Відображення алергенів і опису мовою відвідувача | 2 год | ✅ Done |

---

## Мови (7 підтримуваних)

| Код | Мова | Прапорець | Пріоритет |
|---|---|---|---|
| `uk` | Українська | 🇺🇦 | Основна (всі поля обовʼязкові, fallback) |
| `en` | English | 🇬🇧 | Обовʼязкова (фестиваль міжнародний) |
| `cnr` | Crnogorski (Чорногорська) | 🇲🇪 | Рекомендована (ISO 639-3, **не** `sr` — різні літери: ś, ź) |
| `hr` | Hrvatski (Хорватська) | 🇭🇷 | Рекомендована |
| `bs` | Bosanski (Боснійська) | 🇧🇦 | Рекомендована |
| `it` | Italiano (Італійська) | 🇮🇹 | Бажана |
| `de` | Deutsch (Німецька) | 🇩🇪 | Бажана |

## Що реалізовано

### Task 6.1 — modeltranslation setup
- `django-modeltranslation` в залежностях
- `modeltranslation` перед `django.contrib.admin` в INSTALLED_APPS
- `LANGUAGES` — 7 мов (чисті назви, прапорці через `|lang_flag` template filter)
- `LANGUAGE_CODE = "uk"`, `MODELTRANSLATION_DEFAULT_LANGUAGE = "uk"`, `MODELTRANSLATION_FALLBACK_LANGUAGES = ("uk",)`
- `LocaleMiddleware` після SessionMiddleware
- `menu/translation.py` — реєстрація Category, Dish, Tag, Allergen (title + description)
- Міграції: 0005 (initial 4 langs), 0006 (Allergen model), 0007 (add hr/bs/it), 0008 (rename sr→cnr)
- mypy override: `django-manager-missing` disabled для `menu.models` (modeltranslation runtime patching)

### Task 6.2 — Адмінка
- `TabbedTranslationAdmin` для Category, Dish, Tag, Allergen
- `search_fields = ["title_uk", "title_en"]`
- `ordering` на всіх admin classes (Category, Tag, Dish, Allergen)

### Task 6.3 — Language switcher
- `/i18n/setlang/` URL (Django built-in `set_language` view)
- Navbar: `<select>` з формою POST, автоматичний submit onChange
- `|lang_flag` template filter (menu_extras.py) — маппінг lang_code → emoji прапорець
- Switcher показує: `🇺🇦 Українська`, `🇬🇧 English`, `🇲🇪 Crnogorski` тощо
- Мова зберігається в cookie `django_language`

### Task 6.4 — Allergen модель
- `Allergen(ModelWithTitle)` — translated `title` + `icon` (CharField, emoji)
- `Dish.allergens` — ManyToManyField
- Allergen badges в `_dish_card.html` (`.allergen-badge` CSS клас)
- Prefetch `allergens` в category_list та dish_list views
- Query count: 3→4 (додатковий prefetch для allergens)
- `AllergenAdmin(TabbedTranslationAdmin)` в admin

### Тести
- menu/tests_translation.py — 7 тестів (translation fields, fallback, override, admin)
- menu/tests_i18n.py — 9 тестів (switcher, allergens, admin, translation override)
- menu/tests.py — оновлено: `12.50` → `12,50` (uk locale), query count 3→4

### Архітектурні рішення
- Прапорці в template filter, а не в `LANGUAGES` setting — separation of concerns (UI vs config)
- Чорногорська `cnr` (ISO 639-3) замість `sr` — це різні мови з різними буквами
- modeltranslation fallback на `uk` — якщо переклад порожній, показується українською

## Відкладено на майбутнє

- [ ] `makemessages` + `compilemessages` для UI рядків (`{% trans %}` в шаблонах)
- [ ] Переклад Availability choices ("В наявності", "Закінчується") через gettext
- [ ] `.po` файли для всіх 7 мов
- [ ] Переклади хардкодних рядків в staff шаблонах (kitchen/waiter dashboards)

## Definition of Done ✅

- [x] `django-modeltranslation` налаштований, міграції застосовані
- [x] `Dish.title`, `Dish.description`, `Category.title`, `Category.description`, `Tag.title`, `Tag.description` — перекладені
- [x] `Allergen` модель з перекладом `title` + emoji icon
- [x] Адмінка: всі мови редагуються в одній формі (tabbed)
- [x] Language switcher в navbar з прапорцями
- [x] Cookie-based мова через `/i18n/setlang/`
- [x] Fallback на `uk` якщо переклад відсутній
- [x] Всі тести зелені
