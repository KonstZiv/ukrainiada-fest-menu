"""Telegram channel verification — code generation and linking."""

from __future__ import annotations

import logging
import secrets

from django.core.cache import cache

from user.models import CommunicationChannel

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "tg_verify_"
_CODE_TTL = 600  # 10 minutes


def generate_verification_code(user_id: int) -> str:
    """Generate a one-time code and cache it with the user ID."""
    code = secrets.token_urlsafe(16)
    cache.set(f"{_CACHE_PREFIX}{code}", user_id, timeout=_CODE_TTL)
    return code


def verify_telegram(chat_id: int, code: str) -> bool:
    """Validate code and create/update verified Telegram channel.

    Returns True if verification succeeded.
    """
    cache_key = f"{_CACHE_PREFIX}{code}"
    user_id = cache.get(cache_key)
    if user_id is None:
        return False

    CommunicationChannel.objects.update_or_create(
        user_id=user_id,
        channel_type=CommunicationChannel.ChannelType.TELEGRAM,
        defaults={"address": str(chat_id), "is_verified": True},
    )
    cache.delete(cache_key)
    logger.info("Telegram verified for user #%s (chat_id=%s)", user_id, chat_id)
    return True
