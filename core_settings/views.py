"""Core views — offline page, health check, DB connection monitoring, SW."""

import logging
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def landing_page(request: HttpRequest) -> HttpResponse:
    """Central landing page for the Ukrainian Cultural Center platform."""
    return render(request, "landing.html", {"show_search": False})


def offline_page(request: HttpRequest) -> HttpResponse:
    """Offline fallback page served from Service Worker cache."""
    return render(request, "offline.html")


def service_worker(request: HttpRequest) -> HttpResponse:
    """Serve SW from root so its scope covers the entire site."""
    sw_path = Path(settings.BASE_DIR) / "staticfiles" / "js" / "sw.js"
    return HttpResponse(
        sw_path.read_text(),
        content_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


def _get_db_connection_count() -> int | None:
    """Query pg_stat_activity for active backend count."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity"
                " WHERE datname = current_database()"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
    except Exception:
        return None


def health_check(request: HttpRequest) -> JsonResponse:
    """Health check with DB connection monitoring.

    Returns connection count and warns when approaching PostgreSQL limits.
    Query param ``?detail=1`` adds per-state breakdown.
    """
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    data: dict[str, object] = {"status": "ok" if db_ok else "unhealthy", "db": db_ok}
    status = 200

    if db_ok:
        conn_count = _get_db_connection_count()
        data["db_connections"] = conn_count

        warn = getattr(settings, "DB_CONNECTIONS_WARN", 60)
        critical = getattr(settings, "DB_CONNECTIONS_CRITICAL", 80)

        if conn_count is not None:
            if conn_count >= critical:
                data["db_connections_status"] = "CRITICAL"
                status = 503
                logger.critical("DB connections CRITICAL: %d", conn_count)
            elif conn_count >= warn:
                data["db_connections_status"] = "WARNING"
                logger.warning("DB connections WARNING: %d", conn_count)
            else:
                data["db_connections_status"] = "ok"

        if request.GET.get("detail"):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT state, count(*) FROM pg_stat_activity"
                        " WHERE datname = current_database()"
                        " GROUP BY state"
                    )
                    data["db_connections_detail"] = {
                        state or "no_state": cnt for state, cnt in cursor.fetchall()
                    }
            except Exception:
                pass

    return JsonResponse(data, status=status)
