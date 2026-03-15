# Task 0.7 — Docker Compose dev (детально)

## Що робимо

Docker Compose для локальної розробки: PostgreSQL, Redis, Django (ASGI), Celery worker, Celery beat.

## Файли

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Встановлюємо uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Спочатку тільки pyproject.toml — кешування шару залежностей
COPY pyproject.toml .
RUN uv sync --no-dev

# Потім весь код
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
```

### docker-compose.dev.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-festival_menu}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: >
      sh -c "uv run python manage.py migrate &&
             uv run python -m uvicorn core_settings.asgi:application
             --host 0.0.0.0 --port 8000 --reload"
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery:
    build: .
    command: uv run celery -A core_settings worker -l info -c 2
    volumes:
      - .:/app
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery-beat:
    build: .
    command: uv run celery -A core_settings beat -l info
    volumes:
      - .:/app
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
```

### .env (для локального запуску, не в git)

```
SECRET_KEY=local-dev-secret-key-change-in-prod
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

DB_NAME=festival_menu
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

KITCHEN_TIMEOUT=5
MANAGER_TIMEOUT=5
PAY_TIMEOUT=10
SPEED_INTERVAL_KITCHEN=15
```

⚠️ `DB_HOST=db` — hostname сервісу в Docker мережі (не `localhost`).

### .dockerignore

```
.git
.env
*.pyc
__pycache__
.pytest_cache
.mypy_cache
.ruff_cache
db.sqlite3
media/
```

## Перевірка

```bash
# Підняти все
docker compose -f docker-compose.dev.yml up --build

# Перевірити що всі сервіси живі
docker compose -f docker-compose.dev.yml ps

# Перевірити міграції
docker compose -f docker-compose.dev.yml exec web uv run python manage.py showmigrations

# Перевірити Celery
docker compose -f docker-compose.dev.yml exec celery uv run celery -A core_settings inspect active

# Перевірити SSE
curl -N http://localhost:8000/events/manager/
```

## Тести

```python
# tests/test_docker_config.py
import pytest
import os

@pytest.mark.tier1
def test_env_example_has_required_keys():
    """Перевіряємо що .env.example містить всі потрібні змінні."""
    required_keys = {
        "SECRET_KEY", "DEBUG", "DB_NAME", "DB_USER",
        "DB_PASSWORD", "DB_HOST", "DB_PORT", "REDIS_URL",
        "KITCHEN_TIMEOUT", "MANAGER_TIMEOUT", "PAY_TIMEOUT",
        "SPEED_INTERVAL_KITCHEN",
    }
    env_example_path = os.path.join(
        os.path.dirname(__file__), "..", ".env.example"
    )
    with open(env_example_path) as f:
        content = f.read()
    for key in required_keys:
        assert key in content, f"Missing key in .env.example: {key}"
```

## Acceptance criteria

- [ ] `docker compose -f docker-compose.dev.yml up --build` — всі 5 сервісів запущені
- [ ] `web` сервіс: міграції пройшли автоматично при старті
- [ ] `http://localhost:8000/admin/` — відповідає 200
- [ ] `celery` сервіс: у логах `celery@... ready`
- [ ] `celery-beat` сервіс: у логах `beat: Starting...`
- [ ] `curl -N http://localhost:8000/events/manager/` — тримає з'єднання
- [ ] `.dockerignore` присутній
- [ ] `uv run pytest -m tier1 tests/test_docker_config.py` — зелені
