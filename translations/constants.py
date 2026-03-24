"""Constants for the translations app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db import models

# Languages to auto-translate into (all except the source language 'uk').
TARGET_LANGUAGES: list[str] = ["en", "cnr", "hr", "bs", "it", "de"]

# Mapping: model class -> list of translatable field base names.
# Populated at app ready() from modeltranslation registry.
FIELDS_MAP: dict[type[models.Model], list[str]] = {}


def populate_fields_map() -> None:
    """Build FIELDS_MAP from modeltranslation registry (called once at ready)."""
    from modeltranslation.translator import translator

    for model in translator.get_registered_models(abstract=False):
        opts = translator.get_options_for_model(model)
        FIELDS_MAP[model] = list(opts.fields)  # type: ignore[attr-defined]
