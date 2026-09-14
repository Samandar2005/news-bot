"""Tests for pipeline.digest.delivery.send_digest_message — mocked
aiogram Bot (api.telegram.org isn't reachable from this sandbox, and
even if it were, a real bot token would be needed)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramRetryAfter

from pipeline.digest.delivery import send_digest_message


def _make_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_successful_send_returns_true():
    bot = _make_bot()
    result = await send_digest_message(bot, 12345, "Hello")
    assert result is True
    bot.send_message.assert_awaited_once_with(chat_id=12345, text="Hello")


@pytest.mark.asyncio
async def test_blocked_bot_returns_false_without_raising():
    bot = _make_bot()
    bot.send_message.side_effect = TelegramForbiddenError(method=AsyncMock(), message="blocked")

    result = await send_digest_message(bot, 12345, "Hello")

    assert result is False


@pytest.mark.asyncio
async def test_flood_wait_under_threshold_retries_and_succeeds():
    bot = _make_bot()
    retry_error = TelegramRetryAfter(method=AsyncMock(), message="flood", retry_after=1)
    bot.send_message.side_effect = [retry_error, None]  # fails once, then succeeds

    result = await send_digest_message(bot, 12345, "Hello")

    assert result is True
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_flood_wait_over_threshold_gives_up_without_retrying():
    bot = _make_bot()
    retry_error = TelegramRetryAfter(method=AsyncMock(), message="flood", retry_after=999)
    bot.send_message.side_effect = retry_error

    result = await send_digest_message(bot, 12345, "Hello")

    assert result is False
    assert bot.send_message.await_count == 1  # did not retry a huge wait


@pytest.mark.asyncio
async def test_other_telegram_api_error_returns_false_without_raising():
    bot = _make_bot()
    bot.send_message.side_effect = TelegramNotFound(method=AsyncMock(), message="chat not found")

    result = await send_digest_message(bot, 12345, "Hello")

    assert result is False
