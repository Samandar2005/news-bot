"""Integration tests for /api/v1/users/{telegram_id}/notifications — real
FastAPI app, real (isolated) Postgres, no mocks."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_new_user_has_default_settings(client):
    await client.post("/api/v1/users", json={"telegram_id": 3001, "language": "en"})

    resp = await client.get("/api/v1/users/3001/notifications")

    assert resp.status_code == 200
    body = resp.json()
    assert body["morning_enabled"] is True
    assert body["evening_enabled"] is True
    assert body["morning_time"] == "07:00:00"
    assert body["evening_time"] == "19:00:00"
    assert body["timezone"] == "Asia/Tashkent"


@pytest.mark.asyncio
async def test_get_notifications_for_unknown_user_404s(client):
    resp = await client.get("/api/v1/users/999996/notifications")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_disables_morning_only(client):
    await client.post("/api/v1/users", json={"telegram_id": 3002, "language": "en"})

    resp = await client.patch("/api/v1/users/3002/notifications", json={"morning_enabled": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["morning_enabled"] is False
    assert body["evening_enabled"] is True  # untouched


@pytest.mark.asyncio
async def test_patch_persists(client):
    await client.post("/api/v1/users", json={"telegram_id": 3003, "language": "en"})
    await client.patch("/api/v1/users/3003/notifications", json={"evening_enabled": False})

    resp = await client.get("/api/v1/users/3003/notifications")

    assert resp.json()["evening_enabled"] is False


@pytest.mark.asyncio
async def test_patch_for_unknown_user_404s(client):
    resp = await client.patch("/api/v1/users/999995/notifications", json={"morning_enabled": False})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_missing_internal_token_rejected(client):
    client.headers.pop("X-Internal-Token")
    resp = await client.get("/api/v1/users/3001/notifications")
    assert resp.status_code == 401
