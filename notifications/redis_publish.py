"""Direct Redis publish for SSE events.

Replaces django-eventstream ``send_event()`` with a direct
``redis.publish()`` call.  Lazy-initialises one ``Redis`` client
per process and never raises — failures are logged as warnings.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from redis import Redis

logger = logging.getLogger("notifications.sse")

_redis_client: Redis | None = None


def _get_redis() -> Redis:
    """Return a lazily-created Redis client from ``SSE_REDIS`` settings."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        conf: dict[str, Any] = getattr(settings, "SSE_REDIS", {})
        host = str(conf.get("host", "localhost"))
        port = int(str(conf.get("port", 6379)))
        db = int(str(conf.get("db", 0)))
        logger.info(
            "[SSE:redis] initializing client host=%s port=%d db=%d", host, port, db
        )
        _redis_client = Redis(host=host, port=port, db=db)
    return _redis_client


def publish_sse_event(
    channel: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish SSE event to Redis ``events_channel``.

    Wire format (flat JSON, no wrappers)::

        {"channel": "waiter-7", "type": "ticket_done", "ticket_id": 1, ...}

    Never raises — logs warning on failure.
    """
    message = {"channel": channel, "type": event_type, **data}
    try:
        _get_redis().publish("events_channel", json.dumps(message))
        logger.debug(
            "[SSE:pub] channel=%s type=%s %s",
            channel,
            event_type,
            " ".join(f"{k}={v}" for k, v in data.items()),
        )
    except Exception:
        logger.warning(
            "[SSE:pub] FAILED channel=%s type=%s",
            channel,
            event_type,
            exc_info=True,
        )
