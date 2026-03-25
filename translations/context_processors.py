"""Context processor for translation review badge in navbar."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

_REVIEW_ROLES = {
    "manager",
    "kitchen_supervisor",
    "senior_waiter",
    "corrector",
    "editor",
}


def translation_context(request: HttpRequest) -> dict[str, Any]:
    """Provide pending translation count for staff navbar badge."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    role = getattr(user, "role", None)
    if role not in _REVIEW_ROLES:
        return {}

    from translations.models import TranslationApproval

    qs = TranslationApproval.objects.filter(
        status__in=[
            TranslationApproval.Status.PENDING,
            TranslationApproval.Status.FAILED,
        ],
    )

    # Correctors see count only for their assigned languages.
    if role == "corrector":
        allowed = getattr(user, "corrector_languages", None) or []
        if allowed:
            qs = qs.filter(language__in=allowed)
        else:
            return {}

    pending = qs.values("content_type", "object_id").distinct().count()
    return {"pending_translations_count": pending}
