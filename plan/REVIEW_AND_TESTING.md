# Code Review: Sprint 8–11 Implementation

## Загальна оцінка

Нова функціональність реалізована якісно: чистий service layer, правильне розділення відповідальності, SSE-інтеграція, anti-spam логіка ескалацій, feedback з модерацією. Архітектура відповідає існуючим патернам проєкту. Тести покривають основні сценарії.

Нижче — знахідки, розділені на критичні (фіксити до запуску) та бажані.

---

## 🔴 ОБОВ'ЯЗКОВО ФІКСИТИ

### 1. BUG: Відсутній перехід DRAFT → SUBMITTED

**Файл:** `orders/services.py`, `orders/views.py`

Це **pre-existing баг**, не введений новими спринтами, але він блокує ВСЮ нову функціональність.

`submit_order_from_cart()` створює замовлення зі статусом DRAFT (default). Далі `approve_order()` перевіряє `if order.status != Order.Status.SUBMITTED:` і кидає ValueError. Тобто в коді немає місця, де замовлення стає SUBMITTED — офіціант НЕ ЗМОЖЕ підтвердити жодне замовлення.

**Фікс:** або `submit_order_from_cart` має створювати з `status=Order.Status.SUBMITTED` і одразу ставити `submitted_at=timezone.now()`, або додати окремий view/сервіс для переходу DRAFT→SUBMITTED (наприклад, коли відвідувач натискає "Показати офіціанту").

### 2. BUG: `order_qr` без контролю доступу

**Файл:** `orders/views.py`, рядок ~89

```python
def order_qr(request, order_id):
    order = get_object_or_404(Order, pk=order_id, status=Order.Status.DRAFT)
    # ← Немає can_access_order(request, order)!
```

Будь-хто, знаючи `order_id`, може отримати QR-код чужого замовлення. Зважаючи на те що order_id — послідовний integer, це тривіально для перебору.

**Фікс:** додати `if not can_access_order(request, order): return HttpResponse(status=403)` перед генерацією QR.

### 3. BUG: Progress bar JS/SSR розсинхронізація

**Файли:** `orders/views.py` (`_build_progress_steps`), `staticfiles/js/order_tracker.js` (`updateProgress`)

Сервер і JS по-різному маплять 6 статусів замовлення на 5 кроків progress bar:

- **Сервер** використовує `thresholds = [0, 2, 3, 4, 5]` — пропускає "submitted" (idx=1), тому при статусі "submitted" активним є тільки крок "Створено".
- **JS** маплить напряму: `STATUS_ORDER.indexOf("submitted")` = 1, тому step[1] ("Прийнято") стає active.

Результат: при SSE-оновленні progress bar "стрибне" в інший стан, ніж відрендерив сервер.

**Фікс:** уніфікувати логіку. Найпростіше — JS теж має використовувати mapping thresholds, або серверний `_build_progress_steps` має віддавати `data-step-index` атрибути кожному кроку, а JS оперувати ними.

### 4. BUG: `escalation_services.create_escalation` не валідує `reason`

**Файл:** `orders/escalation_services.py`

View валідує `reason` (`if reason not in VisitorEscalation.Reason.values`), але сервіс — ні. За архітектурним правилом проєкту ("Бізнес-логіка — в сервісних функціях, НЕ у views"), валідація має бути в сервісі. Якщо сервіс викликається з Celery task або management command, невалідний reason потрапить у БД.

**Фікс:** додати в `create_escalation()`:
```python
if reason not in VisitorEscalation.Reason.values:
    raise ValueError(f"Невідома причина: {reason}")
```

### 5. BUG: `order_approve` приймає GET

**Файл:** `orders/waiter_views.py`, `order_approve`

```python
def order_approve(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if request.method == "POST":
        ...
    return redirect(...)
```

Без `@require_POST`. Crawler, prefetch або випадковий GET-запит виконає redirect без помилки, що не є критичним, але порушує patternи проєкту (інші подібні views мають `@require_POST`).

**Фікс:** додати `@require_POST` декоратор, як у `ticket_take`, `ticket_done`, `escalation_acknowledge`.

---

## 🟡 БАЖАНО ФІКСИТИ

### 6. `total_price` property — N+1 запитів

**Файл:** `orders/models.py`

Кожен виклик `total_price` у шаблоні виконує окремий SQL `aggregate()`. У списку 20 замовлень на waiter dashboard — 20 додаткових запитів.

**Рекомендація:** або кешувати total в полі моделі (оновлювати в `submit_order_from_cart`), або використовувати `annotate(total=Sum(F("items__dish__price") * F("items__quantity")))` у QuerySet.

### 7. `feedback/submit` — token не проброшується в POST

**Файл:** `templates/orders/order_detail.html`

Форма feedback використовує `action="{% url 'feedback:submit' order.id %}"` без `?token=...`. Для користувачів, які потрапили на order_detail через shared URL з `?token=`, POST на feedback submit може повернути 403 (якщо token не в session).

**Рекомендація:** або додати hidden input з `access_token`, або зберігати token у session при GET-доступі через `?token=`.

### 8. `order_detail` — подвійний запит для feedback

**Файл:** `orders/views.py`

```python
has_feedback = GuestFeedback.objects.filter(order=order).exists()  # запит 1
if has_feedback:
    feedback_obj = order.feedback  # запит 2 (lazy load)
```

**Рекомендація:** замінити на:
```python
try:
    feedback_obj = order.feedback
    has_feedback = True
except GuestFeedback.DoesNotExist:
    feedback_obj = None
    has_feedback = False
```

### 9. `cart_add` — немає `@require_POST`

**Файл:** `orders/views.py`

Перевіряє `request.method == "POST"` вручну замість декоратора. Не критично, але inconsistent.

### 10. `order_detail` — `{% trans step.label %}` не працюватиме

**Файл:** `templates/orders/order_detail.html`

```html
<span class="step-label">{% trans step.label %}</span>
```

`{% trans %}` працює тільки зі строковими літералами, а не зі змінними. Для змінних треба використовувати фільтр або передавати вже перекладені рядки з view.

**Фікс:** у `_build_progress_steps()` повертати вже перекладені labels:
```python
from django.utils.translation import gettext as _
labels = [_("Створено"), _("Прийнято"), _("Готується"), _("Готово"), _("Доставлено")]
```
І в шаблоні просто: `{{ step.label }}`

### 11. `VisitorEscalation.message` — max_length на TextField

**Файл:** `orders/models.py`

`TextField(max_length=300)` — Django's TextField ігнорує `max_length` на рівні DB (PostgreSQL). Це працює тільки як form validation. У сервісі є `message[:300]`, але якщо хтось напряму створить через ORM, обмеження не буде.

Не критично (сервіс обрізає), але варто знати.

---

## ✅ ДОБРЕ ЗРОБЛЕНО

- `can_access_order` — чітка 4-рівнева авторизація (staff, owner, session, URL token)
- `push_visitor_event` — єдина точка входу для всіх visitor SSE подій
- `OrderTracker` JS — textContent замість innerHTML (XSS-safe), auto-reconnect
- Anti-spam в ескалаціях — три рівні захисту
- `escalate_visitor_issues` task — exclude вже промотованих (`.exclude(id__in=manager_ids)`)
- Feedback модерація — list_editable в admin + окремий manager view
- Template `403.html` — зрозуміле повідомлення з корисними посиланнями

---
---

# План ручного тестування

## Передумови: створення даних

### Акаунти (створити через Django admin або `createsuperuser` + admin panel)

| Email | Role | display_title | public_name | Пароль |
|---|---|---|---|---|
| admin@fest.ua | (superuser) | — | — | admin123 |
| valentyna@fest.ua | kitchen | Повариха | Валентина | test123 |
| barmen@fest.ua | kitchen | Бармен | Наталія | test123 |
| dmytro@fest.ua | waiter | Офіціант | Дмитро | test123 |
| senior@fest.ua | senior_waiter | Старший офіціант | Оксана | test123 |
| manager@fest.ua | manager | Менеджер | Ігор | test123 |
| guest@gmail.com | visitor | — | — | test123 |

### Меню (через admin або fixtures)

- Категорія "Перші страви": Борщ (€5), Вареники (€4)
- Категорія "Напої": Чай (€2), Компот (€2.50)

### KitchenAssignment (через admin)

- Валентина → Борщ, Вареники
- Наталія → Чай, Компот

### Інфраструктура

- PostgreSQL + Redis запущені (`docker compose -f compose.dev.yml up -d`)
- Celery worker: `uv run celery -A core_settings worker -l info`
- Celery beat: `uv run celery -A core_settings beat -l info`
- Django dev server: `uv run python manage.py runserver`

---

## Сценарій 1: Повний цикл замовлення (Happy Path)

### 🧑 Відвідувач (guest@gmail.com або анонім)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.1 | Відкрити `/menu/` | Бачить меню з категоріями |
| 1.2 | Додати Борщ x1, Чай x1 у кошик | Кнопки "Додати" працюють, badge кошика оновлюється |
| 1.3 | Перейти в `/order/cart/` | Бачить Борщ + Чай, разом €7 |
| 1.4 | Написати "біля дерева" в полі location_hint | Поле приймає текст |
| 1.5 | Натиснути "Оформити" | Redirect на order_detail, бачить QR-код, статус "Чернетка" |
| 1.6 | Запам'ятати URL (з order_id) | Для подальшого доступу |

### 👔 Офіціант Дмитро (dmytro@fest.ua)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.7 | Відсканувати QR з екрана відвідувача (або відкрити URL `/waiter/order/N/scan/`) | Бачить деталі замовлення: Борщ, Чай, "біля дерева" |
| 1.8 | Натиснути "Підтвердити" | Замовлення стає APPROVED. Flash "Підтверджено" |
| 1.9 | Перейти на dashboard `/waiter/dashboard/` | Бачить замовлення у списку активних |

### 🧑 Відвідувач (перевірка live tracking)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.10 | Оновити сторінку замовлення | Бачить progress bar: "Прийнято" активний. Бачить "⏳ Борщ — В черзі", "⏳ Чай — В черзі" |
| 1.11 | Залишити сторінку відкритою | SSE з'єднання встановлене (Network tab: EventSource) |

### 👩‍🍳 Повариха Валентина (valentyna@fest.ua)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.12 | Відкрити kitchen dashboard `/kitchen/dashboard/` | Бачить тікет "Борщ" в черзі |
| 1.13 | Натиснути "Взяти" на тікеті Борщ | Тікет переходить у "В роботі", Валентина бачить його у своїй колонці |

### 🧑 Відвідувач (без перезавантаження!)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.14 | Подивитись на сторінку | "👩‍🍳 Повариха Валентина готує" біля Борщу (live SSE). Progress bar: "Готується" |

### 🍺 Бармен Наталія (barmen@fest.ua)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.15 | Kitchen dashboard → взяти тікет "Чай" | Тікет в роботі |
| 1.16 | Натиснути "Готово" на тікеті Чай | Тікет DONE |

### 🧑 Відвідувач (без перезавантаження!)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.17 | Подивитись на сторінку | "✅ Готово" біля Чаю |

### 👩‍🍳 Повариха Валентина

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.18 | "Готово" на тікеті Борщ | Тікет DONE |
| 1.19 | QR або "Вручну" — передача тікетів офіціанту | Handoff підтверджений |

### 🧑 Відвідувач (без перезавантаження!)

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.20 | Подивитись на сторінку | "🎉 Всі страви готові!" Progress bar: "Готово" |

### 👔 Офіціант Дмитро

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.21 | Dashboard → "Передано" на замовленні | Статус → DELIVERED |

### 🧑 Відвідувач

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.22 | Подивитись на сторінку | "✅ Доставлено! Смачного!". SSE закрито. Форма відгуку з'явилась |

### 👔 Офіціант Дмитро

| # | Дія | Очікуваний результат |
|---|---|---|
| 1.23 | Dashboard → "Підтвердити оплату" (готівка) | payment_status=PAID |

---

## Сценарій 2: Ескалація від відвідувача

**Передумова:** повторити кроки 1.1–1.13 (замовлення в статусі IN_PROGRESS, минуло 5+ хвилин після approve).

### 🧑 Відвідувач

| # | Дія | Очікуваний результат |
|---|---|---|
| 2.1 | Почекати 5 хвилин (або змінити ESCALATION_MIN_WAIT=0 для тестів) | Кнопка "Є проблема" з'являється |
| 2.2 | Натиснути "Є проблема" | Modal з вибором причини |
| 2.3 | Обрати "Довго чекаю", написати "Вже 20 хвилин" | — |
| 2.4 | Натиснути "Надіслати" | Flash "Ваше звернення надіслано!", alert "надіслано" замість кнопки |
| 2.5 | Спробувати натиснути "Є проблема" ще раз | Кнопка НЕ видна (вже є активна ескалація) |

### 👔 Офіціант Дмитро

| # | Дія | Очікуваний результат |
|---|---|---|
| 2.6 | Відкрити/оновити dashboard | Жовтий блок "Звернення відвідувачів (1)" зверху |
| 2.7 | Натиснути "Побачив" | Ескалація → ACKNOWLEDGED, відвідувач бачить "побачено, працюємо" |
| 2.8 | Натиснути "Вирішено", написати "Вже несемо!" | Ескалація → RESOLVED, зникає з dashboard |

### 🧑 Відвідувач

| # | Дія | Очікуваний результат |
|---|---|---|
| 2.9 | Подивитись на сторінку (SSE) | Статус ескалації оновився: "побачено" → зникло (resolved) |

### Авто-ескалація (тест Celery Beat)

| # | Дія | Очікуваний результат |
|---|---|---|
| 2.10 | Створити ескалацію, НЕ реагувати 3 хвилини | Celery task піднімає level → SENIOR. Senior waiter отримує SSE push |
| 2.11 | Не реагувати ще 3 хвилини | Level → MANAGER. Manager отримує push |

---

## Сценарій 3: Feedback та дошка відгуків

**Передумова:** замовлення зі статусом DELIVERED (після кроку 1.22).

### 🧑 Відвідувач

| # | Дія | Очікуваний результат |
|---|---|---|
| 3.1 | На order_detail бачить форму відгуку | Emoji-кнопки (❤️😊😐😕), поле імені, поле повідомлення |
| 3.2 | Обрати ❤️, написати ім'я "Олена", повідомлення "Неймовірний борщ!" | — |
| 3.3 | Натиснути "Надіслати відгук" | Flash "Дякуємо за відгук! 🙏". Замість форми — confirmation |
| 3.4 | Оновити сторінку | Підтвердження залишається (не можна подати вдруге) |
| 3.5 | Відкрити `/feedback/board/` | Відгук НЕ видно (ще не опубліковано) |

### 🏢 Менеджер Ігор (manager@fest.ua)

| # | Дія | Очікуваний результат |
|---|---|---|
| 3.6 | Відкрити `/feedback/moderate/` | Бачить відгук Олени в "Очікують модерації" |
| 3.7 | Натиснути "Опублікувати" | Відгук опублікований, зникає з pending |
| 3.8 | Створити ще один відгук (інше замовлення), натиснути "Виділити" | Відгук опубліковано І виділено |

### 🌐 Будь-хто (без логіну)

| # | Дія | Очікуваний результат |
|---|---|---|
| 3.9 | Відкрити `/feedback/board/` | Бачить обидва відгуки. Виділений — першим |
| 3.10 | Офіціант або кухар спробує `/feedback/moderate/` | 403 (тільки manager) |

---

## Сценарій 4: Безпека та access control

### 🔒 Доступ до чужих замовлень

| # | Дія | Очікуваний результат |
|---|---|---|
| 4.1 | Анонім: `/order/1/` без token | 403 сторінка |
| 4.2 | Анонім: `/order/1/?token=wrong-uuid` | 403 |
| 4.3 | Анонім: `/order/1/?token=<правильний_token>` | 200, бачить замовлення |
| 4.4 | Гість (guest@): створити замовлення, закрити браузер, відкрити URL без ?token | 403 (session втрачена) |
| 4.5 | Гість (guest@): тий самий URL з `?token=` | 200 |
| 4.6 | Офіціант: `/order/1/` (чуже замовлення) | 200 (staff має доступ) |
| 4.7 | ⚠️ Анонім: `/order/1/qr/` | **Зараз: 200 (баг #2). Після фіксу: 403** |

### 🔒 Ролева авторизація

| # | Дія | Очікуваний результат |
|---|---|---|
| 4.8 | Visitor: `/waiter/dashboard/` | 403 |
| 4.9 | Visitor: `/kitchen/dashboard/` | 403 |
| 4.10 | Waiter: `/feedback/moderate/` | 403 |
| 4.11 | Waiter: `/waiter/senior/` | 403 |
| 4.12 | Senior waiter: `/waiter/senior/` | 200 |
| 4.13 | Manager: будь-який dashboard | 200 |

---

## Сценарій 5: Edge cases та error handling

| # | Дія | Очікуваний результат |
|---|---|---|
| 5.1 | Подати відгук для NOT DELIVERED замовлення (POST напряму) | Warning "тільки після отримання" |
| 5.2 | Подати відгук двічі (POST напряму) | Warning "вже залишили" |
| 5.3 | Створити ескалацію одразу після approve (< 5 хв) | Warning "Зачекайте" |
| 5.4 | Створити другу ескалацію при відкритій першій | Warning "вже є активне" |
| 5.5 | Resolve ескалацію, створити нову одразу (< cooldown) | Warning "щойно вирішено" |
| 5.6 | Офіціант: acknowledge ескалацію яка вже acknowledged | Warning "вже оброблена" |
| 5.7 | Офіціант: resolve ескалацію яка вже resolved | Warning "вже вирішена" |
| 5.8 | Відключити мережу на телефоні (order_detail відкритий) | Offline banner, SSE reconnect після повернення |
| 5.9 | Відкрити order_detail без JS (NoScript) | SSR показує поточний стан (graceful degradation) |

---

## Сценарій 6: Staff display labels

| # | Дія | Очікуваний результат |
|---|---|---|
| 6.1 | Кухар з display_title + public_name → взяти тікет | Відвідувач бачить "Повариха Валентина готує" |
| 6.2 | Кухар БЕЗ display_title (тільки role) → взяти тікет | Відвідувач бачить "Виробництво [first_name]" |
| 6.3 | Кухар без будь-яких імен → взяти тікет | Відвідувач бачить "Виробництво [email_prefix]" |
| 6.4 | Офіціант з display_title → delivery | Відвідувач бачить "Офіціант Дмитро" у SSE |

---

## Сценарій 7: Перевірка оплати та ескалації несплачених

| # | Дія | Очікуваний результат |
|---|---|---|
| 7.1 | Замовлення DELIVERED, не оплачене | Офіціант бачить у "Очікують оплати" |
| 7.2 | Зачекати PAY_TIMEOUT (10 хв) | Celery task → payment_escalation_level=1 |
| 7.3 | Senior waiter: `/waiter/senior/` | Бачить ескальоване замовлення |
| 7.4 | Senior: "Підтвердити (готівка)" | payment_status=PAID, зникає з dashboard |
| 7.5 | Зачекати 2×PAY_TIMEOUT без оплати | payment_escalation_level=2, Manager бачить |

---

## Сценарій 8: i18n (перемикання мови)

| # | Дія | Очікуваний результат |
|---|---|---|
| 8.1 | Navbar → language switcher → English | UI рядки на англійській (де перекладені) |
| 8.2 | Kitchen dashboard → English | Кнопки "Take", "Done" (якщо перекладено) |
| 8.3 | Feedback board → English | Заголовок, пустий стан — англійською |
| 8.4 | Повернутись на Українську | Все українською |

---

## Чеклист перед фестивалем

- [ ] Баг #1 (DRAFT→SUBMITTED) зафіксовано
- [ ] Баг #2 (order_qr доступ) зафіксовано
- [ ] Баг #3 (progress bar JS/SSR) зафіксовано
- [ ] Баг #4 (reason validation) зафіксовано
- [ ] Баг #5 (order_approve @require_POST) зафіксовано
- [ ] Сценарій 1 (happy path) пройдений від початку до кінця
- [ ] Сценарій 2 (ескалація) пройдений
- [ ] Сценарій 4 (безпека) пройдений
- [ ] SSE працює на реальному телефоні (не тільки localhost)
- [ ] Celery Beat задачі запущені і працюють
- [ ] Всі staff мають display_title і public_name
- [ ] Переклади (.po) для en як мінімум
- [ ] `uv run pytest` — зелені
