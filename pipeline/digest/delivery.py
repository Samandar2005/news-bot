"""Telegram delivery (spec Phase 3 stage 14).

Deliberately never raises — a single bad recipient (blocked the bot,
deleted their account, hit a transient Telegram error) must not stop the
rest of a digest batch. Callers get a plain bool and decide what to do
about it (pipeline/digest/dispatch.py deactivates the user on a
confirmed block).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter

logger = logging.getLogger(__name__)

# If Telegram asks for a longer wait than this, don't stall the whole
# digest batch for one recipient — skip them this cycle and let the next
# scheduled run pick them up naturally.
_MAX_RETRY_AFTER_SECONDS = 5


async def send_digest_message(bot: Bot, telegram_id: int, text: str) -> bool:
    """Returns True if delivered, False otherwise."""
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
        return True
    except TelegramForbiddenError:
        # spec Phase 3 stage 14's named edge case: user blocked the bot.
        # Logged at info, not warning/error — this is an expected,
        # routine occurrence at any real scale, not a system problem.
        logger.info("User %s has blocked the bot", telegram_id)
        return False
    except TelegramRetryAfter as exc:
        logger.warning(
            "Flood control hit sending to %s, retry_after=%ss", telegram_id, exc.retry_after
        )
        if exc.retry_after > _MAX_RETRY_AFTER_SECONDS:
            return False
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.send_message(chat_id=telegram_id, text=text)
            return True
        except TelegramAPIError:
            logger.exception("Retry after flood wait also failed for %s", telegram_id)
            return False
    except TelegramAPIError:
        logger.exception("Failed to send digest to %s", telegram_id)
        return False
