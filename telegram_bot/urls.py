"""URL patterns for Telegram bot webhook."""

from django.urls import path

from telegram_bot import views

app_name = "telegram_bot"

urlpatterns = [
    path("<str:secret>/", views.telegram_webhook, name="webhook"),
]
