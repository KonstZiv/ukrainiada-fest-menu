"""Business logic for translation approval workflow."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from translations.constants import FIELDS_MAP, TARGET_LANGUAGES
from translations.models import TranslationApproval

if __import__("typing").TYPE_CHECKING:
    from user.models import User


def approve_translation(approval: TranslationApproval, user: User) -> None:
    """Mark a single translation as approved."""
    approval.status = TranslationApproval.Status.APPROVED
    approval.approved_by = user
    approval.approved_at = timezone.now()
    approval.save(update_fields=["status", "approved_by", "approved_at"])


def approve_all_for_object(
    content_type: ContentType, object_id: int, user: User
) -> int:
    """Approve all pending translations for one object. Returns count."""
    now = timezone.now()
    return TranslationApproval.objects.filter(
        content_type=content_type,
        object_id=object_id,
        status=TranslationApproval.Status.PENDING,
    ).update(
        status=TranslationApproval.Status.APPROVED,
        approved_by=user,
        approved_at=now,
    )


def save_edited_translation(
    approval: TranslationApproval,
    field_values: dict[str, str],
    user: User,
) -> None:
    """Save manually edited translation text and auto-approve."""
    ct = approval.content_type
    model = ct.model_class()
    if model is None:
        return

    obj = model.objects.get(pk=approval.object_id)  # type: ignore[attr-defined]
    fields = FIELDS_MAP.get(model, {})
    update_fields: list[str] = []

    for field, value in field_values.items():
        if field not in fields:
            continue
        attr = f"{field}_{approval.language}"
        if hasattr(obj, attr):
            setattr(obj, attr, value)
            update_fields.append(attr)

    if update_fields:
        obj.save(update_fields=update_fields)

    approve_translation(approval, user)


def retry_translation(approval: TranslationApproval) -> None:
    """Re-trigger Gemini translation for a failed approval."""
    from translations.tasks import translate_object

    translate_object.delay(approval.content_type_id, approval.object_id)


def get_pending_objects() -> list[dict[str, object]]:
    """Return list of objects with pending/failed translations, grouped by model."""
    pending_qs = TranslationApproval.objects.filter(
        status__in=[
            TranslationApproval.Status.PENDING,
            TranslationApproval.Status.FAILED,
        ],
    ).select_related("content_type", "approved_by")

    # Group by (content_type, object_id).
    grouped: dict[tuple[int, int], list[TranslationApproval]] = {}
    for a in pending_qs:
        key = (a.content_type_id, a.object_id)
        grouped.setdefault(key, []).append(a)

    result: list[dict[str, object]] = []
    for (ct_id, obj_id), approvals in grouped.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model = ct.model_class()
        if model is None:
            continue
        try:
            obj = model.objects.get(pk=obj_id)  # type: ignore[attr-defined]
        except model.DoesNotExist:  # type: ignore[attr-defined]
            continue

        fields = FIELDS_MAP.get(model, {})
        source = {f: getattr(obj, f"{f}_uk", "") for f in fields}

        lang_data: dict[str, dict[str, object]] = {}
        for a in approvals:
            translations = {f: getattr(obj, f"{f}_{a.language}", "") for f in fields}
            lang_data[a.language] = {
                "approval": a,
                "translations": translations,
            }

        # Also include approved languages so the reviewer sees full picture.
        approved_qs = TranslationApproval.objects.filter(
            content_type_id=ct_id,
            object_id=obj_id,
            status=TranslationApproval.Status.APPROVED,
        )
        for a in approved_qs:
            if a.language not in lang_data:
                translations = {
                    f: getattr(obj, f"{f}_{a.language}", "") for f in fields
                }
                lang_data[a.language] = {
                    "approval": a,
                    "translations": translations,
                }

        result.append(
            {
                "content_type": ct,
                "object_id": obj_id,
                "object": obj,
                "model_name": ct.model.capitalize(),
                "source": source,
                "fields": fields,
                "languages": {
                    lang: lang_data.get(lang)
                    for lang in TARGET_LANGUAGES
                    if lang in lang_data
                },
            }
        )

    return result
