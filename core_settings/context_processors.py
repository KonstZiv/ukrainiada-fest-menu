"""Platform-level context processors."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

# Path prefix → subtitle mapping.
_SUBTITLE_MAP: list[tuple[str, str]] = [
    ("/menu/", "Ukrainiada"),
    ("/order/", "Ukrainiada"),
    ("/waiter/", "Ukrainiada"),
    ("/kitchen/", "Ukrainiada"),
    ("/manager/", "Ukrainiada"),
    ("/news/", "Новини"),
]


def brand_context(request: HttpRequest) -> dict[str, Any]:
    """Provide brand_subtitle for navbar based on current URL path."""
    path = request.path
    for prefix, subtitle in _SUBTITLE_MAP:
        if path.startswith(prefix):
            return {"brand_subtitle": subtitle}
    return {"brand_subtitle": ""}
