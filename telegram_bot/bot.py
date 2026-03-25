"""Aiogram3 bot instance, dispatcher, and message handlers."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start and /start CODE for verification."""
    if message.from_user is None or message.chat is None:
        return

    text = message.text or ""
    args = text.split(maxsplit=1)

    if len(args) > 1:
        # /start CODE — verification flow.
        from telegram_bot.verification import verify_telegram

        code = args[1].strip()
        ok = verify_telegram(chat_id=message.chat.id, code=code)
        if ok:
            await message.answer(
                "\u2705 Telegram підключено! Ви будете отримувати сповіщення тут."
            )
        else:
            await message.answer(
                "\u274c Код недійсний або прострочений. Спробуйте ще раз на сайті."
            )
    else:
        await message.answer(
            "\U0001f44b Привіт! Це бот Dobro Djelo.\n\n"
            "Щоб підключити Telegram, натисніть кнопку "
            "«Підключити Telegram» на сторінці каналів у вашому профілі на сайті."
        )


def get_bot() -> Bot:
    """Create a Bot instance with the configured token."""
    from django.conf import settings

    return Bot(token=settings.TG_TOKEN)


def get_dispatcher() -> Dispatcher:
    """Create a Dispatcher with registered handlers."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp
