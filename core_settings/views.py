"""Core views — offline page, health check, etc."""

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def offline_page(request: HttpRequest) -> HttpResponse:
    """Offline fallback page served from Service Worker cache."""
    return render(request, "offline.html")


def health_check(request: HttpRequest) -> JsonResponse:
    """Lightweight health check for Docker/load balancer probes."""
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse(
        {"status": "ok" if db_ok else "unhealthy", "db": db_ok}, status=status
    )
