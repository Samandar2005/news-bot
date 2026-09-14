"""Integration tests for /api/v1/interests and
/api/v1/users/{telegram_id}/interests.

Uses the `sample_categories` fixture (test-owned rows) rather than the real
14 seeded categories — see tests/integration/conftest.py for why.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_categories_returns_whats_in_the_db(client, sample_categories):
    resp = await client.get("/api/v1/interests/categories")
    assert resp.status_code == 200
    categories = resp.json()
    assert len(categories) == len(sample_categories)
    keys = {c["key"] for c in categories}
    assert keys == {c.key for c in sample_categories}
    for c in categories:
        assert c["name_en"] and c["name_ru"] and c["name_uz"]


@pytest.mark.asyncio
async def test_user_starts_with_no_interests(client, sample_categories):
    await client.post("/api/v1/users", json={"telegram_id": 2001, "language": "en"})
    resp = await client.get("/api/v1/users/2001/interests")
    assert resp.status_code == 200
    assert resp.json()["categories"] == []


@pytest.mark.asyncio
async def test_set_and_get_user_interests(client, sample_categories):
    await client.post("/api/v1/users", json={"telegram_id": 2002, "language": "en"})
    by_key = {c.key: c.id for c in sample_categories}

    resp = await client.put(
        "/api/v1/users/2002/interests",
        json={"category_ids": [by_key["test_tech"], by_key["test_ai"]]},
    )
    assert resp.status_code == 200
    returned_keys = {c["key"] for c in resp.json()["categories"]}
    assert returned_keys == {"test_tech", "test_ai"}

    # confirm it actually persisted, not just echoed back
    get_resp = await client.get("/api/v1/users/2002/interests")
    assert {c["key"] for c in get_resp.json()["categories"]} == {"test_tech", "test_ai"}


@pytest.mark.asyncio
async def test_set_interests_replaces_previous_selection(client, sample_categories):
    await client.post("/api/v1/users", json={"telegram_id": 2003, "language": "en"})
    by_key = {c.key: c.id for c in sample_categories}

    await client.put(
        "/api/v1/users/2003/interests", json={"category_ids": [by_key["test_science"]]}
    )
    resp = await client.put(
        "/api/v1/users/2003/interests", json={"category_ids": [by_key["test_space"]]}
    )
    keys = {c["key"] for c in resp.json()["categories"]}
    assert keys == {"test_space"}  # science should be gone, not accumulated


@pytest.mark.asyncio
async def test_set_interests_rejects_invalid_category_id(client, sample_categories):
    await client.post("/api/v1/users", json={"telegram_id": 2004, "language": "en"})
    resp = await client.put("/api/v1/users/2004/interests", json={"category_ids": [999999]})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_interests_for_unknown_user_404s(client, sample_categories):
    resp = await client.put("/api/v1/users/999997/interests", json={"category_ids": []})
    assert resp.status_code == 404
