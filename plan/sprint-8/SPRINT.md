# Sprint 8 — Підготовка, безпека, персоналізація staff

## Board

**Мета:** закрити критичні прогалини безпеки, додати ідентифікацію місця/столу, персоналізувати staff-профілі (посада + display name для відвідувачів), підготувати i18n UI рядків.
**Оцінка:** 8–10 годин
**Залежності:** Sprint 7 завершений
**Пріоритет:** 🔴 Критичний — без цього спринту Live Order Tracking (Sprint 9) неможливий

| # | Назва | Оцінка |
|---|---|---|
| 8.1 | Staff display: `display_title` + `public_name` на User | 2 год |
| 8.2 | Безпека доступу до замовлень (session token) | 2.5 год |
| 8.3 | Необов'язкова підказка місця на Order | 0.5 год |
| 8.4 | i18n UI рядків для staff- і visitor-шаблонів | 2.5 год |

---

## Детально для виконавця

### 8.1 — Staff display: навіщо і як

Для Live Order Tracking (Sprint 9) відвідувач бачитиме:
```
👩‍🍳 Повариха Валентина готує ваш борщ
🍺 Бармен Наталія готує ваш чай
🏃 Офіціант Дмитро несе ваше замовлення
```

Потрібно два нових поля на `User`:

- **`display_title`** — весела/дружня посада (`CharField(max_length=60, blank=True)`).
  Приклади: "Повариха", "Шеф-кухар", "Бармен", "Майстер десертів", "Чарівниця борщу".
  Заповнюється адміном перед фестивалем.
  Fallback → `get_role_display()` ("Виробництво", "Офіціант").

- **`public_name`** — ім'я для відвідувачів (`CharField(max_length=50, blank=True)`).
  Приклади: "Валентина", "Дмитро", "Катя".
  Fallback → `first_name` → email prefix.
  Прізвище НЕ показуємо — захист приватності.

Ці поля **мовонезалежні**: на фестивалі імена та посади залишаються тими самими для всіх мов. Якщо знадобиться переклад "Повариха" → "Cook" — це можна зробити через `modeltranslation` пізніше, але поки що це зайвий scope.

### 8.2 — Безпека: order access token

**Проблема:** `order_detail(order_id)` і `order_qr(order_id)` доступні будь-кому.

**Рішення:** `Order.access_token` — UUID, auto-generated при створенні.

Два режими доступу:
1. Авторизований відвідувач → `visitor == request.user`
2. Анонімний → URL містить `?token=<uuid>` АБО token збережений у session

При submit з cart → `request.session["my_orders"]` зберігає `{order_id: access_token}`.
При переході на order_detail → перевіряє session або GET-параметр.

### 8.3 — Необов'язкова підказка місця

Просте текстове поле `Order.location_hint` (max 60 символів, blank).
Це подія діаспори: більшість знайомі, увечері всі переміщуються, жорстка прив'язка до місця не працює. Але хто хоче — може написати "ми біля дерева" чи "столик у Марини".

Мінімальний input без акценту в cart form. Відображення на waiter dashboard — тільки якщо заповнено, дрібним текстом.

### 8.4 — i18n UI рядків

Мінімальний обсяг:
- `{% trans %}` / `{% blocktrans %}` у staff і visitor шаблонах
- `gettext()` / `gettext_lazy()` у views (flash messages), forms, model verbose_name
- `makemessages -l uk -l en -l cnr` → `.po` файли
- `compilemessages` → `.mo` файли

Обсяг перекладу для MVP: uk (вже є як hardcoded), en, cnr.
Решта мов (hr, bs, it, de) — заповнюються перекладачами після спринту.

---

## Definition of Done

- [ ] `User.display_title`, `User.public_name` — міграція, admin form, тести
- [ ] `User.staff_label` property — повертає "Повариха Валентина" з fallback ланцюжком
- [ ] `Order.access_token` — UUID, auto-generated, `unique=True`, `db_index=True`
- [ ] `order_detail` і `order_qr` — перевіряють ownership або token
- [ ] Session зберігає `my_orders` mapping при submit
- [ ] `Order.location_hint` — необов'язкове поле, тихий input у cart, дрібне відображення на dashboard
- [ ] `{% trans %}` у staff та visitor шаблонах, `.po` файли для uk/en/cnr
- [ ] `uv run pytest -m "tier1 or tier2"` — зелені

## Відкладено

- [ ] Переклад `display_title` через modeltranslation (коли буде потреба)
- [ ] Повний переклад `.po` для всіх 7 мов
- [ ] QR-код з вбудованим access_token
- [ ] Зони фестивалю (якщо колись знадобиться структурований вибір місця)
