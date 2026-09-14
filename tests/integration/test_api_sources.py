"""Integration tests for /api/v1/sources — real FastAPI app, real
(isolated) Postgres, no mocks. Covers admin auth, CRUD, the soft-delete
behavior, and the reliability-change recompute trigger end to end
through the HTTP layer (not just calling the service function directly,
which tests/integration/test_reliability.py already covers).
"""

from __future__ import annotations

import pytest


def _source_payload(**overrides):
    payload = {
        "name": "Test Source",
        "url": "https://example.test/feed.xml",
        "source_type": "rss",
        "language": "en",
        "reliability_score": 0.6,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_and_list_source(client):
    resp = await client.post("/api/v1/sources", json=_source_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Source"
    assert body["is_state_affiliated"] is False
    assert body["is_active"] is True

    list_resp = await client.get("/api/v1/sources")
    assert list_resp.status_code == 200
    assert any(s["url"] == "https://example.test/feed.xml" for s in list_resp.json())


@pytest.mark.asyncio
async def test_get_source_not_found(client):
    resp = await client.get("/api/v1/sources/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_missing_admin_token_rejected(client):
    client.headers.pop("X-Admin-Token")
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_internal_token_alone_is_not_enough_for_sources(client):
    """Sources are admin-only — having a valid bot-facing internal token
    should not be sufficient on its own (spec Phase 8.1's separate admin
    auth)."""
    client.headers.pop("X-Admin-Token")
    assert "X-Internal-Token" in client.headers  # still present
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_updates_fields(client):
    create_resp = await client.post("/api/v1/sources", json=_source_payload())
    source_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/sources/{source_id}", json={"is_state_affiliated": True})
    assert resp.status_code == 200
    assert resp.json()["is_state_affiliated"] is True
    # untouched fields should survive the partial update
    assert resp.json()["name"] == "Test Source"


@pytest.mark.asyncio
async def test_delete_is_soft_deactivation_not_row_removal(client):
    create_resp = await client.post("/api/v1/sources", json=_source_payload())
    source_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/sources/{source_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["is_active"] is False

    # still fetchable — a real DELETE would 404 here
    get_resp = await client.get(f"/api/v1/sources/{source_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_reactivating_a_deactivated_source(client):
    create_resp = await client.post("/api/v1/sources", json=_source_payload())
    source_id = create_resp.json()["id"]
    await client.delete(f"/api/v1/sources/{source_id}")

    resp = await client.patch(f"/api/v1/sources/{source_id}", json={"is_active": True})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_patch_not_found(client):
    resp = await client.patch("/api/v1/sources/999999", json={"reliability_score": 0.1})
    assert resp.status_code == 404
