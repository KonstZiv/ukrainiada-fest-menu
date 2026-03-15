# Festival Menu — Project Overview

## Контекст

Сервіс для ресторанного обслуговування на фестивалі української культури і їжі
в Херцег-Нові (Чорногорія). Проводиться двічі на рік, до 2000 відвідувачів.
Волонтери готують страви, виручка — на підтримку Українського Культурного Центру.

**Ключові проблеми, які вирішує сервіс:**
- Пікові навантаження і черги
- Мовний бар'єр (UA, EN, ME, DE, HR, AL, BS...)
- Незнайомість відвідувачів з українською кухнею

---

## Tech Stack

| Компонент | Технологія |
|---|---|
| Backend | Django 5.0+ |
| DB | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Task queue | Celery + django-celery-beat |
| Real-time | SSE (django-eventstream) |
| Package manager | uv |
| Linter | ruff |
| Type checker | mypy + django-stubs |
| DB driver | psycopg (v3) |
| Containerization | Docker Compose |

---

## Ролі користувачів

| Role key | Назва | Опис |
|---|---|---|
| `visitor` | Відвідувач | Переглядає меню, формує замовлення |
| `waiter` | Офіціант | Підтверджує замовлення, контролює оплату, передає страви |
| `senior_waiter` | Старший офіціант | Отримує ескальовані несплачені замовлення |
| `kitchen` | Виробництво | Бере страви в роботу, видає офіціанту |
| `kitchen_supervisor` | Старший кухні | Отримує ескальовані нічийні замовлення |
| `manager` | Менеджер | Фінальна ескалація всіх проблем, повний огляд |

---

## Ключові бізнес-константи (settings/base.py)

```python
KITCHEN_TIMEOUT: int = 5        # хв — нічийне замовлення → kitchen_supervisor
MANAGER_TIMEOUT: int = 5        # хв — після KITCHEN_TIMEOUT → manager
PAY_TIMEOUT: int = 10           # хв — несплачено після отримання → senior_waiter
SPEED_INTERVAL_KITCHEN: int = 15  # хв — вікно підрахунку throughput
```

---

## Pipeline замовлення

```
visitor: draft
    ↓ (показує QR офіціанту)
waiter: submitted → approved
    ↓ (розподіл по виробництвах)
kitchen: pending → in_progress → ready
    ↓ (QR-передача офіціанту)
waiter: collecting → delivered
    ↓
waiter: payment confirmed
```

**Статуси `Order`:**
`draft` → `submitted` → `approved` → `in_progress` → `ready` → `delivered`

**Статуси оплати `Order`:**
`unpaid` → `paid`

---

## Доступність страв (Dish.availability)

| Значення | Відображення в меню |
|---|---|
| `available` | Нормально відображається |
| `low` | "Уточнюйте у офіціанта" |
| `out` | Не відображається |

---

## Структура проєкту

```
festival_menu/
├── core_settings/        # Django settings, urls, celery, asgi
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── celery.py
│   ├── asgi.py
│   └── urls.py
├── menu/                 # Страви, категорії, теги (існує)
├── user/                 # Користувачі, ролі (існує, розширюється)
├── orders/               # Замовлення, OrderItem
├── kitchen/              # Кухонний pipeline, KitchenAssignment
├── notifications/        # SSE-канали, події
├── templates/
├── staticfiles/
├── pyproject.toml
├── docker-compose.dev.yml
├── Dockerfile
└── .env.example
```

---

## Загальні правила розробки

### Код
- Весь код — з type annotations (mypy строгий режим)
- ruff — linter і formatter, запускається в pre-commit і CI
- Docstrings для всіх публічних методів і класів
- `select_related` / `prefetch_related` — обов'язково де є FK/M2M у views
- `transaction.atomic()` — всі операції що зачіпають ≥2 моделей
- Бізнес-логіка — в сервісних функціях або методах моделі, НЕ у views
- Views — тонкі: приймають запит, делегують, повертають відповідь

### Git
- Гілки: `feature/sprint-N-task-M-short-name`
- Commit message: `[S0.1] Add project structure` (номер таски в префіксі)
- MR — обов'язково проходить Tier 1 і Tier 2 тести

### Міграції
- Кожна зміна моделі — окрема міграція
- Назва міграції — описова: `0004_add_dish_availability`
- Squash міграцій — тільки перед major release

---

## Тестування — Три рівні

### Tier 1 — Fast (кожен MR, кожен push)
**Час:** < 60 секунд
**Запуск:** `pytest -m tier1`
**Що входить:**
- Unit-тести моделей (без DB — `@pytest.mark.django_db` НЕ використовується де можливо)
- Тести валідаторів і форм (з `TestCase` або factory)
- Тести утилітарних функцій і сервісів (mock зовнішніх залежностей)
- Тести URL-routing (статус-коди, redirect)
- Тести серіалізації / десеріалізації

**Правило:** жодного реального звернення до БД, Redis, Celery.

### Tier 2 — Integration (MR у `dev` та `main`)
**Час:** < 5 хвилин
**Запуск:** `pytest -m tier2`
**Що входить:**
- Інтеграційні тести views з реальною тестовою БД
- Тести Celery-задач (з `celery.contrib.pytest`, broker в пам'яті)
- Тести pipeline замовлення (повний цикл через моделі)
- Тести ескалації (таймаути через mock `django.utils.timezone.now`)
- Тести ролей і пермішенів

**Правило:** реальна БД (PostgreSQL у CI), Redis mock або testcontainers.

### Tier 3 — Full (тільки перед деплоєм)
**Час:** необмежений
**Запуск:** `pytest -m tier3`
**Що входить:**
- E2E тести повного pipeline (Selenium або Playwright)
- Load тести (locust) — пікове навантаження ~200 одночасних користувачів
- Тести SSE (реальний Redis, channel layers)
- Тести QR-флоу
- Smoke тести production-конфіга

**Правило:** окреме CI-середовище, запускається вручну або по тегу `release/*`.

### Маркування тестів

```python
# conftest.py або pytest.ini
[pytest]
markers =
    tier1: Fast unit tests, no external dependencies
    tier2: Integration tests, requires DB and Redis
    tier3: Full E2E and load tests, pre-deploy only
```

```python
# Приклад маркування
@pytest.mark.tier1
def test_dish_availability_default():
    ...

@pytest.mark.tier2
@pytest.mark.django_db
def test_order_pipeline_full():
    ...

@pytest.mark.tier3
def test_peak_load_200_users():
    ...
```

### CI конфігурація (GitHub Actions / GitLab CI)

```yaml
# Кожен push/MR
test-fast:
  script: pytest -m tier1

# MR у dev або main
test-integration:
  script: pytest -m "tier1 or tier2"
  only: [merge_requests]
  variables:
    CI_BRANCH: [dev, main]

# Тег release/*
test-full:
  script: pytest -m "tier1 or tier2 or tier3"
  only: [/^release\/.*/]
```

---

## SSE-канали (реалізація в Sprint 4)

| Канал | Підписники | Події |
|---|---|---|
| `kitchen-{user_id}` | kitchen, kitchen_supervisor | нове замовлення, ескалація |
| `waiter-{user_id}` | waiter, senior_waiter | страва готова, ескалація оплати |
| `manager` | manager | всі ескалації |

---

## .env.example

```
SECRET_KEY=change-me
DEBUG=True
DB_NAME=festival_menu
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
```
