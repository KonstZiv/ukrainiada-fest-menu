"""Async SSE endpoints for real-time updates per user role and visitor order.

Django 6 ASGI requires async views for proper StreamingHttpResponse with
async generators.  django-eventstream's ``events()`` is sync and fails to
stream in ASGI — we bypass it and call ``stream()`` directly.
"""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse

from django_eventstream.eventrequest import EventRequest
from django_eventstream.utils import add_default_headers
from django_eventstream.views import Listener, stream

from notifications.channels import channels_for_user, visitor_order_channel
from orders.models import Order
from orders.services import can_access_order


def _make_sse_response(
    request: HttpRequest,
    channels: list[str],
) -> StreamingHttpResponse:
    """Build a StreamingHttpResponse with django-eventstream's async stream.

    Must be called from a sync context (or via sync_to_async) because
    EventRequest accesses Django ORM internals synchronously.
    """
    event_request = EventRequest(request, view_kwargs={"channels": channels})

    listener = Listener()
    listener.user_id = (
        request.user.pk
        if hasattr(request, "user") and request.user.is_authenticated
        else "anonymous"
    )
    listener.channels = event_request.channels

    response = StreamingHttpResponse(
        stream(event_request, listener),
        content_type="text/event-stream",
    )
    add_default_headers(response, request=request)
    return response


async def user_events(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """SSE stream for the current user's channels.

    Returns 403 if user has no channels (e.g. visitor role).
    Requires authentication.
    """
    user = await sync_to_async(lambda: request.user)()
    is_authenticated = await sync_to_async(lambda: user.is_authenticated)()
    if not is_authenticated:
        return HttpResponse("Login required", status=401)

    channels = await sync_to_async(channels_for_user)(user)  # type: ignore[arg-type]
    if not channels:
        return HttpResponse("No channels for your role", status=403)

    return await sync_to_async(_make_sse_response)(request, channels)


async def visitor_order_events(
    request: HttpRequest, order_id: int
) -> HttpResponse | StreamingHttpResponse:
    """SSE stream for visitor order tracking.

    Authorization: session token, ?token= parameter, or order owner.
    No login required — anonymous visitors access via token.
    """
    order = await sync_to_async(Order.objects.get)(pk=order_id)
    if not await sync_to_async(can_access_order)(request, order):
        return HttpResponse("Access denied", status=403)

    channel = visitor_order_channel(order_id)
    return await sync_to_async(_make_sse_response)(request, [channel])
