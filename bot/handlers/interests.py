"""Interest selection: entering the picker, toggling categories, finishing.

`enter_interest_selection` is shared by /start (onboarding), /language
(after an onboarding-flow language change), and /interests (re-entry to
change interests later) — see bot/handlers/start.py and
bot/handlers/language.py.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.interests import interests_keyboard
from bot.locales.strings import t
from bot.services.backend_client import BackendClient, CategoryDTO
from bot.states.onboarding import OnboardingStates

router = Router(name="interests")


def _category_to_dict(c: CategoryDTO) -> dict:
    return {
        "id": c.id,
        "key": c.key,
        "name_en": c.name_en,
        "name_ru": c.name_ru,
        "name_uz": c.name_uz,
    }


async def enter_interest_selection(
    message: Message,
    state: FSMContext,
    backend: BackendClient,
    language: str,
    onboarding: bool,
    preselected: set[int] | None = None,
) -> None:
    categories = await backend.list_categories()
    selected = preselected or set()

    await state.set_state(OnboardingStates.choosing_interests)
    await state.update_data(
        selected=list(selected),
        onboarding=onboarding,
        language=language,
        categories=[_category_to_dict(c) for c in categories],
    )
    await message.answer(
        t(language, "choose_interests"),
        reply_markup=interests_keyboard(categories, selected, language),
    )


@router.message(Command("interests"))
async def cmd_interests(message: Message, state: FSMContext, backend: BackendClient) -> None:
    user = await backend.get_user(message.from_user.id)
    if user is None:
        await message.answer(t("en", "welcome_choose_language"))
        return
    preselected = await backend.get_user_interest_ids(user.telegram_id)
    await enter_interest_selection(
        message, state, backend, user.language, onboarding=False, preselected=preselected
    )


@router.callback_query(OnboardingStates.choosing_interests, F.data.startswith("interest:"))
async def on_interest_toggled(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    selected.symmetric_difference_update({category_id})
    await state.update_data(selected=list(selected))

    categories = [CategoryDTO(**c) for c in data["categories"]]
    language = data["language"]
    await callback.message.edit_reply_markup(
        reply_markup=interests_keyboard(categories, selected, language)
    )
    await callback.answer()


@router.callback_query(OnboardingStates.choosing_interests, F.data == "interests:done")
async def on_interests_done(
    callback: CallbackQuery, state: FSMContext, backend: BackendClient
) -> None:
    data = await state.get_data()
    selected = list(set(data.get("selected", [])))
    language = data["language"]
    onboarding = data.get("onboarding", False)

    if not selected:
        await callback.answer(t(language, "interests_empty_warning"), show_alert=True)
        return

    await backend.set_user_interests(callback.from_user.id, selected)
    await state.clear()

    saved_key = "interests_saved_onboarding" if onboarding else "interests_saved"
    await callback.message.answer(t(language, saved_key))
    await callback.message.answer(t(language, "main_menu"))
    await callback.answer()
