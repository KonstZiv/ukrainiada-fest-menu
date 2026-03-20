"""Production settings — deployed environment."""

from .base import *  # noqa: F403
from .env import config

DEBUG = False

# ---------------------------------------------------------------------------
# Database — short-lived connections (safe for ASGI + Celery)
#
# CONN_MAX_AGE=0: close connection after each request.
# ASGI (uvicorn) runs sync views in a thread pool — each thread gets its own
# DB connection.  With CONN_MAX_AGE>0 those connections stay open indefinitely
# because thread-local storage is never cleaned up, eventually exhausting
# PostgreSQL max_connections.
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        # PgBouncer transaction pooling requires this — server-side cursors
        # span multiple queries (DECLARE/FETCH/CLOSE) and with transaction
        # pooling each query may hit a different backend connection.
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
}

# ---------------------------------------------------------------------------
# Connection monitoring thresholds
# ---------------------------------------------------------------------------

DB_CONNECTIONS_WARN: int = config("DB_CONNECTIONS_WARN", default=60, cast=int)
DB_CONNECTIONS_CRITICAL: int = config("DB_CONNECTIONS_CRITICAL", default=80, cast=int)

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
