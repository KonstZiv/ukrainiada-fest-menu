# Task 0.3 — Celery + Redis (детально)

## Що робимо

Підключаємо Celery як брокер задач для фонових таймаутів і ескалацій.
django-celery-beat — для periodic tasks (перевірка таймаутів кожну хвилину).

## Кроки

### 1. core_settings/celery.py

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")

app = Celery("festival_menu")

# Беремо конфіг з Django settings, префікс CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Автоматично знаходить tasks.py у всіх INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # type: ignore[type-arg]
    """Тестова задача для перевірки що Celery працює."""
    print(f"Request: {self.request!r}")
```

### 2. core_settings/__init__.py

```python
from .celery import app as celery_app

__all__ = ("celery_app",)
```

### 3. settings/base.py — додати Celery конфіг

```python
from decouple import config as env_config

CELERY_BROKER_URL: str = env_config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND: str = env_config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT: list[str] = ["json"]
CELERY_TASK_SERIALIZER: str = "json"
CELERY_RESULT_SERIALIZER: str = "json"
CELERY_TIMEZONE: str = "Europe/Podgorica"  # фестиваль у Чорногорії

# django-celery-beat: зберігає розклад у БД
CELERY_BEAT_SCHEDULER: str = "django_celery_beat.schedulers:DatabaseScheduler"

# Додати до INSTALLED_APPS в base.py:
# "django_celery_beat",
# "django_celery_results",  # опціонально
```

### 4. Додати django_celery_beat до INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    "django_celery_beat",
]
```

### 5. Тестова задача запуску

```bash
# Термінал 1: worker
uv run celery -A core_settings worker -l info

# Термінал 2: beat
uv run celery -A core_settings beat -l info

# Термінал 3: перевірка
uv run python manage.py shell
>>> from core_settings.celery import debug_task
>>> debug_task.delay()
```

## Тести

```python
# tests/test_celery.py
import pytest
from unittest.mock import patch

@pytest.mark.tier1
def test_debug_task_exists():
    from core_settings.celery import debug_task
    assert callable(debug_task)

@pytest.mark.tier2
def test_celery_task_execution(celery_worker):
    """Потребує pytest-celery або celery.contrib.pytest."""
    from core_settings.celery import debug_task
    result = debug_task.delay()
    # Якщо worker не запущений — задача ставиться в чергу без помилки
    assert result is not None

@pytest.mark.tier1
def test_celery_settings():
    from django.conf import settings
    assert hasattr(settings, "CELERY_BROKER_URL")
    assert hasattr(settings, "CELERY_BEAT_SCHEDULER")
    assert "django_celery_beat" in settings.INSTALLED_APPS
```

## Acceptance criteria

- [ ] `uv run python manage.py migrate` — міграції django_celery_beat пройшли
- [ ] `uv run celery -A core_settings worker -l info` — стартує без помилок
- [ ] `debug_task.delay()` — задача виконується у worker
- [ ] `uv run pytest -m tier1 tests/test_celery.py` — зелені
