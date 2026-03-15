"""Celery application configuration for the festival menu project."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")

app = Celery("festival_menu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self: Celery) -> None:  # type: ignore[type-arg]
    """Test task to verify Celery is working."""
    print(f"Request: {self.request!r}")
