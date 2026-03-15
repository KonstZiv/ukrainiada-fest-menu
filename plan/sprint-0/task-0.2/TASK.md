# Task 0.2 — PostgreSQL + psycopg3 (детально)

## Що робимо

Перемикаємо dev-середовище з SQLite на PostgreSQL з psycopg v3.

## Важливо про psycopg v3

Django 4.2+ підтримує psycopg v3 нативно — окремого адаптера не треба.
`psycopg[binary]` — бінарна збірка, не потребує системного libpq.
Engine той самий: `django.db.backends.postgresql`.

## Кроки

### 1. settings/dev.py — замінити DATABASES

```python
from decouple import config

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="festival_menu"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            # psycopg3: підтримка prepared statements (опціонально, але корисно)
            "prepare_threshold": 10,
        },
    }
}
```

### 2. settings/prod.py — аналогічно, але без дефолтів

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,  # connection pooling у prod
    }
}
```

### 3. Локальна БД (якщо без Docker)

```bash
createdb festival_menu
uv run python manage.py migrate
```

### 4. Перевірка міграцій

Всі існуючі міграції `user` і `menu` мають пройти без змін.
psycopg3 сумісний з усіма стандартними Django-міграціями.

## Тести

```python
# tests/test_db.py
import pytest
from django.db import connection

@pytest.mark.tier2
@pytest.mark.django_db
def test_postgresql_connection():
    """Перевіряємо що використовується PostgreSQL, не SQLite."""
    vendor = connection.vendor
    assert vendor == "postgresql", f"Expected postgresql, got {vendor}"

@pytest.mark.tier2
@pytest.mark.django_db
def test_migrations_applied():
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    assert len(plan) == 0, f"Unapplied migrations: {plan}"
```

## Acceptance criteria

- [ ] `uv run python manage.py migrate` — 0 помилок на PostgreSQL
- [ ] `uv run python manage.py dbshell` — підключається до PostgreSQL
- [ ] `uv run pytest -m tier2 tests/test_db.py` — зелені
