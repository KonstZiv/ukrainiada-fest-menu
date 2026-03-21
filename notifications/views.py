"""Async SSE endpoints — Redis pub-sub subscriber.

Publishing: ``notifications.redis_publish.publish_sse_event()`` pushes a
flat JSON message to Redis channel ``events_channel``.

Subscribing: ``_sse_stream()`` connects to the same Redis channel via
``redis.asyncio``, filters messages by logical channel name and yields
SSE-formatted text to the HTTP response.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from redis.asyncio import Redis as AsyncRedis

from notifications.channels import channels_for_user, visitor_order_channel
from orders.models import Order
from orders.services import can_access_order

logger = logging.getLogger("notifications.sse")


async def _sse_stream(
    channels: list[str],
    client_label: str,
    keepalive_seconds: int = 15,
) -> AsyncIterator[str]:
    """Subscribe to Redis pub-sub and yield SSE events for given channels.

    Filters ``events_channel`` messages by logical channel name.
    Sends keepalive comments to prevent proxy/browser timeout.
    Tracks connection duration and event count for structured logging.
    """
    conf: dict[str, Any] = getattr(settings, "SSE_REDIS", {})
    redis = AsyncRedis(
        host=str(conf.get("host", "localhost")),
        port=int(str(conf.get("port", 6379))),
        db=int(str(conf.get("db", 0))),
    )
    pubsub = redis.pubsub()

    events_delivered = 0
    loop = asyncio.get_event_loop()
    start_time = loop.time()

    try:
        await pubsub.subscribe("events_channel")
    except Exception:
        logger.error("[SSE:err] redis_subscribe_failed %s", client_label, exc_info=True)
        await redis.close()
        return

    logger.info(
        "[SSE:sub] connected %s channels=%s",
        client_label,
        ",".join(channels),
    )

    # Initial padding (flush nginx buffers) + stream-open
    yield ":" + " " * 2048 + "\n\n"
    yield "event: stream-open\ndata:\n\n"

    channel_set = set(channels)

    last_yield = loop.time()

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0,  # safety net if get_message hangs
                )
            except TimeoutError:
                message = None

            if message is None:
                if loop.time() - last_yield >= keepalive_seconds:
                    yield "event: keep-alive\ndata:\n\n"
                    last_yield = loop.time()
                    logger.debug("[SSE:sub] keepalive %s", client_label)
                continue

            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError, TypeError:
                continue

            event_channel = data.pop("channel", "")
            if event_channel not in channel_set:
                continue

            # data is now {"type": "ticket_done", ...} — forward as-is
            yield f"event: message\ndata: {json.dumps(data)}\n\n"
            events_delivered += 1
            last_yield = loop.time()

    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("[SSE:err] stream_error %s", client_label)
    finally:
        duration = int(loop.time() - start_time)
        logger.info(
            "[SSE:sub] disconnected %s duration=%ds events=%d",
            client_label,
            duration,
            events_delivered,
        )
        await pubsub.unsubscribe("events_channel")
        await pubsub.close()
        await redis.close()


async def sse_stream(
    request: HttpRequest,
    order_id: int | None = None,
) -> HttpResponse | StreamingHttpResponse:
    """Unified SSE stream endpoint.

    Staff users (``order_id is None``): subscribes to role-based channels.
    Visitors (``order_id`` provided): subscribes to ``visitor-order-{id}``.
    """
    if order_id is not None:
        # --- Visitor order tracking path ---
        try:
            order = await sync_to_async(Order.objects.get)(pk=order_id)
        except Order.DoesNotExist:
            return HttpResponse("Not found", status=404)

        if not await sync_to_async(can_access_order)(request, order):
            return HttpResponse("Access denied", status=403)

        channels = [visitor_order_channel(order_id)]
        client_label = f"visitor order_id={order_id}"
    else:
        # --- Staff path ---
        user = await sync_to_async(lambda: request.user)()
        is_authenticated = await sync_to_async(lambda: user.is_authenticated)()
        if not is_authenticated:
            return HttpResponse("Login required", status=401)

        channels = await sync_to_async(channels_for_user)(user)  # type: ignore[arg-type]
        if not channels:
            return HttpResponse("No channels for your role", status=403)

        client_label = f"user={user.email} role={user.role}"  # type: ignore[union-attr]

    response = StreamingHttpResponse(
        _sse_stream(channels, client_label),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
