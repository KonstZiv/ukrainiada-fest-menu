"""Development settings — local machine with Docker infra services."""

from .base import *  # noqa: F403
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

# Use plain static storage in dev — ManifestStaticFilesStorage needs collectstatic
STORAGES = {  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS: list[str] = ["127.0.0.1"]

# ---------------------------------------------------------------------------
# Logging — verbose console for development
# ---------------------------------------------------------------------------

import copy  # noqa: E402

LOGGING = copy.deepcopy(LOGGING)  # noqa: F405

for _logger_name in ("notifications", "notifications.sse", "db.monitor"):
    LOGGING["loggers"][_logger_name]["level"] = "DEBUG"  # type: ignore[index]

# Uncomment to see SQL queries:
# LOGGING["loggers"]["django.db.backends"] = {  # type: ignore[index]
#     "handlers": ["console"],
#     "level": "DEBUG",
#     "propagate": False,
# }
