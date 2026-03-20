"""Async SSE endpoints for real-time updates per user role and visitor order.

Django 6 ASGI requires the StreamingHttpResponse with async generator
to be created directly in the async view — NOT inside sync_to_async.
Only the ORM-touching parts (EventRequest, auth checks) run via
sync_to_async; the response itself is assembled in the async context
so Django's ASGI handler properly iterates the async generator.
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


def _build_event_request(
    request: HttpRequest,
    channels: list[str],
) -> EventRequest:
    """Create EventRequest (sync — touches ORM internals)."""
    return EventRequest(request, view_kwargs={"channels": channels})


def _get_user_id(request: HttpRequest) -> str:
    """Extract user ID for listener (sync — touches request.user)."""
    if hasattr(request, "user") and request.user.is_authenticated:
        return str(request.user.pk)
    return "anonymous"


async def user_events(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """SSE stream for the current user's channels.

    Returns 401 if not authenticated, 403 if no channels for role.
    """
    user = await sync_to_async(lambda: request.user)()
    is_authenticated = await sync_to_async(lambda: user.is_authenticated)()
    if not is_authenticated:
        return HttpResponse("Login required", status=401)

    channels = await sync_to_async(channels_for_user)(user)  # type: ignore[arg-type]
    if not channels:
        return HttpResponse("No channels for your role", status=403)

    event_request = await sync_to_async(_build_event_request)(request, channels)
    user_id = await sync_to_async(_get_user_id)(request)

    listener = Listener()
    listener.user_id = user_id
    listener.channels = event_request.channels

    response = StreamingHttpResponse(
        stream(event_request, listener),
        content_type="text/event-stream",
    )
    await sync_to_async(add_default_headers)(response, request=request)
    return response


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
    event_request = await sync_to_async(_build_event_request)(request, [channel])

    listener = Listener()
    listener.user_id = "anonymous"
    listener.channels = event_request.channels

    response = StreamingHttpResponse(
        stream(event_request, listener),
        content_type="text/event-stream",
    )
    await sync_to_async(add_default_headers)(response, request=request)
    return response
