"""Template filters and tags for orders app."""

from __future__ import annotations

import logging
from typing import Any

from django import template
from django.utils.translation import gettext

from orders.event_log import resolve_params

logger = logging.getLogger(__name__)

register = template.Library()


@register.filter
def get_item(dictionary: dict[Any, Any], key: Any) -> Any:
    """Lookup a dictionary value by key in templates.

    Usage: {{ dish_stats|get_item:item.dish.id }}
    """
    return dictionary.get(key)


@register.filter
def render_event(event: Any) -> str:
    """Render OrderEvent message in current language.

    If event has message_key + params, translates via gettext.
    Otherwise falls back to stored message (legacy events).

    Usage: {{ event|render_event }}
    """
    key = getattr(event, "message_key", "")
    if not key:
        return str(getattr(event, "message", ""))

    params = getattr(event, "params", {}) or {}
    try:
        resolved = resolve_params(params)
        return gettext(key) % resolved
    except KeyError, TypeError, ValueError:
        logger.warning(
            "Failed to render event %s: key=%r params=%r", event.pk, key, params
        )
        return str(getattr(event, "message", key))
