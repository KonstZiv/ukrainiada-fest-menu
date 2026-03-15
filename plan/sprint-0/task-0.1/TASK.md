# Task 0.1 — Реструктуризація проєкту (детально)

## Що робимо

Переводимо навчальний проєкт на production-структуру:
розбиваємо settings, вводимо `pyproject.toml` для uv, створюємо нові порожні аплікації.

## Кроки

### 1. Перейменування і нові аплікації

```bash
# Перейменувати корінь проєкту (якщо ще не зроблено)
# django_1609/ → festival_menu/

# Створити нові аплікації (порожні — заповнюються в наступних спрінтах)
uv run python manage.py startapp orders
uv run python manage.py startapp kitchen
uv run python manage.py startapp notifications
```

### 2. pyproject.toml

Замінити будь-який існуючий `requirements.txt` на `pyproject.toml`:

```toml
[project]
name = "festival-menu"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "django>=5.0",
    "psycopg[binary]>=3.0",
    "python-decouple",
    "celery>=5.3",
    "redis>=5.0",
    "django-celery-beat",
    "django-eventstream",
    "channels-redis",
    "Pillow",
]

[dependency-groups]
dev = [
    "django-debug-toolbar",
    "ruff",
    "mypy>=1.0",
    "django-stubs[compatible-mypy]",
    "pytest",
    "pytest-django",
    "pytest-cov",
]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM"]

[tool.mypy]
plugins = ["mypy_django_plugin.main"]
strict = true
ignore_missing_imports = true

[tool.django-stubs]
django_settings_module = "core_settings.settings.dev"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "core_settings.settings.dev"
python_files = ["test_*.py", "*_test.py"]
markers = [
    "tier1: Fast unit tests, no external dependencies",
    "tier2: Integration tests, requires DB and Redis",
    "tier3: Full E2E and load tests, pre-deploy only",
]
```

### 3. Розбивка settings

**Структура:**
```
core_settings/
├── settings/
│   ├── __init__.py     # порожній
│   ├── base.py         # всі загальні налаштування
│   ├── dev.py          # DEBUG=True, SQLite → потім PostgreSQL
│   └── prod.py         # DEBUG=False, безпека
```

**`settings/base.py`** — перенести з `settings.py` все крім DEBUG-специфічного:
```python
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS: list[str] = config("ALLOWED_HOSTS", default="", cast=lambda v: [s.strip() for s in v.split(",")])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "user",
    "menu",
    "orders",
    "kitchen",
    "notifications",
]

AUTH_USER_MODEL = "user.User"

# ... решта стабільних налаштувань (TEMPLATES, AUTH, STATIC, MEDIA тощо)

# --- Festival service timeouts (minutes) ---
KITCHEN_TIMEOUT: int = config("KITCHEN_TIMEOUT", default=5, cast=int)
MANAGER_TIMEOUT: int = config("MANAGER_TIMEOUT", default=5, cast=int)
PAY_TIMEOUT: int = config("PAY_TIMEOUT", default=10, cast=int)
SPEED_INTERVAL_KITCHEN: int = config("SPEED_INTERVAL_KITCHEN", default=15, cast=int)
```

**`settings/dev.py`:**
```python
from .base import *  # noqa: F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
# PostgreSQL підключається в Task 0.2

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS: list[str] = ["127.0.0.1"]
```

**`settings/prod.py`:**
```python
from .base import *  # noqa: F403

DEBUG = False
# HTTPS, HSTS, secure cookies — заповнюється в Sprint prod-prep
```

### 4. Оновити wsgi.py, asgi.py, celery.py, manage.py

Скрізь замінити:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings")
# →
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")
```

### 5. .env.example

```
SECRET_KEY=change-me-to-random-string
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=festival_menu
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6379/0

KITCHEN_TIMEOUT=5
MANAGER_TIMEOUT=5
PAY_TIMEOUT=10
SPEED_INTERVAL_KITCHEN=15
```

### 6. Dockerfile

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .
```

## Тести для цієї задачі

```python
# tests/test_settings.py
import pytest
from django.conf import settings

@pytest.mark.tier1
def test_required_settings_present():
    assert hasattr(settings, "KITCHEN_TIMEOUT")
    assert hasattr(settings, "MANAGER_TIMEOUT")
    assert hasattr(settings, "PAY_TIMEOUT")
    assert hasattr(settings, "SPEED_INTERVAL_KITCHEN")

@pytest.mark.tier1
def test_new_apps_installed():
    assert "orders" in settings.INSTALLED_APPS
    assert "kitchen" in settings.INSTALLED_APPS
    assert "notifications" in settings.INSTALLED_APPS
```

## Acceptance criteria

- [ ] `uv sync` — встановлює всі залежності без помилок
- [ ] `uv run python manage.py check` — 0 помилок
- [ ] `uv run ruff check .` — 0 помилок
- [ ] `uv run mypy .` — 0 помилок
- [ ] `uv run pytest -m tier1` — всі тести зелені
- [ ] Файл `.env.example` присутній і містить всі змінні
- [ ] Аплікації `orders`, `kitchen`, `notifications` — створені і в `INSTALLED_APPS`
