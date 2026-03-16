"""Core views — offline page, health check, etc."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def offline_page(request: HttpRequest) -> HttpResponse:
    """Offline fallback page served from Service Worker cache."""
    return render(request, "offline.html")
