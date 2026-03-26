"""CI settings — dev settings with LocMemCache (no Redis in CI)."""

from .dev import *  # noqa: F403

# Override Redis cache with in-memory — CI has no Redis service.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}
