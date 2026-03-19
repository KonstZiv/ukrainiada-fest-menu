"""Production settings — deployed environment."""

from .base import *  # noqa: F403
from .env import config

DEBUG = False

# ---------------------------------------------------------------------------
# Database — PostgreSQL with persistent connections
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}

# ---------------------------------------------------------------------------
# Security — HTTPS hardening
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS: list[str] = [
    f"https://{h}" for h in config("ALLOWED_HOSTS", default="").split(",") if h
]

# ---------------------------------------------------------------------------
# Static files — served by nginx from collected directory
# ---------------------------------------------------------------------------

STATIC_ROOT = BASE_DIR / "static_collected"  # noqa: F405
