# Playwright Testing Findings

## Тестове середовище

- Dev server: `http://127.0.0.1:8000`
- DB: PostgreSQL з fixtures (44 страви, 14 категорій)
- Users: valentyna (kitchen), barmen (kitchen), dmytro (waiter), senior, manager, guest, admin
- KitchenAssignment: налаштовані для всіх страв
- Redis/Celery: НЕ запущені (SSE не працює live, тільки SSR)

---

## ✅ ПРОЙДЕНІ СЦЕНАРІЇ

### Сценарій 1: Повний цикл замовлення (Happy Path) — ✅ PASSED

| Крок | Результат | Коментар |
|------|-----------|---------|
| 1.1 Меню | ✅ | 44 страви, 14 категорій |
| 1.2 Додати в кошик | ✅ | Борщ €8 (після фіксу B-1) |
| 1.3 Кошик | ✅ | Борщ x1, €8,00 |
| 1.4 Location hint | ✅ | "біля дерева" збережено |
| 1.5 Оформити | ✅ | Замовлення #1, SUBMITTED, QR видно |
| 1.7 Waiter scan | ✅ | Деталі замовлення, кнопка "Підтвердити" |
| 1.8 Approve | ✅ | APPROVED, офіціант "Дмитро" |
| 1.12 Kitchen dashboard | ✅ | Kanban: Борщ в "Черзі (1)" |
| 1.13 Взяти тікет | ✅ | Переміщено в "В роботі (1)" |
| 1.18 Готово | ✅ | "Готово (1)" з кнопками QR та Вручну |
| 1.19 Manual handoff | ✅ | Handoff виконано |
| 1.21 Передав відвідувачу | ✅ | DELIVERED, з'явився блок "НЕ ОПЛАЧЕНО" |
| 1.22 Order detail | ✅ | Progress bar, feedback form видно |
| 1.23 Оплата | ✅ | PAID, замовлення зникло |

### Сценарій 3: Feedback та дошка — ✅ PASSED

| Крок | Результат | Коментар |
|------|-----------|---------|
| 3.1 Форма feedback | ✅ | Emoji кнопки (❤️😊😐😕), поля ім'я, повідомлення |
| 3.2-3.3 Submit | ✅ | "Дякуємо за відгук! ❤️ Чудово" + цитата |
| 3.4 Re-open | ✅ | Confirmation замість форми |
| 3.5 Board (до модерації) | ✅ | Порожній — "Поки що відгуків немає" |
| 3.6 Moderate page | ✅ | "Очікують модерації (1)", Олена, Борщ |
| 3.7 Publish | ✅ | "Очікують (0)", зникло з pending |
| 3.9 Board (після) | ✅ | "❤️ Чудово, Неймовірний борщ!, — Олена" |

### Сценарій 4: Безпека — ✅ PASSED

| Крок | Результат | Коментар |
|------|-----------|---------|
| 4.1 /order/1/ без token | ✅ 403 | Friendly 403 page |
| 4.2 Wrong token | ✅ 403 | |
| 4.3 Правильний token | ✅ 200 | |
| 4.7 /order/1/qr/ анонім | ✅ 404 | Order вже DELIVERED (не SUBMITTED) |
| 4.8 /waiter/dashboard/ анонім | ✅ 302 | Redirect на login |
| 4.9 /kitchen/ анонім | ✅ 302 | Redirect на login |
| 4.10 /feedback/moderate/ waiter | ✅ 403 | Manager-only |
| 4.6 Staff бачить чуже замовлення | ✅ 200 | Manager має доступ |

### Сценарій 8: i18n — ✅ PARTIAL

| Крок | Результат | Коментар |
|------|-----------|---------|
| 8.1 Switcher видно | ✅ | 7 мов з прапорцями |
| 8.4 UK locale | ✅ | Все українською |

---

## 🔴 ВИПРАВЛЕНІ БЛОКЕРИ (в цій сесії)

### B-1: Кнопка "+" на dish_card не додавала в кошик — **FIXED** ✅
Додано `<form>` з POST action.

### F-2: Admin UI видно анонімам — **FIXED** ✅
Обгорнуто `{% if user.is_staff or user.role == 'manager' %}`.

---

## 🟡 НЕВИПРАВЛЕНІ ЗНАХІДКИ

### F-1: FAB "ЗАМОВЛЕННЯ" показує застарілі дані
**Сторінки:** всі
**Проблема:** FAB внизу показує "3 ЗАМОВЛЕННЯ €38.50" постійно, не зважаючи на реальний стан кошика.
**Причина:** `_order_fab.html` не використовує context processor з реальними cart даними.

### F-3: Дублікатні категорії "Перші" (id 13, 14) та "Борщ" (id 43, 44)
**Тип:** Тестові дані в БД
**Фікс:** Видалити через admin.

### F-4: `update_translation_fields` не виконано після loaddata
**Тип:** Setup procedure
**Фікс:** Додати в CLAUDE.md або data migration.

### F-5: Location hint не видно на waiter scan view
**Сторінка:** `/waiter/order/N/scan/`
**Проблема:** Офіціант не бачить "біля дерева" при скануванні QR, тільки на dashboard.
**Фікс:** Додати `{{ order.location_hint }}` в `waiter_order_detail.html`.

### F-6: Login page доступна залогіненому
**Сторінка:** `/accounts/login/`
**Проблема:** Якщо залогінений — login page все одно показується (Django default). Не критично.
**Фікс:** redirect_authenticated_user=True в LoginView.

### U-1: Мовний switcher показує "Англійська" замість "English"
**Причина:** Django i18n display names залежать від поточної locale.

### U-2: SSE Warning "Connection lost" при відсутньому Redis
**Тип:** Інфраструктура
**Причина:** Redis не запущений → SSE reconnect loop в console.

---

## 📊 Зведення

| Сценарій | Статус |
|----------|--------|
| 1. Happy path | ✅ PASSED |
| 2. Ескалація | ⏸️ Потребує Redis/Celery для auto-escalation |
| 3. Feedback | ✅ PASSED |
| 4. Безпека | ✅ PASSED |
| 5. Edge cases | ⏸️ Потребує окремого тестування |
| 6. Staff labels | ✅ PARTIAL (staff_label не тестовано через SSE) |
| 7. Оплата | ✅ PASSED (як частина сценарію 1) |
| 8. i18n | ✅ PARTIAL (switcher працює, переклади не перевірені) |
