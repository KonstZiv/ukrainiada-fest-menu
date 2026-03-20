"""ASGI config for core_settings project.

django-eventstream 5.x works through standard Django URL patterns
(no channels routing needed).  Cross-worker event delivery is handled
by EVENTSTREAM_STORAGE_CLASS=RedisStorage in settings.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.prod")

application = get_asgi_application()
