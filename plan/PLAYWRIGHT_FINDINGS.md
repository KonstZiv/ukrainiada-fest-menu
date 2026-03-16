# Playwright Testing Findings

## Тестове середовище

- Dev server: `http://127.0.0.1:8000`
- DB: PostgreSQL з fixtures (44 страви, 14 категорій)
- Users: створені через management script (valentyna, barmen, dmytro, senior, manager, guest, admin)
- KitchenAssignment: налаштовані для всіх страв

---

## 🔴 БЛОКЕРИ (тестування далі неможливе без фіксу)

### B-1: Кнопка "+" на dish_card не додає в кошик

**Сторінка:** `/menu/dishes/` (dish_list), також `_dish_card.html` в category_list та search
**Проблема:** Кнопка "+" на картці страви — це `<button>` без `<form>` обгортки. Натискання нічого не робить. Відвідувач НЕ МОЖЕ додати страву в кошик з жодної сторінки меню.

**Причина:** `templates/components/_dish_card.html` — кнопка декоративна:
```html
<button class="btn btn-outline-primary btn-sm rounded-circle p-0" style="width: 28px; height: 28px;">
  <i class="bi bi-plus"></i>
</button>
```
Немає `<form method="post" action="{% url 'orders:cart_add' %}">` з hidden input `dish_id`.

**Фікс:** обгорнути кнопку формою:
```html
<form method="post" action="{% url 'orders:cart_add' %}">
  {% csrf_token %}
  <input type="hidden" name="dish_id" value="{{ dish.id }}">
  <input type="hidden" name="quantity" value="1">
  <button type="submit" class="btn btn-outline-primary btn-sm rounded-circle p-0"
          style="width: 28px; height: 28px;">
    <i class="bi bi-plus"></i>
  </button>
</form>
```

### B-2: Дублікати "Борщ" (id 43, 44) без категорії

**Сторінка:** `/menu/dishes/`
**Проблема:** Два тестових записи "Борщ" з description "s", без категорії logo — тестові дані в БД. Не критично для коду, але засмічує меню.

**Фікс:** видалити через admin або `Dish.objects.filter(id__in=[43,44]).delete()`.

---

## 🟡 ФУНКЦІОНАЛЬНІ ПРОБЛЕМИ

### F-1: FAB "ЗАМОВЛЕННЯ" показує застарілі дані

**Сторінки:** всі (FAB видно скрізь через base.html)
**Проблема:** FAB кнопка внизу показує "3 ЗАМОВЛЕННЯ €38.50" хоча кошик порожній. FAB не перевіряє session cart, а показує хардкодні/старі дані.

**Причина:** `templates/components/_order_fab.html` не читає реальний стан кошика. Потрібен context processor `cart_count` + `cart_total` або перевірка в шаблоні.

**Фікс:** або скрити FAB коли кошик порожній (через context processor), або оновити FAB щоб використовував реальні cart дані.

### F-2: Адмін-елементи видні всім користувачам

**Сторінки:** всі
**Проблема:**
1. Dropdown "АДМІНІСТРУВАННЯ" в navbar (створення категорій/тегів/страв) — видно анонімам
2. Кнопки edit/delete на кожній категорії в `/menu/categories/` — видно анонімам
3. Кнопки "Редагувати"/"Видалити" на dish_detail — видно анонімам

Хоча views мають role check (403), UI не повинен показувати ці елементи нікому крім superuser та manager.

**Фікс:**
- Navbar: обгорнути "АДМІНІСТРУВАННЯ" в `{% if user.is_staff or user.role == 'manager' %}`
- Category list: обгорнути edit/delete лінки в ту саму перевірку
- Dish detail: обгорнути "Редагувати"/"Видалити" кнопки аналогічно
- Або створити template tag `{% if can_manage %}` для консистентності

### F-3: Дублікатні категорії "Перші" (id 13, 14)

**Сторінка:** `/menu/categories/`
**Проблема:** Дві категорії "Перші" без logo, окрім існуючої "Перші страви" — тестові дані.

**Фікс:** видалити через admin.

### F-4: `update_translation_fields` не виконано після міграцій

**Проблема:** Всі страви мали `title_uk=None` поки не виконали `manage.py update_translation_fields`. Це означає що після `loaddata fixtures/menu_data.json` + міграцій modeltranslation, дані не потрапляють у `_uk` поля автоматично.

**Фікс:** додати `update_translation_fields` в CLAUDE.md setup інструкції. Або додати data migration що копіює `title` → `title_uk`.

---

## 📝 UI/UX ЗАУВАЖЕННЯ

### U-1: Мовний switcher показує "Англійська" замість "English"

**Сторінка:** navbar, language selector
**Проблема:** Опції показують `get_language_info` display name через Django i18n system, тому для uk locale англійська називається "Англійська" замість "English". Це може бути заплутано для іноземців.

**Фікс:** можна показувати native name (`lang_info['name_local']`) або hardcoded назви з LANGUAGES.

### U-2: Пошук доступний але без підказки "Enter"

**Сторінка:** navbar
**Проблема:** Поле пошуку є, але немає підказки що потрібно натиснути Enter або кнопку пошуку. На mobile може бути не очевидно.

---

## ⏸️ ТЕСТУВАННЯ ЗУПИНЕНО

Сценарії 1.2-1.6 (додати в кошик → оформити) неможливо пройти через **B-1** (кнопка "+" не працює). Весь подальший flow (approve, kitchen, tracking, escalation, feedback) залежить від можливості створити замовлення.

**Для продовження тестування потрібно:**
1. Виправити B-1 (форма add-to-cart на dish_card)
2. Або створити замовлення через shell/admin для тестування решти flow

---

## Статус проходження сценаріїв

| Сценарій | Статус | Блокер |
|----------|--------|--------|
| 1. Happy path (1.1-1.23) | ⏸️ Зупинено на 1.2 | B-1: add-to-cart |
| 2. Ескалація | ⏸️ Не почато | Залежить від 1 |
| 3. Feedback | ⏸️ Не почато | Залежить від 1 |
| 4. Безпека | ⏸️ Частково (403 page OK) | — |
| 5. Edge cases | ⏸️ Не почато | — |
| 6. Staff labels | ⏸️ Не почато | — |
| 7. Оплата | ⏸️ Не почато | Залежить від 1 |
| 8. i18n | ✅ Switcher працює | — |
