"""Digest delivery via email and Telegram."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail

if TYPE_CHECKING:
    from user.models import User

logger = logging.getLogger(__name__)


def deliver_to_user(
    user: User, subject: str, body_text: str, body_html: str = ""
) -> bool:
    """Send message via the user's highest-priority verified channel.

    Returns True if delivery succeeded.
    """
    channels = user.channels.filter(is_verified=True).order_by("priority")

    for ch in channels:
        if ch.channel_type == "email":
            try:
                send_mail(
                    subject=subject,
                    message=body_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[ch.address],
                    html_message=body_html or None,
                    fail_silently=False,
                )
                logger.info("Digest email sent to %s", ch.address)
                return True
            except Exception:
                logger.exception("Failed to send email to %s", ch.address)
                continue

        if ch.channel_type == "telegram":
            try:
                _send_telegram_sync(int(ch.address), body_text)
                logger.info("Digest Telegram sent to chat %s", ch.address)
                return True
            except Exception:
                logger.exception("Failed to send Telegram to chat %s", ch.address)
                continue

    logger.warning("No delivery channel available for user #%s", user.pk)
    return False


def _send_telegram_sync(chat_id: int, text: str) -> None:
    """Send a Telegram message synchronously (for use in Celery tasks)."""
    if not settings.TG_TOKEN:
        return

    from telegram_bot.bot import get_bot

    async def _send() -> None:
        bot = get_bot()
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        finally:
            await bot.session.close()

    asyncio.run(_send())
