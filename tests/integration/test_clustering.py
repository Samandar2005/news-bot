"""Integration tests for pipeline.processing.clustering — real Postgres,
real pgvector cosine_distance queries, no mocks. Articles are constructed
directly (not through the full RSS ingest pipeline) for fine control over
embeddings/hashes/timestamps.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pipeline.ai.embeddings import compute_embedding
from pipeline.processing.clustering import (
    TIME_WINDOW,
    cluster_article,
    cluster_new_articles,
)
from shared.enums import SourceType
from shared.models import InterestCategory, NewsArticle, NewsSource

NOW = dt.datetime(2026, 8, 20, 12, 0, tzinfo=dt.UTC)


async def _make_source(session, name="Test Source", reliability=0.7) -> NewsSource:
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


async def _make_category(session, key="test_space") -> InterestCategory:
    cat = InterestCategory(key=key, name_en="Space", name_ru="Космос", name_uz="Kosmos")
    session.add(cat)
    await session.flush()
    return cat


async def _make_article(
    session,
    source: NewsSource,
    *,
    title: str,
    content: str,
    category: InterestCategory | None = None,
    published_at: dt.datetime = NOW,
    content_hash: str | None = None,
    embedding: list[float] | None = None,
) -> NewsArticle:
    text = f"{title} {content}"
    article = NewsArticle(
        source_id=source.id,
        url=f"https://example.test/articles/{hash((source.id, title))}",
        title=title,
        content=content,
        content_hash=content_hash or f"hash-{hash(text)}",
        embedding=embedding if embedding is not None else compute_embedding(text),
        language="en",
        category_id=category.id if category else None,
        published_at=published_at,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    return article


@pytest.mark.asyncio
async def test_exact_hash_match_clusters_across_different_sources(session):
    """The core wire-service-syndication case (spec Phase 3 stage 6):
    byte-identical content from two different outlets is the same event.
    """
    source_a = await _make_source(session, "Source A")
    source_b = await _make_source(session, "Source B")
    shared_hash = "identical-content-hash"

    article_a = await _make_article(
        session,
        source_a,
        title="Breaking news",
        content="Same wire text.",
        content_hash=shared_hash,
    )
    assignment_a = await cluster_article(session, article_a)
    assert assignment_a.created_new_event is True

    article_b = await _make_article(
        session,
        source_b,
        title="Breaking news",
        content="Same wire text.",
        content_hash=shared_hash,
    )
    assignment_b = await cluster_article(session, article_b)

    assert assignment_b.created_new_event is False
    assert assignment_b.event.id == assignment_a.event.id


@pytest.mark.asyncio
async def test_near_duplicate_embeddings_cluster_together(session):
    source_a = await _make_source(session, "Source A")
    source_b = await _make_source(session, "Source B")
    category = await _make_category(session)

    article_a = await _make_article(
        session,
        source_a,
        title="NASA announces new Mars mission timeline for rocket launch",
        content="The space station crew will prepare a new satellite for orbit.",
        category=category,
    )
    assignment_a = await cluster_article(session, article_a)

    article_b = await _make_article(
        session,
        source_b,
        title="NASA has announced a new timeline for its Mars mission and rocket launch",
        content="Space station crew members will prepare a satellite for orbit.",
        category=category,
    )
    assignment_b = await cluster_article(session, article_b)

    assert assignment_b.created_new_event is False
    assert assignment_b.event.id == assignment_a.event.id


@pytest.mark.asyncio
async def test_unrelated_articles_get_separate_events(session):
    source = await _make_source(session)
    category = await _make_category(session)

    article_a = await _make_article(
        session,
        source,
        title="NASA announces new Mars mission timeline for rocket launch",
        content="Space station crew prepare satellite for orbit.",
        category=category,
    )
    await cluster_article(session, article_a)

    article_b = await _make_article(
        session,
        source,
        title="Local bakery wins regional award",
        content="Best sourdough bread recipe after years of fundraising.",
        category=category,
    )
    assignment_b = await cluster_article(session, article_b)

    assert assignment_b.created_new_event is True


@pytest.mark.asyncio
async def test_similar_articles_outside_time_window_do_not_cluster(session):
    """Same content, but well outside the 72h window — should be treated
    as separate events even though they'd otherwise match on hash."""
    source_a = await _make_source(session, "Source A")
    source_b = await _make_source(session, "Source B")
    shared_hash = "identical-content-old-vs-new"

    old_time = NOW - (TIME_WINDOW * 2)
    article_old = await _make_article(
        session,
        source_a,
        title="Old story",
        content="Text.",
        content_hash=shared_hash,
        published_at=old_time,
    )
    await cluster_article(session, article_old)

    article_new = await _make_article(
        session,
        source_b,
        title="Old story",
        content="Text.",
        content_hash=shared_hash,
        published_at=NOW,
    )
    assignment_new = await cluster_article(session, article_new)

    assert assignment_new.created_new_event is True


@pytest.mark.asyncio
async def test_event_aggregates_update_as_articles_join(session):
    source_a = await _make_source(session, "Source A", reliability=0.9)
    source_b = await _make_source(session, "Source B", reliability=0.5)
    shared_hash = "aggregate-test-hash"

    article_a = await _make_article(
        session, source_a, title="T", content="C", content_hash=shared_hash
    )
    assignment_a = await cluster_article(session, article_a)
    event = assignment_a.event

    assert event.source_count == 1
    assert event.avg_reliability == pytest.approx(0.9)

    article_b = await _make_article(
        session, source_b, title="T", content="C", content_hash=shared_hash
    )
    await cluster_article(session, article_b)
    await session.refresh(event)

    assert event.source_count == 2
    assert event.avg_reliability == pytest.approx(0.7)  # avg(0.9, 0.5)


@pytest.mark.asyncio
async def test_new_event_inherits_category_and_timestamps_from_first_article(session):
    source = await _make_source(session)
    category = await _make_category(session)
    published = NOW - dt.timedelta(hours=3)

    article = await _make_article(
        session, source, title="T", content="C", category=category, published_at=published
    )
    assignment = await cluster_article(session, article)

    assert assignment.event.category_id == category.id
    assert assignment.event.first_seen_at == published
    assert assignment.event.last_updated_at == published


@pytest.mark.asyncio
async def test_cluster_new_articles_only_processes_unprocessed(session):
    source = await _make_source(session)

    already_done = await _make_article(session, source, title="Old", content="Already clustered")
    already_done.is_processed = True
    await session.flush()

    pending = await _make_article(session, source, title="New", content="Not yet clustered")

    stats = await cluster_new_articles(session)

    assert stats.processed == 1
    await session.refresh(pending)
    assert pending.event_id is not None
    await session.refresh(already_done)
    assert already_done.event_id is None  # untouched — was already is_processed


@pytest.mark.asyncio
async def test_cluster_new_articles_marks_processed_so_rerun_is_a_noop(session):
    source = await _make_source(session)
    await _make_article(session, source, title="Article", content="Some content")

    first_run = await cluster_new_articles(session)
    second_run = await cluster_new_articles(session)

    assert first_run.processed == 1
    assert second_run.processed == 0


@pytest.mark.asyncio
async def test_cluster_new_articles_reports_new_vs_attached_correctly(session):
    source_a = await _make_source(session, "Source A")
    source_b = await _make_source(session, "Source B")
    shared_hash = "batch-stats-hash"

    await _make_article(session, source_a, title="T", content="C", content_hash=shared_hash)
    await _make_article(session, source_b, title="T", content="C", content_hash=shared_hash)
    await _make_article(session, source_a, title="Unrelated", content="Different story entirely")

    stats = await cluster_new_articles(session)

    assert stats.processed == 3
    assert stats.new_events == 2  # first duplicate pair's event + the unrelated one
    assert stats.attached_to_existing == 1  # second half of the duplicate pair
