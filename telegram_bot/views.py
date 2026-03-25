"""Django async view for Telegram webhook."""

from __future__ import annotations

import logging

from aiogram.types import Update
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from telegram_bot.bot import get_bot, get_dispatcher

logger = logging.getLogger(__name__)


@csrf_exempt
async def telegram_webhook(request: HttpRequest, secret: str) -> HttpResponse:
    """Receive Telegram webhook updates.

    The secret in the URL path prevents unauthorized access.
    Additionally verifies X-Telegram-Bot-Api-Secret-Token header.
    """
    if not settings.TG_TOKEN:
        return HttpResponse("Bot not configured", status=503)

    # Verify secret from URL path.
    if secret != settings.TG_WEBHOOK_SECRET:
        return HttpResponse(status=403)

    # Optionally verify Telegram header.
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret and header_secret != settings.TG_WEBHOOK_SECRET:
        return HttpResponse(status=403)

    try:
        update = Update.model_validate_json(request.body)
    except Exception:
        logger.warning("Invalid Telegram update payload")
        return HttpResponse("Bad request", status=400)

    bot = get_bot()
    dp = get_dispatcher()

    try:
        await dp.feed_update(bot, update)
    except Exception:
        logger.exception("Error processing Telegram update")

    return HttpResponse("ok")
