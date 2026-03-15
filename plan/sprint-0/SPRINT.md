# Sprint 0 — Фундамент і налаштування

## Board (коротко)

**Мета:** перетворити навчальний проєкт на production-ready основу.
**Оцінка:** 6–8 годин
**Залежності:** немає (перший спрінт)
**Результат:** запущений Docker Compose, PostgreSQL, Celery, SSE-інфраструктура, повний набір ролей, `Dish.availability`.

### Задачі

| # | Назва | Оцінка |
|---|---|---|
| 0.1 | Реструктуризація проєкту | 1 год |
| 0.2 | PostgreSQL + psycopg3 | 0.5 год |
| 0.3 | Celery + Redis | 1 год |
| 0.4 | Бізнес-константи в settings | 0.5 год |
| 0.5 | Ролі і Dish.availability | 1 год |
| 0.6 | SSE базова інфраструктура | 1.5 год |
| 0.7 | Docker Compose dev | 1 год |

---

## Детальний опис для виконавця

### Вхідні дані

Існуючий Django-проєкт `django_1609` (навчальний "Jadran Sun"):
- `menu/` — `Category`, `Dish`, `Tag`, `CategoryLogo`, `DishMainImage`, `DishPicture`
- `user/` — кастомний `User` (email auth), `Role` (manager, production, finance, waiter, visitor)
- `core_settings/` — settings (SQLite), urls, wsgi/asgi
- Стек: Django 5.0, Pillow, debug-toolbar

### Що НЕ чіпаємо в цьому спрінті

- Жодна існуюча функціональність меню не ламається
- Всі існуючі міграції лишаються, нові — тільки additive
- Шаблони і views меню — без змін

### Порядок виконання

Строго по номерах задач: 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.7.
Кожна задача — окремий git commit з префіксом `[S0.N]`.

### Definition of Done

- [ ] `docker compose -f docker-compose.dev.yml up` піднімає всі сервіси без помилок
- [ ] `uv run python manage.py migrate` проходить на PostgreSQL (0 помилок)
- [ ] `uv run pytest -m tier1` — всі тести зелені
- [ ] `uv run ruff check .` — 0 помилок
- [ ] `uv run mypy .` — 0 помилок (або тільки known issues з django-stubs)
- [ ] `User.Role` містить 6 ролей: manager, kitchen_supervisor, kitchen, senior_waiter, waiter, visitor
- [ ] `Dish.availability` є в БД, в адмінці, фільтрація працює
- [ ] Celery worker стартує, виконує тестову задачу `debug_task`
- [ ] SSE-ендпоінт `/events/<channel>/` відповідає 200 (перевірити curl)
- [ ] `.env.example` містить усі змінні
