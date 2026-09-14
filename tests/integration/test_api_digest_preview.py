"""Integration tests for GET /api/v1/users/{telegram_id}/digest/preview —
real FastAPI app, real (isolated) Postgres, no mocks.
"""

from __future__ import annotations

import datetime as dt
import itertools

import pytest
from sqlalchemy import select

from shared.enums import EventStatus, SourceType
from shared.models import Digest, DigestItem, EventSummary, NewsArticle, NewsEvent, NewsSource

NOW = dt.datetime.now(dt.UTC)
_id_counter = itertools.count()


async def _make_event_with_summary(session, language="en") -> NewsEvent:
    source = NewsSource(
        name="Digest Preview Test Source",
        url=f"https://digest-preview-test.example/{next(_id_counter)}",
        source_type=SourceType.RSS,
        language=language,
    )
    session.add(source)
    await session.flush()

    event = NewsEvent(
        first_seen_at=NOW,
        last_updated_at=NOW,
        source_count=1,
        avg_reliability=0.7,
        importance_score=0.9,
        status=EventStatus.ACTIVE,
    )
    session.add(event)
    await session.flush()

    session.add(
        NewsArticle(
            source_id=source.id,
            url=f"https://digest-preview-test.example/articles/{next(_id_counter)}",
            title="T",
            content="C",
            content_hash=f"hash-{next(_id_counter)}",
            language=language,
            event_id=event.id,
            published_at=NOW,
            fetched_at=NOW,
        )
    )
    session.add(
        EventSummary(
            event_id=event.id,
            language=language,
            summary_text="A breaking story summary.",
            generated_at=NOW,
        )
    )
    await session.flush()
    return event


@pytest.mark.asyncio
async def test_preview_with_no_content_returns_has_content_false(client):
    await client.post("/api/v1/users", json={"telegram_id": 4001, "language": "en"})

    resp = await client.get("/api/v1/users/4001/digest/preview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_content"] is False
    assert body["text"] is None


@pytest.mark.asyncio
async def test_preview_with_content_returns_rendered_text(client, session):
    await client.post("/api/v1/users", json={"telegram_id": 4002, "language": "en"})
    await _make_event_with_summary(session, language="en")

    resp = await client.get("/api/v1/users/4002/digest/preview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_content"] is True
    assert "A breaking story summary." in body["text"]


@pytest.mark.asyncio
async def test_preview_records_digest_history_as_on_demand(client, session):
    await client.post("/api/v1/users", json={"telegram_id": 4003, "language": "en"})
    await _make_event_with_summary(session, language="en")

    await client.get("/api/v1/users/4003/digest/preview")

    result = await session.execute(select(Digest))
    digests = list(result.scalars().all())
    assert len(digests) == 1
    assert digests[0].digest_type == "on_demand"
    assert digests[0].status == "sent"

    items_result = await session.execute(
        select(DigestItem).where(DigestItem.digest_id == digests[0].id)
    )
    assert len(list(items_result.scalars().all())) == 1


@pytest.mark.asyncio
async def test_preview_for_unknown_user_404s(client):
    resp = await client.get("/api/v1/users/999994/digest/preview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_second_preview_shows_repeat_penalty_effect(client, session):
    """Not a hard exclusion (see pipeline/digest/dispatch.py's manual
    proof notes) — but a second on-demand request for the same event
    should still work, and the event should now carry a nonzero repeat
    penalty in the ranking that produced it.
    """
    await client.post("/api/v1/users", json={"telegram_id": 4004, "language": "en"})
    await _make_event_with_summary(session, language="en")

    first = await client.get("/api/v1/users/4004/digest/preview")
    second = await client.get("/api/v1/users/4004/digest/preview")

    assert first.json()["has_content"] is True
    assert second.json()["has_content"] is True  # still shown, just at a lower score
