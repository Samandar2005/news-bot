"""Bot entrypoint. Run with: python -m bot.main

Uses long polling for the MVP (simpler to run/debug than a webhook; no
public HTTPS endpoint needed). Switching to a webhook is a deployment-time
decision, not a code-shape one — worth doing once this runs somewhere with
a stable public URL.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.config import settings
from bot.handlers import interests, language, news, start
from bot.handlers import settings as settings_handlers
from bot.locales.strings import t
from bot.services.backend_client import BackendClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.telegram_bot_token or settings.telegram_bot_token == "changeme":
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set — get one from @BotFather and put it in .env"
        )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # MemoryStorage is fine for a single bot process during development.
    # It does not survive restarts and won't work if the bot is ever
    # scaled to more than one replica — swap for aiogram's RedisStorage
    # (Redis is already in the stack) before either of those apply.
    dp = Dispatcher(storage=MemoryStorage())

    backend = BackendClient(settings.backend_base_url, settings.internal_api_token)
    dp["backend"] = backend

    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(interests.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(news.router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled error processing update", exc_info=event.exception)
        update = event.update
        try:
            if update.message is not None:
                await update.message.answer(t("en", "error_generic"))
            elif update.callback_query is not None:
                await update.callback_query.answer(t("en", "error_generic"), show_alert=True)
        except Exception:
            logger.exception("Failed to notify user about the earlier error")
        return True

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await backend.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
