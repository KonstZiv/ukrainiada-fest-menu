# ---------------------------------------------------------------------------
# urls.py — Головний конфігуратор URL-маршрутів проєкту
#
# Тут підключаються маршрути всіх застосунків та сервісних інструментів.
# Django Debug Toolbar підключається ТІЛЬКИ при DEBUG=True.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/http/urls/
# ---------------------------------------------------------------------------

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("menu/", include("menu.urls"), name="menu"),
    path("user/", include("user.urls"), name="user"),
    path("accounts/", include("django.contrib.auth.urls")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
]

# ---------------------------------------------------------------------------
# Django Debug Toolbar — маршрут /__debug__/ для панелі інструментів.
# Підключаємо тільки при DEBUG=True, щоб не потрапило у production.
#
# Документація:
#   https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#urls
# ---------------------------------------------------------------------------
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
        *urlpatterns,
    ]
