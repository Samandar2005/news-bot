"""/news — on-demand digest (M13)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.locales.strings import t
from bot.services.backend_client import BackendClient

router = Router(name="news")


@router.message(Command("news"))
async def cmd_news(message: Message, backend: BackendClient) -> None:
    user = await backend.get_user(message.from_user.id)
    if user is None:
        await message.answer(t("en", "welcome_choose_language"))
        return

    digest_text = await backend.get_digest_preview(message.from_user.id)
    if digest_text is None:
        await message.answer(t(user.language, "news_no_content"))
        return

    await message.answer(digest_text)
