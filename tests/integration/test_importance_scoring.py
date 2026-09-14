"""Integration tests for pipeline.scoring.importance's DB-touching
functions — real Postgres, real event/category/article rows.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pipeline.processing.clustering import cluster_article
from pipeline.scoring.importance import score_all_active_events, score_event
from shared.enums import EventStatus, SourceType
from shared.models import InterestCategory, NewsArticle, NewsEvent, NewsSource

NOW = dt.datetime.now(dt.UTC)


async def _make_source(session, reliability=0.7) -> NewsSource:
    source = NewsSource(
        name="Score Test Source",
        url=f"https://score-test.example/{id(object())}",
        source_type=SourceType.RSS,
        language="en",
        reliability_score=reliability,
    )
    session.add(source)
    await session.flush()
    return source


async def _make_category(session, weight=0.6) -> InterestCategory:
    cat = InterestCategory(
        key=f"score-test-{id(object())}",
        name_en="Test",
        name_ru="Тест",
        name_uz="Test",
        default_weight=weight,
    )
    session.add(cat)
    await session.flush()
    return cat


@pytest.mark.asyncio
async def test_score_event_uses_category_weight(session):
    source = await _make_source(session)
    category = await _make_category(session, weight=0.9)

    article = NewsArticle(
        source_id=source.id,
        url="https://score-test.example/a1",
        title="Neutral headline about routine matters",
        content="Content",
        content_hash="score-test-hash-1",
        language="en",
        category_id=category.id,
        clickbait_score=0.0,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    assignment = await cluster_article(session, article)
    event = assignment.event

    score = await score_event(session, event)

    assert event.importance_score == pytest.approx(score)
    assert score > 0  # sanity: a reasonable event should score positively


@pytest.mark.asyncio
async def test_score_event_uses_uncategorized_default_without_crashing(session):
    source = await _make_source(session)
    article = NewsArticle(
        source_id=source.id,
        url="https://score-test.example/a2",
        title="Uncategorized article",
        content="Content",
        content_hash="score-test-hash-2",
        language="en",
        category_id=None,
        clickbait_score=0.0,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    assignment = await cluster_article(session, article)

    score = await score_event(session, assignment.event)
    assert score is not None


@pytest.mark.asyncio
async def test_score_all_active_events_only_scores_active_status(session):
    source = await _make_source(session)
    category = await _make_category(session)

    article = NewsArticle(
        source_id=source.id,
        url="https://score-test.example/a3",
        title="Some story",
        content="Content",
        content_hash="score-test-hash-3",
        language="en",
        category_id=category.id,
        clickbait_score=0.0,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    assignment = await cluster_article(session, article)
    active_event = assignment.event

    archived_event = NewsEvent(
        category_id=category.id,
        first_seen_at=NOW,
        last_updated_at=NOW,
        source_count=1,
        avg_reliability=0.5,
        importance_score=0.0,
        status=EventStatus.ARCHIVED,
    )
    session.add(archived_event)
    await session.flush()

    scored_count = await score_all_active_events(session)

    await session.refresh(active_event)
    await session.refresh(archived_event)

    assert active_event.importance_score != 0.0
    assert archived_event.importance_score == 0.0  # untouched
    assert scored_count >= 1


@pytest.mark.asyncio
async def test_high_clickbait_score_reduces_importance(session):
    source = await _make_source(session)
    category = await _make_category(session)

    clean_article = NewsArticle(
        source_id=source.id,
        url="https://score-test.example/clean",
        title="Central bank raises interest rates",
        content="Content",
        content_hash="score-test-clean",
        language="en",
        category_id=category.id,
        clickbait_score=0.0,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(clean_article)
    await session.flush()
    clean_assignment = await cluster_article(session, clean_article)

    clickbaity_article = NewsArticle(
        source_id=source.id,
        url="https://score-test.example/clickbaity",
        title="A completely different story",
        content="Content",
        content_hash="score-test-clickbaity",
        language="en",
        category_id=category.id,
        clickbait_score=1.0,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(clickbaity_article)
    await session.flush()
    clickbaity_assignment = await cluster_article(session, clickbaity_article)

    clean_score = await score_event(session, clean_assignment.event)
    clickbaity_score = await score_event(session, clickbaity_assignment.event)

    assert clean_score > clickbaity_score
