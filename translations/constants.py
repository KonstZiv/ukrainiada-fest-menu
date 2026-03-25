"""Constants for the translations app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from django.db import models

# Languages to auto-translate into (all except the source language 'uk').
TARGET_LANGUAGES: list[str] = ["en", "cnr", "hr", "bs", "it", "de"]

# Content type for each translatable field.
ContentKind = Literal["plain", "html"]

# Mapping: model class -> {field_name: content_kind}.
# Populated at app ready() from modeltranslation registry.
# Default kind is "plain"; override in FIELD_CONTENT_KINDS for HTML fields.
FIELDS_MAP: dict[type[models.Model], dict[str, ContentKind]] = {}

# Explicit overrides: (app_label.ModelName, field_name) -> content kind.
# Add entries here for fields that contain HTML (e.g. CKEditor content).
_FIELD_KIND_OVERRIDES: dict[tuple[str, str], ContentKind] = {
    ("news.Article", "content"): "html",
}


def populate_fields_map() -> None:
    """Build FIELDS_MAP from modeltranslation registry (called once at ready)."""
    from modeltranslation.translator import translator

    for model in translator.get_registered_models(abstract=False):
        opts = translator.get_options_for_model(model)
        model_label = f"{model._meta.app_label}.{model.__name__}"
        fields: dict[str, ContentKind] = {}
        for field_name in opts.fields:  # type: ignore[attr-defined]
            kind = _FIELD_KIND_OVERRIDES.get((model_label, field_name), "plain")
            fields[field_name] = kind
        FIELDS_MAP[model] = fields
