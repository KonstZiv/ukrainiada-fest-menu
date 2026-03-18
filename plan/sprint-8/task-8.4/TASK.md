# Task 8.4 — i18n UI рядків ({% trans %}) для staff і visitor шаблонів

## Мета

Замінити хардкоджені українські рядки в шаблонах і views на `{% trans %}` / `gettext_lazy()`. Створити `.po` файли для uk/en/cnr.

## Що робити

### 1. Шаблони — обгорнути у {% trans %}

**Пріоритетні шаблони (staff):**
- `kitchen/dashboard.html` — "Черга", "В роботі", "Готово", кнопки
- `orders/waiter_dashboard.html` — "Мої замовлення", "Очікують оплати", кнопки
- `orders/senior_waiter_dashboard.html` — "Ескальовані замовлення"
- `orders/waiter_order_detail.html` — "Підтвердити"
- `orders/handoff_confirm.html` — "Підтвердити прийом"

**Пріоритетні шаблони (visitor):**
- `orders/cart.html` — "Кошик", "Оформити", "Де ви сидите?"
- `orders/order_detail.html` — "Замовлення #", "Статус", "Позиції"
- `orders/pay_online.html` — "Оплатити"
- `menu/index.html` — "Меню"
- `components/_navbar.html` — навігація
- `offline.html` — "Немає зв'язку"

**Формат:**
```html
<!-- До -->
<h2>Черга</h2>
<button>Взяти в роботу</button>

<!-- Після -->
{% load i18n %}
<h2>{% trans "Черга" %}</h2>
<button>{% trans "Взяти в роботу" %}</button>
```

### 2. Python рядки — gettext_lazy

```python
# views.py — flash messages
from django.utils.translation import gettext_lazy as _

messages.success(request, _("Замовлення #{order_id} підтверджено.").format(order_id=order.id))

# models.py — verbose_name (вже частково зроблено)
# forms.py — labels, help_text
```

### 3. JS рядки

`offline_detector.js` — banner text. Варіанти:
- Передати через `data-` атрибут у HTML: `data-offline-text="{% trans 'Немає зʼєднання' %}"`
- Або Django JSON-серіалізація в `<script>` блок

### 4. makemessages + compilemessages

```bash
# Створити .po файли
uv run python manage.py makemessages -l uk -l en -l cnr --no-wrap

# Структура
locale/
├── uk/LC_MESSAGES/django.po   # Заповнено автоматично (джерело)
├── en/LC_MESSAGES/django.po   # Потребує перекладу
└── cnr/LC_MESSAGES/django.po  # Потребує перекладу

# Компіляція
uv run python manage.py compilemessages
```

### 5. Мінімальний переклад для MVP

Для **en** — перекласти всі рядки (основна міжнародна мова).
Для **cnr** — перекласти критичні рядки (меню, кошик, навігація).

Решта мов (hr, bs, it, de) — `.po` файли створені, але порожні → fallback на uk.

## Обсяг рядків (оцінка)

| Категорія | Рядків |
|---|---|
| Kitchen dashboard | ~15 |
| Waiter dashboard | ~20 |
| Senior dashboard | ~10 |
| Cart + order detail | ~15 |
| Menu + navbar | ~10 |
| Flash messages (views) | ~20 |
| Offline + misc | ~5 |
| **Разом** | **~95** |

## Тести

### Tier 2

```python
@pytest.mark.tier2
def test_kitchen_dashboard_translated(client, kitchen_user):
    """Kitchen dashboard renders without untranslated hardcoded strings."""
    client.cookies["django_language"] = "en"
    response = client.get("/kitchen/dashboard/")
    # Не повинно бути хардкоджених українських рядків у кнопках
    assert "Взяти в роботу" not in response.content.decode()
    assert "Take" in response.content.decode()

@pytest.mark.tier2
def test_po_files_exist():
    """PO files exist for uk, en, cnr."""
    ...
```

## Оцінка: 2.5 години

## Acceptance Criteria

- [ ] Всі пріоритетні шаблони використовують `{% trans %}`
- [ ] Flash messages у views використовують `gettext_lazy`
- [ ] `.po` файли створені для uk, en, cnr
- [ ] en переклад — повний
- [ ] cnr переклад — критичні рядки (visitor-facing)
- [ ] `compilemessages` працює без помилок
- [ ] Тести зелені
