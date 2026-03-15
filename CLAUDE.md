# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django 6+ restaurant menu management system for the Ukrainiada festival ("Jadran Sun"). Features: menu CRUD (categories, tags, dishes with images), user auth via email, avatar processing, search. UI in Ukrainian, code in English.

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run dev server
uv run python manage.py runserver

# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Seed database (run in order)
uv run python fill_categories.py
uv run python fill_tags.py
uv run python fill_full_menu.py

# Tests
uv run pytest                                          # all tests
uv run pytest --cov=menu --cov=user --cov-report=term-missing  # with coverage
uv run pytest menu/tests.py -k "test_name"             # single test

# Linting & formatting
uv run ruff check .
uv run ruff format .
uv run mypy .
```

## Architecture

**Django apps:**
- `core_settings/` — project settings, root URL config, debug toolbar (auto-enabled when DEBUG=True)
- `menu/` — categories, tags, dishes with image models (SVG for logos, ImageField for dishes)
- `user/` — custom User model with email as USERNAME_FIELD, avatar crop/resize on save

**Key design decisions:**
- Image models are separate (CategoryLogo, TagLogo, DishMainImage, DishPicture) linked via OneToOneField/ForeignKey — not fields on the parent model
- Views use a mix of FBVs (categories, dish_list, search) and CBVs (tags use ListView/CreateView/UpdateView/DeleteView, dishes use CreateView/UpdateView/DeleteView)
- Dish create/edit handles 3 forms simultaneously: DishForm + DishMainImageForm (prefix="main_image") + DishPictureFormSet (inlineformset_factory)
- Category create/edit handles 2 forms: CategoryForm + CategoryLogoForm (prefix="logo")
- SVG uploads validated by both FileExtensionValidator and custom `validate_svg_content` (checks for `<svg>` / `<?xml>` markers)
- Avatar processing: crop to min aspect ratio 0.7, resize to max 256×256 (settings: USER_AVATAR_ASPECT_RATIO, USER_AVATAR_MAX_PIXELS)
- QuerySet optimization: `select_related` for OneToOne joins, `Prefetch` objects for nested prefetching in category_list

**Database:** SQLite3 (db.sqlite3). AUTH_USER_MODEL = "user.User".

**Templates:** Bootstrap 5.3 + Bootstrap Icons. Component includes: `_navbar.html`, `_dish_card.html`, `_nav_pills.html`, `_order_fab.html`. Custom template filter `highlight` in `menu/templatetags/menu_extras.py`.

**Media uploads:** `upload_image()` helper generates UUID-based filenames. Directories: `category_logos/`, `tag_logos/`, `dish_main_images/`, `dish_pictures/`, `avatars/`.

## CI/CD (.gitlab-ci.yml)

Runs on MRs to dev/main: `ruff check` + `ruff format --check`, `mypy`, `pytest --cov`. AI review via Gemini on MRs only.

## Python Version

Requires Python >=3.14.
