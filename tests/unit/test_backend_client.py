"""Tests for BackendClient — uses httpx.MockTransport so the real request
building / response parsing / error handling runs, without needing a live
backend or network access.
"""

from __future__ import annotations

import json

import httpx
import pytest

from bot.services.backend_client import BackendClient, BackendError, CategoryDTO


def _client(handler) -> BackendClient:
    return BackendClient(
        "http://backend.test", "test-token", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_get_user_returns_none_on_404():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(handler)
    assert await client.get_user(123) is None


@pytest.mark.asyncio
async def test_get_user_parses_response_and_sends_auth_header():
    seen_headers = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            json={
                "id": 1,
                "telegram_id": 123,
                "username": "alice",
                "language": "en",
                "is_active": True,
            },
        )

    client = _client(handler)
    user = await client.get_user(123)
    assert user is not None
    assert user.telegram_id == 123
    assert user.language == "en"
    assert seen_headers["x-internal-token"] == "test-token"


@pytest.mark.asyncio
async def test_create_user_sends_correct_payload():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": 1,
                "telegram_id": 555,
                "username": "bob",
                "language": "ru",
                "is_active": True,
            },
        )

    client = _client(handler)
    await client.create_user(555, "bob", "ru")
    assert captured["body"] == {"telegram_id": 555, "username": "bob", "language": "ru"}


@pytest.mark.asyncio
async def test_list_categories_parses_list():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "key": "tech",
                    "name_en": "Technology",
                    "name_ru": "Технологии",
                    "name_uz": "Texnologiya",
                }
            ],
        )

    client = _client(handler)
    categories = await client.list_categories()
    assert len(categories) == 1
    assert categories[0].key == "tech"


@pytest.mark.asyncio
async def test_server_error_raises_backend_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = _client(handler)
    with pytest.raises(BackendError):
        await client.get_user_interest_ids(123)


@pytest.mark.asyncio
async def test_set_user_interests_sends_category_ids():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"categories": []})

    client = _client(handler)
    await client.set_user_interests(123, [1, 2, 3])
    assert captured["body"] == {"category_ids": [1, 2, 3]}


def test_category_dto_localized_name_falls_back_to_english():
    cat = CategoryDTO(
        id=1, key="tech", name_en="Technology", name_ru="Технологии", name_uz="Texnologiya"
    )
    assert cat.localized_name("ru") == "Технологии"
    assert cat.localized_name("fr") == "Technology"  # no name_fr attribute -> falls back


@pytest.mark.asyncio
async def test_get_notification_settings_parses_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "morning_enabled": True,
                "evening_enabled": False,
                "morning_time": "07:00:00",
                "evening_time": "19:00:00",
                "timezone": "Asia/Tashkent",
            },
        )

    client = _client(handler)
    settings = await client.get_notification_settings(123)
    assert settings.morning_enabled is True
    assert settings.evening_enabled is False


@pytest.mark.asyncio
async def test_update_notification_settings_only_sends_provided_fields():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "morning_enabled": False,
                "evening_enabled": True,
                "morning_time": "07:00:00",
                "evening_time": "19:00:00",
                "timezone": "Asia/Tashkent",
            },
        )

    client = _client(handler)
    await client.update_notification_settings(123, morning_enabled=False)
    assert captured["body"] == {"morning_enabled": False}  # evening_enabled omitted, not null


@pytest.mark.asyncio
async def test_get_digest_preview_returns_text_when_has_content():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"has_content": True, "text": "Some digest text."})

    client = _client(handler)
    result = await client.get_digest_preview(123)
    assert result == "Some digest text."


@pytest.mark.asyncio
async def test_get_digest_preview_returns_none_when_no_content():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"has_content": False, "text": None})

    client = _client(handler)
    result = await client.get_digest_preview(123)
    assert result is None
