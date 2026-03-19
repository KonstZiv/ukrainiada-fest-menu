"""ASGI config — routes HTTP through django-eventstream for SSE support."""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import re_path

import django_eventstream.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.prod")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                *django_eventstream.routing.urlpatterns,
                re_path(r"^", django_asgi_app),  # type: ignore[arg-type]
            ]
        ),
    }
)
