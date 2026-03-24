"""Translations app configuration."""

from django.apps import AppConfig


class TranslationsConfig(AppConfig):
    """Auto-translate menu content via LLM with staff approval workflow."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "translations"

    def ready(self) -> None:
        from translations.constants import populate_fields_map

        populate_fields_map()

        from translations import signals  # noqa: F401
