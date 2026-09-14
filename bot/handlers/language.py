"""Language selection: the /language command (re-entry) and the callback
that handles a tap on either that or the onboarding keyboard from /start.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.interests import enter_interest_selection
from bot.keyboards.language import language_keyboard
from bot.locales.strings import t
from bot.services.backend_client import BackendClient
from bot.states.onboarding import OnboardingStates

router = Router(name="language")

_TRILINGUAL_LANGUAGE_PROMPT = (
    "🌐 Please choose your language / Пожалуйста, выберите язык / Tilni tanlang:"
)


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext) -> None:
    await state.set_state(OnboardingStates.choosing_language)
    await state.update_data(onboarding=False)
    await message.answer(_TRILINGUAL_LANGUAGE_PROMPT, reply_markup=language_keyboard())


@router.callback_query(OnboardingStates.choosing_language, F.data.startswith("lang:"))
async def on_language_chosen(
    callback: CallbackQuery, state: FSMContext, backend: BackendClient
) -> None:
    language = callback.data.split(":", 1)[1]
    data = await state.get_data()
    onboarding = data.get("onboarding", True)

    await backend.update_user_language(callback.from_user.id, language)
    await callback.answer(t(language, "language_set"))

    if onboarding:
        await enter_interest_selection(
            callback.message, state, backend, language, onboarding=True
        )
    else:
        await state.clear()
        await callback.message.answer(t(language, "language_set"))
        await callback.message.answer(t(language, "main_menu"))
