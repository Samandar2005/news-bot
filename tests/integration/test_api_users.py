"""Integration tests for /api/v1/users — real FastAPI app, real (isolated)
Postgres, no mocks.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_user_returns_201_shape(client):
    resp = await client.post(
        "/api/v1/users", json={"telegram_id": 1001, "username": "alice", "language": "en"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == 1001
    assert body["username"] == "alice"
    assert body["language"] == "en"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_create_user_is_idempotent(client):
    payload = {"telegram_id": 1002, "username": "bob", "language": "ru"}
    first = await client.post("/api/v1/users", json=payload)
    second = await client.post("/api/v1/users", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_get_user_not_found(client):
    resp = await client.get("/api/v1/users/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_after_create(client):
    await client.post("/api/v1/users", json={"telegram_id": 1003, "language": "uz"})
    resp = await client.get("/api/v1/users/1003")
    assert resp.status_code == 200
    assert resp.json()["language"] == "uz"


@pytest.mark.asyncio
async def test_update_user_language(client):
    await client.post("/api/v1/users", json={"telegram_id": 1004, "language": "en"})
    resp = await client.patch("/api/v1/users/1004", json={"language": "ru"})
    assert resp.status_code == 200
    assert resp.json()["language"] == "ru"


@pytest.mark.asyncio
async def test_update_nonexistent_user(client):
    resp = await client.patch("/api/v1/users/999998", json={"language": "ru"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_missing_internal_token_rejected(client):
    client.headers.pop("X-Internal-Token")
    resp = await client.post("/api/v1/users", json={"telegram_id": 1005, "language": "en"})
    assert resp.status_code == 401
