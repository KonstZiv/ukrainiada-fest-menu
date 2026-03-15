"""Centralized type definitions for the project."""

from __future__ import annotations

from django.http import HttpRequest

from user.models import User


class AuthenticatedHttpRequest(HttpRequest):
    """HttpRequest with user typed as our custom User model.

    Use in views that require authentication (after login_required
    or role_required) to avoid type: ignore for request.user.
    """

    # django-stubs types user as User | AnonymousUser; we narrow to User
    user: User  # type: ignore[assignment]
