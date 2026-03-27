"""ASGI config for core_settings project.

SSE is handled via custom async views in notifications.views using
Redis pub-sub for cross-worker event delivery.
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.prod")

application = get_asgi_application()

# Serve static files in development (uvicorn doesn't do this by default).
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    application = ASGIStaticFilesHandler(application)
