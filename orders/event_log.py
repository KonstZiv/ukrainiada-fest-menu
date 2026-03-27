"""Helper for recording OrderEvent entries at every lifecycle point."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.utils import translation
from django.utils.translation import gettext

from notifications.events import push_order_log_event
from orders.models import Order, OrderEvent

if TYPE_CHECKING:
    from user.models import User

logger = logging.getLogger(__name__)


def _build_staff_label(params: dict[str, Any]) -> str:
    """Resolve staff_label from params for Ukrainian fallback message."""
    display_title = params.get("staff_display_title", "")
    if not display_title:
        # Translate role to Ukrainian for fallback.
        from user.models import User as UserModel

        role_val = params.get("staff_role", "")
        role_choices = dict(UserModel.Role.choices)
        display_title = str(role_choices.get(role_val, role_val))
    name = params.get("staff_name", "")
    return f"{display_title} {name}".strip()


def resolve_params(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve dynamic params for message interpolation.

    Builds staff_label from role + name + display_title.
    Resolves dish_id to dish.title in current active language.
    """
    result = dict(params)

    # Build staff_label if staff_role is present.
    if "staff_role" in result:
        display_title = result.pop("staff_display_title", "")
        if not display_title:
            from user.models import User as UserModel

            role_val = result.get("staff_role", "")
            role_choices = dict(UserModel.Role.choices)
            display_title = str(role_choices.get(role_val, role_val))
        name = result.pop("staff_name", "")
        result.pop("staff_role", None)
        result["staff_label"] = f"{display_title} {name}".strip()

    # Resolve dish_id to translated title.
    if "dish_id" in result:
        from menu.models import Dish

        dish_id = result.pop("dish_id")
        try:
            result["dish_title"] = Dish.objects.get(pk=dish_id).title
        except Dish.DoesNotExist:
            pass  # keep dish_title from params if present

    # Resolve items_data to items_summary in active language.
    if "items_data" in result:
        from menu.models import Dish

        items = result.pop("items_data")
        dish_ids = [item["dish_id"] for item in items]
        dishes = {str(d.pk): d.title for d in Dish.objects.filter(pk__in=dish_ids)}
        result["items_summary"] = ", ".join(
            f"{dishes.get(item['dish_id'], '?')} x{item['qty']}" for item in items
        )

    return result


def log_event(
    order: Order,
    message_key: str,
    params: dict[str, Any] | None = None,
    actor_label: str = "",
    *,
    actor: User | None = None,
    is_auto_skip: bool = False,
    msg_class: str = "",
) -> OrderEvent:
    """Create an OrderEvent with i18n support and push via SSE.

    Stores message_key + params for render-time translation.
    Also generates a Ukrainian fallback in the `message` field.
    """
    raw_params = params or {}

    # Generate Ukrainian fallback message.
    original_lang = translation.get_language()
    try:
        translation.activate("uk")
        resolved = resolve_params(raw_params)
        try:
            fallback_message = gettext(message_key) % resolved
        except KeyError, TypeError, ValueError:
            logger.warning(
                "Failed to format message_key=%r params=%r", message_key, resolved
            )
            fallback_message = message_key
    finally:
        if original_lang:
            translation.activate(original_lang)

    event = OrderEvent.objects.create(
        order=order,
        message=fallback_message,
        message_key=message_key,
        params=raw_params,
        msg_class=msg_class,
        actor=actor,
        actor_label=actor_label,
        is_auto_skip=is_auto_skip,
    )

    push_order_log_event(
        order_id=order.id,
        log_line=event.log_line,
        message_key=message_key,
        params=raw_params,
        msg_class=msg_class,
        timestamp=event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return event
