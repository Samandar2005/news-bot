"""/settings — notification toggle (M13)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.settings import settings_keyboard
from bot.locales.strings import t
from bot.services.backend_client import BackendClient

router = Router(name="settings")


@router.message(Command("settings"))
async def cmd_settings(message: Message, backend: BackendClient) -> None:
    user = await backend.get_user(message.from_user.id)
    if user is None:
        await message.answer(t("en", "welcome_choose_language"))
        return

    settings = await backend.get_notification_settings(message.from_user.id)
    await message.answer(
        t(user.language, "settings_title"),
        reply_markup=settings_keyboard(
            settings.morning_enabled, settings.evening_enabled, user.language
        ),
    )


@router.callback_query(F.data.in_({"settings:toggle_morning", "settings:toggle_evening"}))
async def on_settings_toggled(callback: CallbackQuery, backend: BackendClient) -> None:
    telegram_id = callback.from_user.id
    user = await backend.get_user(telegram_id)
    if user is None:
        await callback.answer()
        return

    current = await backend.get_notification_settings(telegram_id)

    if callback.data == "settings:toggle_morning":
        updated = await backend.update_notification_settings(
            telegram_id, morning_enabled=not current.morning_enabled
        )
    else:
        updated = await backend.update_notification_settings(
            telegram_id, evening_enabled=not current.evening_enabled
        )

    await callback.message.edit_reply_markup(
        reply_markup=settings_keyboard(
            updated.morning_enabled, updated.evening_enabled, user.language
        )
    )
    await callback.answer(t(user.language, "settings_updated"))
