# Ukrainiada Fest Menu

Restaurant menu management system for the Ukrainiada festival ("Jadran Sun").
Django 6+, PostgreSQL, Redis, Celery, SSE (django-eventstream).

## Quick Start

### Prerequisites

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) — package manager
- Docker & Docker Compose — for PostgreSQL and Redis

### Setup

```bash
# 1. Install dependencies
uv sync --group dev

# 2. Create .env-dev from template
cp .env.example .env-dev
# Edit .env-dev: set SECRET_KEY, DB_PASSWORD

# 3. Start infrastructure (PostgreSQL 18 + Redis 8)
docker compose -f compose.dev.yml --env-file .env-dev up -d

# 4. Run migrations
uv run python manage.py migrate

# 5. Load sample data (categories, tags, dishes)
uv run python manage.py loaddata fixtures/menu_data.json

# 6. Start dev server
uv run python manage.py runserver
```

Open http://localhost:8000/menu/

### Pre-commit hooks

```bash
uv run pre-commit install
```

Runs automatically on each commit: ruff check, ruff format, mypy, trailing-whitespace, end-of-file-fixer.

## Project Structure

```
core_settings/     # Settings (base/dev/prod), URLs, ASGI, Celery
menu/              # Categories, tags, dishes, images
user/              # Custom User (email auth), roles, avatars
orders/            # Order management (Sprint 1+)
kitchen/           # Kitchen display (Sprint 1+)
notifications/     # SSE channels and events
fixtures/          # Database fixtures for seeding
templates/         # Django templates (Bootstrap 5.3)
```

## License

Private project.
