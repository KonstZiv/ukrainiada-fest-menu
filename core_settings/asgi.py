"""ASGI config — routes HTTP through django-eventstream for SSE support."""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import django_eventstream.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": URLRouter(
            [
                *django_eventstream.routing.urlpatterns,
                django_asgi_app,  # type: ignore[list-item]
            ]
        ),
    }
)
