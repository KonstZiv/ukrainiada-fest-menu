"""Base Django settings shared across all environments."""

from pathlib import Path

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
    # Project apps
    "user",
    "menu",
    "orders",
    "kitchen",
    "notifications",
    "feedback",
    # Third-party
    "django_celery_beat",
    "channels",
    "django_eventstream",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core_settings.urls"

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
                "orders.context_processors.cart_context",
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

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "user:profile"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

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
}

# ---------------------------------------------------------------------------
# Channels (SSE via django-eventstream)
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL", default="redis://localhost:6379/1")],
        },
    },
}

EVENTSTREAM_KEEPALIVE = 15  # seconds — less than typical 30s proxy timeout

# ---------------------------------------------------------------------------
# Festival business constants (minutes)
# ---------------------------------------------------------------------------

HANDOFF_TOKEN_TTL: int = config("HANDOFF_TOKEN_TTL", default=120, cast=int)  # seconds
KITCHEN_TIMEOUT: int = config("KITCHEN_TIMEOUT", default=5, cast=int)
MANAGER_TIMEOUT: int = config("MANAGER_TIMEOUT", default=5, cast=int)
PAY_TIMEOUT: int = config("PAY_TIMEOUT", default=10, cast=int)
SPEED_INTERVAL_KITCHEN: int = config("SPEED_INTERVAL_KITCHEN", default=15, cast=int)
ESCALATION_COOLDOWN: int = config("ESCALATION_COOLDOWN", default=5, cast=int)  # minutes
ESCALATION_AUTO_LEVEL: int = config(
    "ESCALATION_AUTO_LEVEL", default=3, cast=int
)  # minutes
ESCALATION_MIN_WAIT: int = config("ESCALATION_MIN_WAIT", default=5, cast=int)  # minutes
DISH_PICKUP_WARN: int = config(
    "DISH_PICKUP_WARN", default=3, cast=int
)  # minutes — dish ready, warn waiter
DISH_PICKUP_CRITICAL: int = config(
    "DISH_PICKUP_CRITICAL", default=6, cast=int
)  # minutes — dish ready, escalate to senior
