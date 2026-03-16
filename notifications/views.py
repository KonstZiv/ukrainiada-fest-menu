"""SSE endpoints for real-time updates per user role and visitor order."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

import django_eventstream
from django_eventstream.views import events as eventstream_events

from notifications.channels import channels_for_user, visitor_order_channel
from orders.models import Order
from orders.services import can_access_order


@login_required
def user_events(request: HttpRequest) -> HttpResponse:
    """SSE stream for the current user's channels.

    Returns 403 if user has no channels (e.g. visitor role).
    """
    channels = channels_for_user(request.user)  # type: ignore[arg-type]
    if not channels:
        return HttpResponse("No channels for your role", status=403)

    return eventstream_events(request, channels=channels)  # type: ignore[no-any-return]


def visitor_order_events(request: HttpRequest, order_id: int) -> HttpResponse:
    """SSE stream for visitor order tracking.

    Authorization: session token, ?token= parameter, or order owner.
    No login required — anonymous visitors access via token.
    """
    order = get_object_or_404(Order, pk=order_id)
    if not can_access_order(request, order):
        return HttpResponse("Access denied", status=403)

    channel = visitor_order_channel(order_id)
    return eventstream_events(request, channels=[channel])  # type: ignore[no-any-return]
