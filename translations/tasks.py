"""Celery tasks for LLM auto-translation with two-role pipeline."""

from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType

from translations.constants import FIELDS_MAP, TARGET_LANGUAGES
from translations.models import TranslationApproval

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="translations.translate_object",
    max_retries=3,
    default_retry_delay=30,
)
def translate_object(self: object, content_type_id: int, object_id: int) -> None:
    """Auto-translate an object's UK fields using two-role pipeline.

    Pipeline per language:
      1. Translator (gemini-flash) — initial translation
      2. Reviewer (gemini-pro) — scores on 6 criteria
      3. If average < 8.5 → Translator corrects with feedback (max 2 loops)
    """
    ct = ContentType.objects.get(id=content_type_id)
    model = ct.model_class()
    if model is None:
        logger.error("ContentType %s has no model class", ct)
        return

    try:
        obj = model.objects.get(pk=object_id)  # type: ignore[attr-defined]
    except model.DoesNotExist:  # type: ignore[attr-defined]
        logger.warning(
            "Object %s#%s no longer exists — skipping translation", ct.model, object_id
        )
        return

    fields = FIELDS_MAP.get(model, {})
    if not fields:
        logger.warning("No translatable fields for %s", ct.model)
        return

    # Collect source UK text.
    source: dict[str, str] = {}
    for f in fields:
        val = getattr(obj, f"{f}_uk", None) or ""
        if val:
            source[f] = val

    if not source:
        logger.info("All UK fields empty for %s#%s — skipping", ct.model, object_id)
        return

    from django.conf import settings as django_settings

    if not getattr(django_settings, "GEMINI_API_KEY", ""):
        logger.info(
            "GEMINI_API_KEY not configured — skipping translation for %s#%s",
            ct.model,
            object_id,
        )
        return

    # --- Two-role pipeline ---
    from translations.gemini import translate_and_review

    try:
        results = translate_and_review(
            source,
            TARGET_LANGUAGES,
            field_kinds=fields,
        )
    except Exception as exc:
        logger.error(
            "Translation pipeline failed for %s#%s: %s", ct.model, object_id, exc
        )
        for lang in TARGET_LANGUAGES:
            TranslationApproval.objects.update_or_create(
                content_type=ct,
                object_id=object_id,
                language=lang,
                defaults={"status": TranslationApproval.Status.FAILED},
            )
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]

    # Save translations and review scores.
    update_fields: list[str] = []
    for lang, result in results.items():
        if lang not in TARGET_LANGUAGES:
            continue

        # Save translated field values to model.
        for field_name, value in result.fields.items():
            if field_name not in fields:
                continue
            attr = f"{field_name}_{lang}"
            if hasattr(obj, attr):
                setattr(obj, attr, value)
                update_fields.append(attr)

        # Save review scores to TranslationApproval.
        scores = result.scores
        TranslationApproval.objects.update_or_create(
            content_type=ct,
            object_id=object_id,
            language=lang,
            defaults={
                "status": TranslationApproval.Status.PENDING,
                "approved_by": None,
                "approved_at": None,
                "llm_accuracy": scores.accuracy,
                "llm_emotion": scores.emotion,
                "llm_quality": scores.quality,
                "llm_style": scores.style,
                "llm_grammar": scores.grammar,
                "llm_ethics": scores.ethics,
                "llm_average": scores.average,
                "llm_review_comment": scores.comment,
                "llm_review_iterations": result.iterations,
            },
        )

    if update_fields:
        obj.save(update_fields=update_fields)
        logger.info(
            "Saved translations for %s#%s: %d fields",
            ct.model,
            object_id,
            len(update_fields),
        )

    # Log summary.
    for lang, result in results.items():
        avg = result.scores.average
        status = "PASS" if result.scores.passed else "BELOW THRESHOLD"
        logger.info(
            "%s#%s [%s] avg=%.1f (%s, %d iterations)",
            ct.model,
            object_id,
            lang,
            avg,
            status,
            result.iterations,
        )
