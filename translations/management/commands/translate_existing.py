"""Translate existing menu objects via Gemini.

Usage:
    python manage.py translate_existing                    # all models, all languages
    python manage.py translate_existing --model category   # one model type
    python manage.py translate_existing --lang cnr         # one language only
    python manage.py translate_existing --force            # re-translate filled fields
    python manage.py translate_existing --dry-run
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from translations.constants import FIELDS_MAP, TARGET_LANGUAGES
from translations.gemini import reset_stats, translate_with_gemini, usage_stats
from translations.models import TranslationApproval

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Translate all existing menu objects that have empty translation fields."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--model",
            type=str,
            help="Only translate this model (category, dish, tag, allergen).",
        )
        parser.add_argument(
            "--lang",
            type=str,
            help="Only translate to this language (en, cnr, hr, bs, it, de).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be translated without calling the API.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-translate even if fields are already filled.",
        )

    def handle(self, **options: Any) -> None:
        if not settings.GEMINI_API_KEY:
            self.stderr.write(self.style.ERROR("GEMINI_API_KEY not configured."))
            return

        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        model_filter: str | None = options.get("model")
        lang_filter: str | None = options.get("lang")

        # Determine target languages.
        if lang_filter:
            if lang_filter not in TARGET_LANGUAGES:
                self.stderr.write(
                    self.style.ERROR(
                        f"Language '{lang_filter}' not in TARGET_LANGUAGES: {TARGET_LANGUAGES}"
                    )
                )
                return
            languages = [lang_filter]
        else:
            languages = TARGET_LANGUAGES

        reset_stats()

        models_to_process = list(FIELDS_MAP.items())
        if model_filter:
            models_to_process = [
                (m, f)
                for m, f in models_to_process
                if m.__name__.lower() == model_filter.lower()
            ]
            if not models_to_process:
                self.stderr.write(
                    self.style.ERROR(f"Model '{model_filter}' not found in FIELDS_MAP.")
                )
                return

        self.stdout.write(f"Languages: {', '.join(languages)}")

        total_translated = 0
        total_skipped = 0

        for model, fields in models_to_process:
            ct = ContentType.objects.get_for_model(model)
            objects = model.objects.all()  # type: ignore[attr-defined]
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\n{model.__name__} ({objects.count()} objects)"
                )
            )

            for obj in objects:
                # Check if translation is needed.
                source: dict[str, str] = {}
                needs_translation = force
                for f in fields:
                    uk_val = getattr(obj, f"{f}_uk", "") or ""
                    if uk_val:
                        source[f] = uk_val
                    # Check if any target language is empty.
                    if not force:
                        for lang in languages:
                            if not (getattr(obj, f"{f}_{lang}", "") or ""):
                                needs_translation = True
                                break

                if not source:
                    total_skipped += 1
                    continue

                if not needs_translation:
                    self.stdout.write(f"  {obj} — already translated, skipping")
                    total_skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  {obj} — would translate: {list(source.keys())}"
                    )
                    total_translated += 1
                    continue

                self.stdout.write(f"  {obj} — translating...", ending="")
                try:
                    translations = translate_with_gemini(
                        source, languages, field_kinds=fields
                    )
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f" FAILED: {exc}"))
                    for lang in languages:
                        TranslationApproval.objects.update_or_create(
                            content_type=ct,
                            object_id=obj.pk,
                            language=lang,
                            defaults={"status": TranslationApproval.Status.FAILED},
                        )
                    continue

                # Save translations.
                update_fields: list[str] = []
                for lang, field_data in translations.items():
                    if lang not in languages:
                        continue
                    for field, value in field_data.items():
                        if field not in fields:
                            continue
                        attr = f"{field}_{lang}"
                        if hasattr(obj, attr):
                            setattr(obj, attr, value)
                            update_fields.append(attr)

                if update_fields:
                    obj.save(update_fields=update_fields)

                # Create approvals.
                for lang in languages:
                    TranslationApproval.objects.update_or_create(
                        content_type=ct,
                        object_id=obj.pk,
                        language=lang,
                        defaults={
                            "status": TranslationApproval.Status.PENDING,
                            "approved_by": None,
                            "approved_at": None,
                        },
                    )

                self.stdout.write(
                    self.style.SUCCESS(f" OK ({len(update_fields)} fields)")
                )
                total_translated += 1
                time.sleep(2)  # rate limit

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Translated: {total_translated}, skipped: {total_skipped}"
            )
        )
        self.stdout.write(self.style.SUCCESS(f"LLM usage:  {usage_stats.summary()}"))
