# ---------------------------------------------------------------------------
# urls.py — Головний конфігуратор URL-маршрутів проєкту
#
# Тут підключаються маршрути всіх застосунків та сервісних інструментів.
# Django Debug Toolbar підключається ТІЛЬКИ при DEBUG=True.
#
# Документація:
#   https://docs.djangoproject.com/en/stable/topics/http/urls/
# ---------------------------------------------------------------------------

import django_eventstream
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("menu/", include("menu.urls")),
    path("user/", include("user.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("order/", include("orders.urls")),
    path(
        "events/<str:channel>/",
        include(django_eventstream.urls),
        {"format-error": "json"},
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    # django-stubs types static() as list[URLPattern], but urlpatterns is list[URLResolver]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # type: ignore[arg-type]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]
