"""Template filters for orders app."""

from __future__ import annotations

from typing import Any

from django import template

register = template.Library()


@register.filter
def get_item(dictionary: dict[Any, Any], key: Any) -> Any:
    """Lookup a dictionary value by key in templates.

    Usage: {{ dish_stats|get_item:item.dish.id }}
    """
    return dictionary.get(key)
