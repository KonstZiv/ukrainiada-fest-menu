"""Base Django settings shared across all environments."""

from pathlib import Path

from celery.schedules import crontab
from decouple import Csv

from core_settings.settings.env import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Three levels up: settings/base.py -> settings/ -> core_settings/ -> project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")

ALLOWED_HOSTS: list[str] = config(
    "ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv()
)

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "modeltranslation",  # must be before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # required by django-allauth
    # Project apps
    "user",
    "menu",
    "orders",
    "kitchen",
    "notifications",
    "feedback",
    "translations",
    "news",
    "telegram_bot",
    # Third-party
    "django_celery_beat",
    "django_ckeditor_5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "allauth.socialaccount.providers.instagram",
    "allauth.socialaccount.providers.telegram",
]

SITE_ID = 1

MIDDLEWARE = [
    "core_settings.middleware.SSEAwareGZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "core_settings.urls"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_USER_MODEL = "user.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core_settings.context_processors.brand_context",
                "orders.context_processors.cart_context",
                "orders.context_processors.manager_context",
                "translations.context_processors.translation_context",
                "news.context_processors.news_context",
            ],
        },
    },
]

WSGI_APPLICATION = "core_settings.wsgi.application"

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGES = [
    ("uk", "Українська"),
    ("en", "English"),
    ("cnr", "Crnogorski"),
    ("hr", "Hrvatski"),
    ("bs", "Bosanski"),
    ("it", "Italiano"),
    ("de", "Deutsch"),
]

LANGUAGE_CODE = "uk"

# Montenegrin (cnr) is not in Django's LANG_INFO — register it to avoid
# KeyError in modeltranslation admin and get_language_info().
import django.conf.locale  # noqa: E402

django.conf.locale.LANG_INFO["cnr"] = {
    "bidi": False,
    "code": "cnr",
    "name": "Montenegrin",
    "name_local": "Crnogorski",
}

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [BASE_DIR / "locale"]

# django-modeltranslation — fallback to Ukrainian if translation is missing
MODELTRANSLATION_DEFAULT_LANGUAGE = "uk"
MODELTRANSLATION_FALLBACK_LANGUAGES: tuple[str, ...] = ("uk",)

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "staticfiles"]
STATIC_ROOT = BASE_DIR / "static_collected"

# Hash-based filenames for cache busting (order_tracker.js → order_tracker.abc123.js).
# {% static 'js/file.js' %} resolves to the hashed name via staticfiles.json manifest.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "user:profile"

# ---------------------------------------------------------------------------
# django-allauth — social authentication
# ---------------------------------------------------------------------------

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "user.adapters.CustomSocialAccountAdapter"

SITE_DOMAIN: str = config("SITE_DOMAIN", default="localhost:8000")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "facebook": {
        "SCOPE": ["email"],
        "METHOD": "oauth2",
    },
}

# ---------------------------------------------------------------------------
# CKEditor 5 — rich text editor for news articles
# ---------------------------------------------------------------------------

CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
CKEDITOR_5_UPLOADS_FOLDER = "ckeditor_uploads/"

CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading",
            "|",
            "bold",
            "italic",
            "underline",
            "strikethrough",
            "|",
            "link",
            "bulletedList",
            "numberedList",
            "blockQuote",
            "|",
            "imageUpload",
            "mediaEmbed",
            "|",
            "undo",
            "redo",
        ],
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = BASE_DIR / "logs"

LOGGING: dict[str, object] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "sse": {
            "format": "{asctime} {levelname} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "notifications.sse": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "notifications": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "db.monitor": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# ---------------------------------------------------------------------------
# User avatar settings
# ---------------------------------------------------------------------------

USER_AVATAR_ASPECT_RATIO: float = 0.7
USER_AVATAR_MAX_PIXELS: int = 256

# ---------------------------------------------------------------------------
# Celery — async task queue
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_WORKER_MAX_TASKS_PER_CHILD: int = (
    50  # recycle workers to prevent connection leaks
)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "escalate-kitchen-tickets": {
        "task": "kitchen.escalate_pending_tickets",
        "schedule": 60.0,
    },
    "escalate-unpaid-orders": {
        "task": "orders.escalate_unpaid_orders",
        "schedule": 60.0,
    },
    "escalate-visitor-issues": {
        "task": "orders.escalate_visitor_issues",
        "schedule": 60.0,
    },
    "escalate-unaccepted-orders": {
        "task": "orders.escalate_unaccepted_orders",
        "schedule": 60.0,
    },
    "escalate-unverified-orders": {
        "task": "orders.escalate_unverified_orders",
        "schedule": 60.0,
    },
    "escalate-cooking-tickets": {
        "task": "kitchen.escalate_cooking_tickets",
        "schedule": 60.0,
    },
    "escalate-handoff-tickets": {
        "task": "kitchen.escalate_handoff_tickets",
        "schedule": 60.0,
    },
    "monitor-db-connections": {
        "task": "core_settings.monitor_db_connections",
        "schedule": 120.0,
    },
    "send-daily-digest": {
        "task": "news.send_daily_digest",
        "schedule": crontab(hour=9, minute=0),
    },
    "send-weekly-digest": {
        "task": "news.send_weekly_digest",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
}

# ---------------------------------------------------------------------------
# SSE — Redis pub-sub
#
# Publishing: notifications.redis_publish.publish_sse_event() pushes flat
# JSON to Redis channel "events_channel".
# Subscribing: notifications.views._sse_stream() reads via redis.asyncio.
# ---------------------------------------------------------------------------

SSE_REDIS = {
    "host": config("REDIS_HOST", default="localhost"),
    "port": config("REDIS_PORT", default=6379, cast=int),
    "db": config("REDIS_SSE_DB", default=2, cast=int),
}

# ---------------------------------------------------------------------------
# Festival business constants (minutes)
# ---------------------------------------------------------------------------

HANDOFF_TOKEN_TTL: int = config("HANDOFF_TOKEN_TTL", default=120, cast=int)  # seconds
KITCHEN_TIMEOUT: int = config("KITCHEN_TIMEOUT", default=10, cast=int)
KITCHEN_WARN_MINUTES: int = config("KITCHEN_WARN_MINUTES", default=5, cast=int)
MANAGER_TIMEOUT: int = config("MANAGER_TIMEOUT", default=10, cast=int)
PAY_TIMEOUT: int = config("PAY_TIMEOUT", default=15, cast=int)
SPEED_INTERVAL_KITCHEN: int = config("SPEED_INTERVAL_KITCHEN", default=15, cast=int)
ESCALATION_COOLDOWN: int = config("ESCALATION_COOLDOWN", default=5, cast=int)  # minutes
ESCALATION_AUTO_LEVEL: int = config(
    "ESCALATION_AUTO_LEVEL", default=5, cast=int
)  # minutes
ESCALATION_MIN_WAIT: int = config(
    "ESCALATION_MIN_WAIT", default=10, cast=int
)  # minutes
DISH_PICKUP_WARN: int = config(
    "DISH_PICKUP_WARN", default=5, cast=int
)  # minutes — dish ready, warn waiter
DISH_PICKUP_CRITICAL: int = config(
    "DISH_PICKUP_CRITICAL", default=10, cast=int
)  # minutes — dish ready, escalate to senior

# Step escalation ownership timeouts (minutes)
ACCEPT_TIMEOUT: int = config("ACCEPT_TIMEOUT", default=5, cast=int)
VERIFY_TIMEOUT: int = config("VERIFY_TIMEOUT", default=5, cast=int)
COOKING_TIMEOUT: int = config("COOKING_TIMEOUT", default=15, cast=int)
HANDOFF_TIMEOUT: int = config("HANDOFF_TIMEOUT", default=10, cast=int)
SENIOR_RESPONSE_TIMEOUT: int = config("SENIOR_RESPONSE_TIMEOUT", default=10, cast=int)

# ---------------------------------------------------------------------------
# LLM auto-translation (Google Gemini)
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str = config("GEMINI_API_KEY", default="")

# ---------------------------------------------------------------------------
# Cache — Redis (shared across uvicorn workers)
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    },
}

# ---------------------------------------------------------------------------
# Telegram Bot (aiogram3 webhook)
# ---------------------------------------------------------------------------

TG_TOKEN: str = config("TG_TOKEN", default="")
TG_WEBHOOK_SECRET: str = config("TG_WEBHOOK_SECRET", default="")
TG_WEBHOOK_BASE_URL: str = config("TG_WEBHOOK_BASE_URL", default="")
TG_BOT_URL: str = config("TG_BOT_URL", default="")  # https://t.me/BotName
