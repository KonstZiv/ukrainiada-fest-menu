"""Context processors for news app."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

_EDITOR_ROLES = {"editor", "manager"}


def news_context(request: HttpRequest) -> dict[str, Any]:
    """Provide pending comment count for editor navbar badge."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    if getattr(user, "role", None) not in _EDITOR_ROLES:
        return {}

    from news.models import ArticleComment

    pending = ArticleComment.objects.filter(
        status=ArticleComment.Status.PENDING,
    ).count()
    return {"pending_comments_count": pending}
