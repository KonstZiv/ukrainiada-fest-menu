"""ASGI config for core_settings project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.prod")

application = get_asgi_application()
