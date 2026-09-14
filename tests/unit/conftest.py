"""Fixtures for testing bot handlers directly (not through a live Telegram
connection, which this sandbox can't reach anyway — api.telegram.org isn't
in the network allowlist).

FSM state uses aiogram's real MemoryStorage + FSMContext — that machinery
is exercised for real, not mocked. Message/CallbackQuery are lightweight
stand-ins exposing only what the handlers actually touch (.answer,
.from_user, .data, etc.), since constructing full aiogram Telegram-API
pydantic models here would need a real Update payload for no added value.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.services.backend_client import BackendClient


@pytest.fixture
def fsm_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
def mock_backend() -> AsyncMock:
    return AsyncMock(spec=BackendClient)


def make_message(user_id: int = 1, username: str = "tester") -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock(id=user_id, username=username)
    msg.answer = AsyncMock()
    return msg


def make_callback(user_id: int = 1, data: str = "", message: MagicMock | None = None) -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock(id=user_id)
    cb.data = data
    cb.message = message or make_message(user_id)
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb
