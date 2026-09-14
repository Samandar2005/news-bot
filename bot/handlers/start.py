"""/start — the entry point for onboarding (spec Phase 7)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.interests import enter_interest_selection
from bot.keyboards.language import language_keyboard
from bot.locales.strings import t
from bot.services.backend_client import BackendClient
from bot.states.onboarding import OnboardingStates

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, backend: BackendClient) -> None:
    telegram_id = message.from_user.id
    user = await backend.get_user(telegram_id)

    if user is None:
        user = await backend.create_user(
            telegram_id, message.from_user.username, language="en"
        )
        await state.set_state(OnboardingStates.choosing_language)
        await state.update_data(onboarding=True)
        await message.answer(
            t("en", "welcome_choose_language"), reply_markup=language_keyboard()
        )
        return

    interest_ids = await backend.get_user_interest_ids(telegram_id)
    if not interest_ids:
        # Returning user who started onboarding but never finished it
        # (e.g. picked a language, then dropped off before selecting any
        # interests) — resume right where they left off.
        await enter_interest_selection(message, state, backend, user.language, onboarding=True)
        return

    await state.clear()
    await message.answer(t(user.language, "main_menu"))
