"""Celery application configuration for the festival menu project."""

import os

from celery import Celery, Task
from celery.signals import task_postrun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_settings.settings.dev")

app = Celery("festival_menu")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@task_postrun.connect
def close_db_connections_after_task(**kwargs: object) -> None:
    """Close stale DB connections after every task execution.

    Celery prefork workers are long-lived processes that don't go through
    Django's request/response cycle, so CONN_MAX_AGE cleanup never triggers.
    This signal ensures connections are returned to PostgreSQL promptly.
    """
    from django.db import close_old_connections

    close_old_connections()


@app.task(bind=True, ignore_result=True)
def debug_task(self: Task) -> None:
    """Test task to verify Celery is working."""
    print(f"Request: {self.request!r}")


@app.task(name="core_settings.monitor_db_connections", ignore_result=True)
def monitor_db_connections() -> dict[str, object]:
    """Log DB connection count, warn/critical if thresholds exceeded.

    Runs every 2 minutes via Beat.  Acts as an early-warning system so
    connection exhaustion never surprises us during the festival.
    """
    import logging

    from django.conf import settings
    from django.db import connection

    logger = logging.getLogger("db.monitor")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT state, count(*) FROM pg_stat_activity"
            " WHERE datname = current_database() GROUP BY state"
        )
        breakdown = {state or "no_state": cnt for state, cnt in cursor.fetchall()}

    total = sum(breakdown.values())
    warn = getattr(settings, "DB_CONNECTIONS_WARN", 60)
    critical = getattr(settings, "DB_CONNECTIONS_CRITICAL", 80)

    if total >= critical:
        logger.critical("DB connections CRITICAL: %d %s", total, breakdown)
    elif total >= warn:
        logger.warning("DB connections WARNING: %d %s", total, breakdown)
    else:
        logger.info("DB connections OK: %d %s", total, breakdown)

    return {"total": total, "breakdown": breakdown}
