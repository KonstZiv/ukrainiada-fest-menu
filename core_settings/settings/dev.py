"""Development settings — local machine with Docker infra services."""

from .base import *  # noqa: F403, F401
from .env import config

DEBUG = True

# ---------------------------------------------------------------------------
# Database — PostgreSQL via Docker Compose
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="festival_menu"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# ---------------------------------------------------------------------------
# Django Debug Toolbar
# ---------------------------------------------------------------------------

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS: list[str] = ["127.0.0.1"]
