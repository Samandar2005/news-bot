"""Handler logic tests. FSM transitions are real (aiogram MemoryStorage);
the backend is mocked since these are unit, not integration, tests — the
backend's actual behavior is covered by tests/integration/test_api_*.py.
"""

from __future__ import annotations

import pytest

from bot.handlers.interests import on_interest_toggled, on_interests_done
from bot.handlers.language import on_language_chosen
from bot.handlers.start import cmd_start
from bot.services.backend_client import CategoryDTO, UserDTO
from bot.states.onboarding import OnboardingStates
from tests.unit.conftest import make_callback, make_message

SAMPLE_CATEGORIES = [
    CategoryDTO(
        id=1, key="tech", name_en="Technology", name_ru="Технологии", name_uz="Texnologiya"
    ),
    CategoryDTO(id=2, key="ai", name_en="AI", name_ru="ИИ", name_uz="SI"),
]


@pytest.mark.asyncio
async def test_start_new_user_prompts_language_selection(fsm_state, mock_backend):
    mock_backend.get_user.return_value = None
    mock_backend.create_user.return_value = UserDTO(
        id=1, telegram_id=42, username="new_guy", language="en", is_active=True
    )
    message = make_message(user_id=42, username="new_guy")

    await cmd_start(message, fsm_state, mock_backend)

    mock_backend.create_user.assert_awaited_once_with(42, "new_guy", language="en")
    assert await fsm_state.get_state() == OnboardingStates.choosing_language
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_returning_user_with_interests_shows_main_menu(fsm_state, mock_backend):
    mock_backend.get_user.return_value = UserDTO(
        id=1, telegram_id=42, username="regular", language="ru", is_active=True
    )
    mock_backend.get_user_interest_ids.return_value = {1, 2}
    message = make_message(user_id=42)

    await cmd_start(message, fsm_state, mock_backend)

    assert await fsm_state.get_state() is None  # cleared, not mid-onboarding
    mock_backend.create_user.assert_not_awaited()
    message.answer.assert_awaited_once()
    # Russian user should get the Russian main menu, not English
    assert "меню" in message.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_start_returning_user_without_interests_resumes_onboarding(fsm_state, mock_backend):
    """User picked a language once, then dropped off before finishing
    interest selection — /start again should resume, not restart."""
    mock_backend.get_user.return_value = UserDTO(
        id=1, telegram_id=42, username="half_done", language="en", is_active=True
    )
    mock_backend.get_user_interest_ids.return_value = set()
    mock_backend.list_categories.return_value = SAMPLE_CATEGORIES
    message = make_message(user_id=42)

    await cmd_start(message, fsm_state, mock_backend)

    assert await fsm_state.get_state() == OnboardingStates.choosing_interests
    mock_backend.create_user.assert_not_awaited()  # user already exists


@pytest.mark.asyncio
async def test_language_chosen_during_onboarding_proceeds_to_interests(fsm_state, mock_backend):
    await fsm_state.set_state(OnboardingStates.choosing_language)
    await fsm_state.update_data(onboarding=True)
    mock_backend.update_user_language.return_value = UserDTO(
        id=1, telegram_id=42, username=None, language="uz", is_active=True
    )
    mock_backend.list_categories.return_value = SAMPLE_CATEGORIES
    callback = make_callback(user_id=42, data="lang:uz")

    await on_language_chosen(callback, fsm_state, mock_backend)

    mock_backend.update_user_language.assert_awaited_once_with(42, "uz")
    assert await fsm_state.get_state() == OnboardingStates.choosing_interests


@pytest.mark.asyncio
async def test_language_chosen_re_entry_shows_main_menu_and_clears_state(fsm_state, mock_backend):
    await fsm_state.set_state(OnboardingStates.choosing_language)
    await fsm_state.update_data(onboarding=False)
    mock_backend.update_user_language.return_value = UserDTO(
        id=1, telegram_id=42, username=None, language="en", is_active=True
    )
    callback = make_callback(user_id=42, data="lang:en")

    await on_language_chosen(callback, fsm_state, mock_backend)

    assert await fsm_state.get_state() is None
    mock_backend.list_categories.assert_not_awaited()  # re-entry skips interests


@pytest.mark.asyncio
async def test_interest_toggle_adds_then_removes_selection(fsm_state):
    await fsm_state.set_state(OnboardingStates.choosing_interests)
    await fsm_state.update_data(
        selected=[],
        onboarding=True,
        language="en",
        categories=[
            {
                "id": c.id,
                "key": c.key,
                "name_en": c.name_en,
                "name_ru": c.name_ru,
                "name_uz": c.name_uz,
            }
            for c in SAMPLE_CATEGORIES
        ],
    )
    callback = make_callback(user_id=42, data="interest:1")

    await on_interest_toggled(callback, fsm_state)
    assert set((await fsm_state.get_data())["selected"]) == {1}

    # tapping the same button again should deselect it
    await on_interest_toggled(callback, fsm_state)
    assert set((await fsm_state.get_data())["selected"]) == set()


@pytest.mark.asyncio
async def test_interests_done_with_selection_saves_and_clears_state(fsm_state, mock_backend):
    await fsm_state.set_state(OnboardingStates.choosing_interests)
    await fsm_state.update_data(selected=[1, 2], onboarding=True, language="en", categories=[])
    callback = make_callback(user_id=42, data="interests:done")

    await on_interests_done(callback, fsm_state, mock_backend)

    mock_backend.set_user_interests.assert_awaited_once_with(42, [1, 2])
    assert await fsm_state.get_state() is None


@pytest.mark.asyncio
async def test_interests_done_with_empty_selection_warns_and_does_not_save(fsm_state, mock_backend):
    await fsm_state.set_state(OnboardingStates.choosing_interests)
    await fsm_state.update_data(selected=[], onboarding=True, language="en", categories=[])
    callback = make_callback(user_id=42, data="interests:done")

    await on_interests_done(callback, fsm_state, mock_backend)

    mock_backend.set_user_interests.assert_not_awaited()
    # still mid-selection — the user needs to actually pick something
    assert await fsm_state.get_state() == OnboardingStates.choosing_interests
    callback.answer.assert_awaited_once()
    assert callback.answer.call_args.kwargs.get("show_alert") is True
