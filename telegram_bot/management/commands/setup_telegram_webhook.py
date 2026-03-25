"""Register Telegram webhook with the Telegram API."""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Register the Telegram webhook URL with the Telegram Bot API."

    def handle(self, **options: Any) -> None:
        if not settings.TG_TOKEN:
            self.stderr.write(self.style.ERROR("TG_TOKEN not configured."))
            return
        if not settings.TG_WEBHOOK_SECRET:
            self.stderr.write(self.style.ERROR("TG_WEBHOOK_SECRET not configured."))
            return

        webhook_url = (
            f"{settings.TG_WEBHOOK_BASE_URL}/bot/webhook/{settings.TG_WEBHOOK_SECRET}/"
        )
        self.stdout.write(f"Setting webhook: {webhook_url}")

        asyncio.run(self._set_webhook(webhook_url))

    async def _set_webhook(self, url: str) -> None:
        bot = Bot(token=settings.TG_TOKEN)
        try:
            await bot.set_webhook(
                url=url,
                secret_token=settings.TG_WEBHOOK_SECRET,
                drop_pending_updates=True,
            )
            info = await bot.get_webhook_info()
            self.stdout.write(self.style.SUCCESS(f"Webhook set: {info.url}"))
        finally:
            await bot.session.close()
