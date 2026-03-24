"""Context processor for translation review badge in navbar."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

_REVIEW_ROLES = {"manager", "kitchen_supervisor", "senior_waiter"}


def translation_context(request: HttpRequest) -> dict[str, Any]:
    """Provide pending translation count for staff navbar badge."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    if getattr(user, "role", None) not in _REVIEW_ROLES:
        return {}

    from translations.models import TranslationApproval

    pending = (
        TranslationApproval.objects.filter(
            status__in=[
                TranslationApproval.Status.PENDING,
                TranslationApproval.Status.FAILED,
            ],
        )
        .values("content_type", "object_id")
        .distinct()
        .count()
    )
    return {"pending_translations_count": pending}
