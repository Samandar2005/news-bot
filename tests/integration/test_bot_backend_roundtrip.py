"""Real round-trip tests: BackendClient talking to the REAL FastAPI app
(via in-process ASGI transport, real Postgres) — not a mocked backend.

**Why this file exists — a real bug it would have caught immediately:**
every other bot test mocks BackendClient entirely (or, for
test_backend_client.py, mocks the HTTP transport with hand-written JSON
fixtures). None of them ever parsed an *actual* response produced by the
real backend schemas. That let a real bug ship silently: UserRead
includes `created_at` and CategoryRead includes `default_weight`, and
UserDTO/CategoryDTO didn't declare those fields — `UserDTO(**response)`
raised `TypeError` on every single real call, meaning `/start` for a
brand new user was broken against a real backend the whole time (see
bot/services/backend_client.py's `_from_json` docstring for the fix).

These tests exercise the full real path: real BackendClient methods,
real HTTP request/response parsing, against the real backend's real
Pydantic schemas — the exact gap that let the bug through.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport

from backend.db.session import get_session
from backend.main import app
from bot.services.backend_client import BackendClient
from shared.config import settings
from shared.models import InterestCategory


@pytest_asyncio.fixture
async def real_backend_client(session) -> AsyncGenerator[BackendClient, None]:
    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    client = BackendClient(
        base_url="http://test", internal_token=settings.internal_api_token, transport=transport
    )
    try:
        yield client
    finally:
        await client.close()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user_round_trip_does_not_raise(real_backend_client):
    """The exact call that was broken: a brand new user's /start flow."""
    user = await real_backend_client.create_user(5001, "roundtrip_tester", "en")
    assert user.telegram_id == 5001
    assert user.language == "en"


@pytest.mark.asyncio
async def test_get_user_round_trip_does_not_raise(real_backend_client):
    await real_backend_client.create_user(5002, "tester", "en")
    user = await real_backend_client.get_user(5002)
    assert user is not None
    assert user.telegram_id == 5002


@pytest.mark.asyncio
async def test_update_user_language_round_trip_does_not_raise(real_backend_client):
    await real_backend_client.create_user(5003, "tester", "en")
    updated = await real_backend_client.update_user_language(5003, "ru")
    assert updated.language == "ru"


@pytest.mark.asyncio
async def test_list_categories_round_trip_does_not_raise(real_backend_client, session):
    """The other broken call: CategoryRead includes default_weight,
    which CategoryDTO didn't declare."""
    session.add(
        InterestCategory(
            key="roundtrip_test_category", name_en="Test", name_ru="Тест", name_uz="Test"
        )
    )
    await session.flush()

    categories = await real_backend_client.list_categories()
    assert any(c.key == "roundtrip_test_category" for c in categories)


@pytest.mark.asyncio
async def test_get_notification_settings_round_trip_does_not_raise(real_backend_client):
    await real_backend_client.create_user(5004, "tester", "en")
    settings_dto = await real_backend_client.get_notification_settings(5004)
    assert settings_dto.morning_enabled is True


@pytest.mark.asyncio
async def test_update_notification_settings_round_trip_does_not_raise(real_backend_client):
    await real_backend_client.create_user(5005, "tester", "en")
    updated = await real_backend_client.update_notification_settings(5005, morning_enabled=False)
    assert updated.morning_enabled is False


@pytest.mark.asyncio
async def test_digest_preview_round_trip_does_not_raise(real_backend_client):
    await real_backend_client.create_user(5006, "tester", "en")
    result = await real_backend_client.get_digest_preview(5006)
    assert result is None  # no events exist in this test's isolated transaction
