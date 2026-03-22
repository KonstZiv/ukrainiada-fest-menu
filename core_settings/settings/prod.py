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

# ---------------------------------------------------------------------------
# Logging — file handlers with daily rotation, 14 days retention
# ---------------------------------------------------------------------------

import copy  # noqa: E402

LOGGING = copy.deepcopy(LOGGING)  # noqa: F405

# Aggressive debug logging for SSE troubleshooting — TEMPORARY
# TODO: revert to INFO after SSE debugging is complete
LOGGING["loggers"]["notifications"]["level"] = "DEBUG"  # type: ignore[index]
LOGGING["loggers"]["notifications.sse"]["level"] = "DEBUG"  # type: ignore[index]

# Only add file handlers if log files are writable.
# Docker volume may not be mounted, or files may be owned by root from
# a previous failed start.  Probe by opening in append mode — same as
# what logging.FileHandler does.
_log_dir_ok = False
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)  # noqa: F405
    for _fname in ("app.log", "sse.log", "errors.log"):
        with open(LOG_DIR / _fname, "a"):  # noqa: F405, SIM115
            pass
    _log_dir_ok = True
except OSError:
    pass

if _log_dir_ok:
    LOGGING["handlers"]["app_file"] = {  # type: ignore[index]
        "class": "logging.handlers.TimedRotatingFileHandler",
        "filename": str(LOG_DIR / "app.log"),  # noqa: F405
        "when": "midnight",
        "backupCount": 14,
        "formatter": "verbose",
        "encoding": "utf-8",
    }

    LOGGING["handlers"]["sse_file"] = {  # type: ignore[index]
        "class": "logging.handlers.TimedRotatingFileHandler",
        "filename": str(LOG_DIR / "sse.log"),  # noqa: F405
        "when": "midnight",
        "backupCount": 14,
        "formatter": "sse",
        "encoding": "utf-8",
    }

    LOGGING["handlers"]["error_file"] = {  # type: ignore[index]
        "class": "logging.handlers.TimedRotatingFileHandler",
        "filename": str(LOG_DIR / "errors.log"),  # noqa: F405
        "when": "midnight",
        "backupCount": 14,
        "formatter": "verbose",
        "level": "WARNING",
        "encoding": "utf-8",
    }

    LOGGING["handlers"]["mail_admins"] = {  # type: ignore[index]
        "class": "django.utils.log.AdminEmailHandler",
        "level": "ERROR",
        "include_html": False,
    }

    LOGGING["loggers"]["notifications"]["handlers"] = ["console", "app_file"]  # type: ignore[index]
    LOGGING["loggers"]["notifications.sse"]["handlers"] = ["console", "sse_file"]  # type: ignore[index]
    LOGGING["loggers"]["db.monitor"]["handlers"] = ["console", "app_file"]  # type: ignore[index]
    LOGGING["loggers"]["django.request"]["handlers"] = [  # type: ignore[index]
        "console",
        "error_file",
        "mail_admins",
    ]
    LOGGING["root"]["handlers"] = ["console", "error_file"]  # type: ignore[index]

# ---------------------------------------------------------------------------
# Email — production SMTP for admin error alerts
# ---------------------------------------------------------------------------

ADMINS: list[tuple[str, str]] = [
    ("Festival Manager", config("ADMIN_EMAIL", default="admin@fest.ua")),
]
SERVER_EMAIL = config("SERVER_EMAIL", default="noreply@fest.ua")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
