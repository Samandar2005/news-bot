"""Handler logic tests for /settings and /news (M13). Backend is mocked —
its actual behavior is covered by tests/integration/test_api_notifications.py
and tests/integration/test_api_digest_preview.py.
"""

from __future__ import annotations

import pytest

from bot.handlers.news import cmd_news
from bot.handlers.settings import cmd_settings, on_settings_toggled
from bot.services.backend_client import NotificationSettingsDTO, UserDTO
from tests.unit.conftest import make_callback, make_message


def _user(language="en") -> UserDTO:
    return UserDTO(id=1, telegram_id=42, username="tester", language=language, is_active=True)


def _settings(morning=True, evening=True) -> NotificationSettingsDTO:
    return NotificationSettingsDTO(
        morning_enabled=morning,
        evening_enabled=evening,
        morning_time="07:00:00",
        evening_time="19:00:00",
        timezone="Asia/Tashkent",
    )


@pytest.mark.asyncio
async def test_settings_command_shows_current_state(mock_backend):
    mock_backend.get_user.return_value = _user()
    mock_backend.get_notification_settings.return_value = _settings(morning=True, evening=False)
    message = make_message(user_id=42)

    await cmd_settings(message, mock_backend)

    message.answer.assert_awaited_once()
    call_kwargs = message.answer.call_args.kwargs
    keyboard = call_kwargs["reply_markup"]
    button_texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
    assert any("✅" in text for text in button_texts)  # morning is on
    assert any("▫️" in text for text in button_texts)  # evening is off


@pytest.mark.asyncio
async def test_settings_command_for_unknown_user_prompts_start(mock_backend):
    mock_backend.get_user.return_value = None
    message = make_message(user_id=999)

    await cmd_settings(message, mock_backend)

    message.answer.assert_awaited_once()
    mock_backend.get_notification_settings.assert_not_awaited()


@pytest.mark.asyncio
async def test_toggle_morning_flips_current_value(mock_backend):
    mock_backend.get_user.return_value = _user()
    mock_backend.get_notification_settings.return_value = _settings(morning=True, evening=True)
    mock_backend.update_notification_settings.return_value = _settings(
        morning=False, evening=True
    )
    callback = make_callback(user_id=42, data="settings:toggle_morning")

    await on_settings_toggled(callback, mock_backend)

    mock_backend.update_notification_settings.assert_awaited_once_with(42, morning_enabled=False)
    callback.message.edit_reply_markup.assert_awaited_once()
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_toggle_evening_flips_current_value(mock_backend):
    mock_backend.get_user.return_value = _user()
    mock_backend.get_notification_settings.return_value = _settings(morning=True, evening=False)
    mock_backend.update_notification_settings.return_value = _settings(morning=True, evening=True)
    callback = make_callback(user_id=42, data="settings:toggle_evening")

    await on_settings_toggled(callback, mock_backend)

    mock_backend.update_notification_settings.assert_awaited_once_with(42, evening_enabled=True)


@pytest.mark.asyncio
async def test_news_command_sends_digest_when_available(mock_backend):
    mock_backend.get_user.return_value = _user()
    mock_backend.get_digest_preview.return_value = "📰 Your news digest\n\n1. Something happened."
    message = make_message(user_id=42)

    await cmd_news(message, mock_backend)

    message.answer.assert_awaited_once_with("📰 Your news digest\n\n1. Something happened.")


@pytest.mark.asyncio
async def test_news_command_shows_no_content_message_when_empty(mock_backend):
    mock_backend.get_user.return_value = _user(language="ru")
    mock_backend.get_digest_preview.return_value = None
    message = make_message(user_id=42)

    await cmd_news(message, mock_backend)

    message.answer.assert_awaited_once()
    sent_text = message.answer.call_args.args[0]
    assert "новост" in sent_text.lower()  # Russian "no news" message


@pytest.mark.asyncio
async def test_news_command_for_unknown_user_prompts_start(mock_backend):
    mock_backend.get_user.return_value = None
    message = make_message(user_id=999)

    await cmd_news(message, mock_backend)

    mock_backend.get_digest_preview.assert_not_awaited()
