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
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog

from core_settings.views import health_check, offline_page

urlpatterns = [
    path("", RedirectView.as_view(url="/menu/", permanent=False)),
    path("health/", health_check, name="health_check"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("offline/", offline_page, name="offline"),
    path("admin/", admin.site.urls),
    path("menu/", include("menu.urls")),
    path("user/", include("user.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("order/", include("orders.urls")),
    path("waiter/", include("orders.waiter_urls")),
    path("kitchen/", include("kitchen.urls")),
    path("manager/", include("orders.manager_urls")),
    path("feedback/", include("feedback.urls")),
    path("events/", include("notifications.urls")),
    path("translations/", include("translations.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    # django-stubs types static() as list[URLPattern], but urlpatterns is list[URLResolver]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # type: ignore[arg-type]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  # type: ignore[arg-type]
