"""Integration tests for pipeline.processing.reliability — real Postgres,
proving the spec Phase 3 stage 8 edge case actually works: changing a
source's reliability_score recomputes every event that source
contributed to.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pipeline.processing.clustering import cluster_article
from pipeline.processing.reliability import recompute_events_for_source
from shared.enums import SourceType
from shared.models import NewsArticle, NewsSource

NOW = dt.datetime(2026, 8, 20, 12, 0, tzinfo=dt.UTC)


async def _make_source(session, name, reliability=0.7) -> NewsSource:
    source = NewsSource(
        name=name,
        url=f"https://example.test/{name.replace(' ', '-').lower()}",
        source_type=SourceType.RSS,
        language="en",
        reliability_score=reliability,
    )
    session.add(source)
    await session.flush()
    return source


async def _make_article(session, source: NewsSource, *, title: str, content_hash: str):
    article = NewsArticle(
        source_id=source.id,
        url=f"https://example.test/articles/{hash((source.id, title))}",
        title=title,
        content="Some content",
        content_hash=content_hash,
        language="en",
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    return article


@pytest.mark.asyncio
async def test_recompute_updates_avg_reliability_after_score_change(session):
    source_a = await _make_source(session, "Source A", reliability=0.9)
    source_b = await _make_source(session, "Source B", reliability=0.5)
    shared_hash = "reliability-recompute-hash"

    article_a = await _make_article(session, source_a, title="T", content_hash=shared_hash)
    assignment = await cluster_article(session, article_a)
    article_b = await _make_article(session, source_b, title="T", content_hash=shared_hash)
    await cluster_article(session, article_b)

    event = assignment.event
    await session.refresh(event)
    assert event.avg_reliability == pytest.approx(0.7)  # avg(0.9, 0.5)

    # Admin downgrades Source A's reliability after the fact.
    source_a.reliability_score = 0.1
    await session.flush()

    touched = await recompute_events_for_source(session, source_a.id)
    await session.refresh(event)

    assert touched == 1
    assert event.avg_reliability == pytest.approx(0.3)  # avg(0.1, 0.5)


@pytest.mark.asyncio
async def test_recompute_returns_zero_for_source_with_no_clustered_articles(session):
    source = await _make_source(session, "Lonely Source")
    touched = await recompute_events_for_source(session, source.id)
    assert touched == 0


@pytest.mark.asyncio
async def test_recompute_touches_multiple_events_from_same_source(session):
    source = await _make_source(session, "Prolific Source")

    article_1 = await _make_article(session, source, title="Story 1", content_hash="hash-1")
    assignment_1 = await cluster_article(session, article_1)
    article_2 = await _make_article(session, source, title="Story 2", content_hash="hash-2")
    assignment_2 = await cluster_article(session, article_2)

    assert assignment_1.event.id != assignment_2.event.id  # two distinct events

    touched = await recompute_events_for_source(session, source.id)
    assert touched == 2
