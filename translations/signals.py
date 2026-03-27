"""Signals to detect UK field changes and trigger auto-translation."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save

from menu.models import Allergen, Category, Dish, Tag
from news.models import Article, NewsTag
from translations.constants import FIELDS_MAP

logger = logging.getLogger(__name__)

_TRANSLATABLE_MODELS = (Category, Dish, Tag, Allergen, Article, NewsTag)


def _uk_field_snapshot(instance: Any) -> dict[str, str | None]:
    """Return a dict of {field_uk: value} for the instance's translatable fields."""
    model = type(instance)
    fields = FIELDS_MAP.get(model, {})
    return {f"{f}_uk": getattr(instance, f"{f}_uk", None) for f in fields}


def store_old_uk_fields(sender: type, instance: Any, **kwargs: Any) -> None:
    """Pre-save: remember current UK field values so post_save can detect changes."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)  # type: ignore[attr-defined]
            instance._old_uk = _uk_field_snapshot(old)  # type: ignore[attr-defined]
        except sender.DoesNotExist:  # type: ignore[attr-defined]
            instance._old_uk = {}  # type: ignore[attr-defined]
    else:
        # New object — will always need translation.
        instance._old_uk = {}  # type: ignore[attr-defined]


def trigger_auto_translate(
    sender: type, instance: Any, created: bool, **kwargs: Any
) -> None:
    """Post-save: if UK fields changed, fire Celery auto-translate task."""
    # When the Celery task saves translations it passes update_fields with
    # only non-UK columns — skip in that case to avoid an infinite loop.
    update_fields: frozenset[str] | None = kwargs.get("update_fields")
    if update_fields is not None and not any(f.endswith("_uk") for f in update_fields):
        return

    # No API key → skip entirely (avoids Redis connection attempt in CI/tests).
    from django.conf import settings

    if not getattr(settings, "GEMINI_API_KEY", ""):
        return

    old: dict[str, str | None] = getattr(instance, "_old_uk", {})
    if not created:
        current = _uk_field_snapshot(instance)
        if current == old:
            return  # UK fields unchanged — nothing to do.

    ct = ContentType.objects.get_for_model(sender)
    logger.info(
        "UK fields changed for %s #%s — scheduling auto-translation",
        ct.model,
        instance.pk,
    )

    from translations.tasks import translate_object

    try:
        translate_object.delay(ct.id, instance.pk)
    except Exception:
        logger.warning("Could not dispatch translate_object (Celery/Redis unavailable)")


# Connect signals for each translatable model.
for _model in _TRANSLATABLE_MODELS:
    pre_save.connect(
        store_old_uk_fields, sender=_model, dispatch_uid=f"trans_pre_{_model.__name__}"
    )
    post_save.connect(
        trigger_auto_translate,
        sender=_model,
        dispatch_uid=f"trans_post_{_model.__name__}",
    )
