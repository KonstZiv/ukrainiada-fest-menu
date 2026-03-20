"""Async SSE endpoints — custom Redis pub-sub subscriber.

django-eventstream's ``stream()`` async generator blocks in Django 6 ASGI
with uvicorn workers.  We use ``send_event()`` for publishing (it pushes
to Redis ``events_channel``) and our own async Redis subscriber for
delivering events to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from redis.asyncio import Redis as AsyncRedis

from notifications.channels import channels_for_user, visitor_order_channel
from orders.models import Order
from orders.services import can_access_order

logger = logging.getLogger("notifications")


async def _sse_stream(
    channels: list[str],
    keepalive_seconds: int = 15,
) -> AsyncIterator[str]:
    """Subscribe to Redis pub-sub and yield SSE events for given channels.

    Filters ``events_channel`` messages by channel name.
    Sends keepalive comments to prevent proxy/browser timeout.
    """
    redis_conf = getattr(settings, "EVENTSTREAM_REDIS", {})
    redis = AsyncRedis(
        host=str(redis_conf.get("host", "localhost")),
        port=int(str(redis_conf.get("port", 6379))),
        db=int(str(redis_conf.get("db", 0))),
    )
    pubsub = redis.pubsub()
    await pubsub.subscribe("events_channel")

    # Initial padding (flush nginx buffers) + stream-open
    yield ":" + " " * 2048 + "\n\n"
    yield "event: stream-open\ndata:\n\n"

    channel_set = set(channels)

    try:
        while True:
            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                timeout=keepalive_seconds,
            )
            if message is None:
                # Timeout — send keepalive
                yield "event: keep-alive\ndata:\n\n"
                continue

            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError, TypeError:
                continue

            event_channel = data.get("channel", "")
            if event_channel not in channel_set:
                continue

            event_type = data.get("event_type", "message")
            event_data = data.get("data", "")

            yield f"event: {event_type}\ndata: {event_data}\n\n"

    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("SSE stream error")
    finally:
        await pubsub.unsubscribe("events_channel")
        await pubsub.close()
        await redis.close()


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

    response = StreamingHttpResponse(
        _sse_stream(channels),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def visitor_order_events(
    request: HttpRequest, order_id: int
) -> HttpResponse | StreamingHttpResponse:
    """SSE stream for visitor order tracking.

    Authorization: session token, ?token= parameter, or order owner.
    No login required — anonymous visitors access via token.
    """
    try:
        order = await sync_to_async(Order.objects.get)(pk=order_id)
    except Order.DoesNotExist:
        return HttpResponse("Not found", status=404)

    if not await sync_to_async(can_access_order)(request, order):
        return HttpResponse("Access denied", status=403)

    channel = visitor_order_channel(order_id)
    response = StreamingHttpResponse(
        _sse_stream([channel]),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
