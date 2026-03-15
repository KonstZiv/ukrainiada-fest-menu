"""SSE endpoint for real-time updates per user role."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse

from django_eventstream import send_event  # noqa: F401 — ensure app is loaded
from django_eventstream.eventresponse import EventResponse

from notifications.channels import channels_for_user


@login_required
def user_events(request: HttpRequest) -> HttpResponse:
    """SSE stream for the current user's channels.

    Returns 403 if user has no channels (e.g. visitor role).
    """
    channels = channels_for_user(request.user)  # type: ignore[arg-type]
    if not channels:
        return HttpResponse("No channels for your role", status=403)

    return EventResponse(request, channels)  # type: ignore[no-any-return, return-value]
