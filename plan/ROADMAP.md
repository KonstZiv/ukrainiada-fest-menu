# Ukrainiada Festival Menu — Roadmap: Sprint 8–11

## Контекст

Після завершення Sprint 0–7 (інфраструктура → меню → замовлення → кухня → оплата → SSE → QR handoff → i18n → responsive UI + PWA) система готова до першого фестивалю. Спринти 8–11 додають три речі:

1. **Підготовка та безпека** — закриття прогалин перед production
2. **Інтерактивність для відвідувачів** — live tracking, ескалація, зворотний зв'язок
3. **Персоналізація** — "Повариха Валентина готує ваш борщ"

---

## Карта спринтів

```
Sprint 8  🔴 Критичний    Підготовка, безпека, персоналізація staff
Sprint 9  🟡 Високий      Live Order Tracking для відвідувача
Sprint 10 🟡 Високий      Ескалація від відвідувача
Sprint 11 🟢 Середній     Відгуки та Дошка повідомлень
```

### Залежності

```
Sprint 7 (done)
    ↓
Sprint 8 — безпека, display_title, location_hint, i18n UI
    ↓
Sprint 9 — SSE visitor channel, live tracking, timeline
    ↓
Sprint 10 — VisitorEscalation, auto-escalation, staff resolve
    ↓
Sprint 11 — GuestFeedback, form, public board, moderation
```

Sprint 10 і 11 можна робити паралельно — вони незалежні одне від одного (обидва залежать від Sprint 9).

---

## Огляд задач

### Sprint 8 — Підготовка (8–10 год)

| # | Задача | Оцінка | Нові моделі/поля |
|---|---|---|---|
| 8.1 | Staff display: `display_title` + `public_name` | 2 год | User +2 fields |
| 8.2 | Безпека: order access token | 2.5 год | Order +1 field |
| 8.3 | Необов'язкова підказка місця | 0.5 год | Order +1 field |
| 8.4 | i18n UI рядків (`{% trans %}`) | 2.5 год | .po файли |

### Sprint 9 — Live Order Tracking (8–10 год)

| # | Задача | Оцінка | Ключове |
|---|---|---|---|
| 9.1 | SSE-канал для відвідувача | 2 год | `visitor-order-{id}` channel |
| 9.2 | Push-події при зміні тікетів | 2 год | 6 нових event types |
| 9.3 | order_detail: live UI + JS-клієнт | 2.5 год | OrderTracker class |
| 9.4 | Візуальний timeline прогресу | 2 год | Progress bar component |

### Sprint 10 — Ескалація від відвідувача (8–10 год)

| # | Задача | Оцінка | Ключове |
|---|---|---|---|
| 10.1 | Модель `VisitorEscalation` + сервіси | 2.5 год | Нова модель + anti-spam |
| 10.2 | Visitor UI: кнопка + modal | 2 год | Emoji причини + коментар |
| 10.3 | Celery auto-escalation | 2 год | Waiter → Senior → Manager |
| 10.4 | Staff UI: acknowledge + resolve | 2 год | Dashboard інтеграція |

### Sprint 11 — Відгуки та Дошка (6–8 год)

| # | Задача | Оцінка | Ключове |
|---|---|---|---|
| 11.1 | Модель `GuestFeedback` + сервіси | 2 год | Нова app `feedback/` |
| 11.2 | Форма відгуку (post-delivery) | 2 год | Emoji mood selector |
| 11.3 | Публічна дошка + модерація | 2.5 год | Board page + manager view |

---

## Нові моделі (зведення)

| Модель | App | Поля |
|---|---|---|
| User (розширення) | user | +`display_title`, +`public_name`, +`staff_label` property |
| Order (розширення) | orders | +`access_token` (UUID), +`location_hint` |
| VisitorEscalation | orders | order FK, reason, message, level, status, resolved_by |
| GuestFeedback | feedback (new) | order O2O, mood, message, visitor_name, is_published |

## Нові SSE-канали

| Канал | Підписник | Trigger |
|---|---|---|
| `visitor-order-{order_id}` | Відвідувач | Зміна тікетів, статусу замовлення, ескалації |

## Нові SSE-події

| Подія | Канал | Trigger |
|---|---|---|
| `ticket_taken` (visitor) | visitor-order | Кухар взяв тікет |
| `ticket_done` (visitor) | visitor-order | Страва готова |
| `order_approved` (visitor) | visitor-order | Офіціант підтвердив |
| `order_ready` (visitor) | visitor-order | Всі страви готові |
| `dish_collecting` (visitor) | visitor-order | Офіціант забрав страву |
| `order_delivered` (visitor) | visitor-order | Доставлено |
| `escalation_created` | visitor-order | Ескалація створена |
| `escalation_acknowledged` | visitor-order | Staff побачив |
| `escalation_resolved` | visitor-order | Staff вирішив |
| `escalation_level_up` | visitor-order | Авто-підвищення рівня |
| `visitor_escalation` | waiter/manager | Нова ескалація |

## Нові Celery tasks

| Task | Schedule | Логіка |
|---|---|---|
| `orders.escalate_visitor_issues` | Кожну хвилину | OPEN level 1→2→3 |

## Нові settings

```python
ESCALATION_AUTO_LEVEL: int = 3    # хв — авто-підняття рівня ескалації
ESCALATION_COOLDOWN: int = 5      # хв — мінімум між ескалаціями
ESCALATION_MIN_WAIT: int = 5      # хв — після approve перед ескалацією
```

---

## Загальна оцінка

| Sprint | Оцінка | Кумулятивно |
|---|---|---|
| Sprint 8 | 8–10 год | 8–10 год |
| Sprint 9 | 8–10 год | 16–20 год |
| Sprint 10 | 8–10 год | 24–30 год |
| Sprint 11 | 6–8 год | 30–38 год |

---

## Що залишається в backlog (після Sprint 11)

### Високий пріоритет
- [ ] Темна тема для staff (кухня під сонцем)
- [ ] Manager dashboard responsive
- [ ] Повний переклад .po для всіх 7 мов

### Середній пріоритет
- [ ] Web Push notifications (order_ready при закритій вкладці)
- [ ] Estimated time ("ваше замовлення через ~10 хв")
- [ ] Статистика ескалацій для менеджера
- [ ] "Подякувати кухарю" — feedback прив'язаний до staff
- [ ] SSE live-feed нових відгуків на дошці
- [ ] Автоматичний resolve ескалації при delivery

### Низький пріоритет
- [ ] Інтеграція з реальним payment gateway
- [ ] E2E тести (Playwright)
- [ ] Load тести (locust)
- [ ] Lighthouse PWA ≥ 80
- [ ] CSS-модуляризація
- [ ] Окремі base_staff.html / base_visitor.html
- [ ] Kiosk mode для дошки відгуків
- [ ] QR на столі → прямий лінк на форму відгуку

---

## Структура файлів плану

```
sprint-8/
├── SPRINT.md
├── task-8.1/  (Staff display)     ├── TASK.md  └── BOARD.md
├── task-8.2/  (Access token)      ├── TASK.md  └── BOARD.md
├── task-8.3/  (Table label)       ├── TASK.md  └── BOARD.md
└── task-8.4/  (i18n UI)           ├── TASK.md  └── BOARD.md

sprint-9/
├── SPRINT.md
├── task-9.1/  (Visitor SSE)       ├── TASK.md  └── BOARD.md
├── task-9.2/  (Push events)       ├── TASK.md  └── BOARD.md
├── task-9.3/  (Live UI + JS)      ├── TASK.md  └── BOARD.md
└── task-9.4/  (Timeline)          ├── TASK.md  └── BOARD.md

sprint-10/
├── SPRINT.md
├── task-10.1/ (Escalation model)  ├── TASK.md  └── BOARD.md
├── task-10.2/ (Visitor UI)        ├── TASK.md  └── BOARD.md
├── task-10.3/ (Celery auto-esc)   ├── TASK.md  └── BOARD.md
└── task-10.4/ (Staff resolve UI)  ├── TASK.md  └── BOARD.md

sprint-11/
├── SPRINT.md
├── task-11.1/ (Feedback model)    ├── TASK.md  └── BOARD.md
├── task-11.2/ (Feedback form)     ├── TASK.md  └── BOARD.md
└── task-11.3/ (Board + moderation)├── TASK.md  └── BOARD.md

ROADMAP.md  ← цей файл
```
