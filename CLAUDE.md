# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django 6+ restaurant menu management system for the Ukrainiada festival ("Jadran Sun"). Features: menu CRUD (categories, tags, dishes with images), user auth via email, avatar processing, search, SSE notifications. UI in Ukrainian, code in English.

## Commands

```bash
# Install dependencies
uv sync --group dev

# Start dev infrastructure (PostgreSQL + Redis)
docker compose -f compose.dev.yml --env-file .env-dev up -d

# Run migrations
uv run python manage.py migrate

# Load fixture data (categories, tags, dishes with images)
uv run python manage.py loaddata fixtures/menu_data.json

# Run dev server
uv run python manage.py runserver

# Tests
uv run pytest                                          # all tests
uv run pytest --cov=menu --cov=user --cov-report=term-missing  # with coverage
uv run pytest menu/tests.py -k "test_name"             # single test

# Linting & formatting
uv run ruff check .
uv run ruff format .
uv run mypy .

# Pre-commit (runs automatically on git commit)
uv run pre-commit run --all-files
```

## Architecture

**Django apps:**
- `core_settings/` — project settings (split: base/dev/prod), root URL config, ASGI with SSE, Celery app, debug toolbar (auto-enabled when DEBUG=True)
- `menu/` — categories, tags, dishes with image models (SVG for logos, ImageField for dishes)
- `user/` — custom User model with email as USERNAME_FIELD, avatar crop/resize on save, role-based access (Manager, Kitchen, Waiter, Visitor)
- `orders/` — order management (empty, Sprint 1+)
- `kitchen/` — kitchen display system (empty, Sprint 1+)
- `notifications/` — SSE channels and event helpers via django-eventstream

**Key design decisions:**
- Image models are separate (CategoryLogo, TagLogo, DishMainImage, DishPicture) linked via OneToOneField/ForeignKey — not fields on the parent model
- Views use a mix of FBVs (categories, dish_list, search) and CBVs (tags use ListView/CreateView/UpdateView/DeleteView, dishes use CreateView/UpdateView/DeleteView)
- Dish create/edit handles 3 forms simultaneously: DishForm + DishMainImageForm (prefix="main_image") + DishPictureFormSet (inlineformset_factory)
- Category create/edit handles 2 forms: CategoryForm + CategoryLogoForm (prefix="logo")
- SVG uploads validated by both FileExtensionValidator and custom `validate_svg_content` (checks for `<svg>` / `<?xml>` markers)
- Avatar processing: crop to min aspect ratio 0.7, resize to max 256×256 (settings: USER_AVATAR_ASPECT_RATIO, USER_AVATAR_MAX_PIXELS)
- QuerySet optimization: `select_related` for OneToOne joins, `Prefetch` objects for nested prefetching in category_list
- Dish.availability (AVAILABLE/LOW/OUT) — OUT dishes hidden from visitors, visible to staff
- Settings use explicit env file loader (`env.py`): dev reads `.env-dev`, prod reads `.env`, CI uses env vars

**Database:** PostgreSQL 18 (via Docker Compose). AUTH_USER_MODEL = "user.User".

**Templates:** Bootstrap 5.3 + Bootstrap Icons. Component includes: `_navbar.html`, `_dish_card.html`, `_nav_pills.html`, `_order_fab.html`. Custom template filter `highlight` in `menu/templatetags/menu_extras.py`.

**Media uploads:** `upload_image()` helper generates UUID-based filenames. Directories: `category_logos/`, `tag_logos/`, `dish_main_images/`, `dish_pictures/`, `avatars/`.

## CI/CD (.github/workflows/ci.yml)

Runs on PRs/pushes to dev/main: `ruff check` + `ruff format --check`, `mypy`, `pytest --cov` (PostgreSQL service). AI review via Gemini on PRs only. Required secrets: `SECRET_KEY`, `CI_DB_PASSWORD`.

## Python Version

Requires Python >=3.14.
