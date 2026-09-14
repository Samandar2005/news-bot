"""Integration tests for pipeline.scoring.relevance's DB-touching
functions — real Postgres, real fixture users/events per M11's roadmap
test criterion.
"""

from __future__ import annotations

import datetime as dt
import itertools

import pytest

from pipeline.scoring.relevance import (
    compute_geo_relevance,
    compute_interest_match,
    compute_repeat_penalty,
    get_candidate_events,
    rank_events_for_user,
)
from shared.enums import DigestStatus, DigestType, EventStatus, SourceType
from shared.models import (
    CustomInterest,
    Digest,
    DigestItem,
    InterestCategory,
    NewsArticle,
    NewsEvent,
    NewsSource,
    User,
    UserInterest,
)

NOW = dt.datetime.now(dt.UTC)
_id_counter = itertools.count()


async def _make_user(session, language="en") -> User:
    user = User(telegram_id=next(_id_counter) + 900_000_000, language=language)
    session.add(user)
    await session.flush()
    return user


async def _make_category(session) -> InterestCategory:
    cat = InterestCategory(
        key=f"relevance-test-{next(_id_counter)}", name_en="Test", name_ru="Тест", name_uz="Test"
    )
    session.add(cat)
    await session.flush()
    return cat


async def _make_event(session, *, category=None, importance_score=0.5) -> NewsEvent:
    event = NewsEvent(
        category_id=category.id if category else None,
        first_seen_at=NOW,
        last_updated_at=NOW,
        source_count=1,
        avg_reliability=0.7,
        importance_score=importance_score,
        status=EventStatus.ACTIVE,
    )
    session.add(event)
    await session.flush()
    return event


async def _add_article(session, event, *, title="T", content="C") -> NewsArticle:
    source = NewsSource(
        name="Relevance Test Source",
        url=f"https://relevance-test.example/{next(_id_counter)}",
        source_type=SourceType.RSS,
        language="en",
    )
    session.add(source)
    await session.flush()
    article = NewsArticle(
        source_id=source.id,
        url=f"https://relevance-test.example/articles/{next(_id_counter)}",
        title=title,
        content=content,
        content_hash=f"hash-{next(_id_counter)}",
        language="en",
        event_id=event.id,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    return article


@pytest.mark.asyncio
async def test_interest_match_for_selected_category(session):
    user = await _make_user(session)
    category = await _make_category(session)
    session.add(UserInterest(user_id=user.id, category_id=category.id))
    await session.flush()
    event = await _make_event(session, category=category)

    match = await compute_interest_match(session, user.id, event)
    assert match == 1.0


@pytest.mark.asyncio
async def test_interest_match_for_unselected_category(session):
    user = await _make_user(session)
    selected = await _make_category(session)
    other = await _make_category(session)
    session.add(UserInterest(user_id=user.id, category_id=selected.id))
    await session.flush()
    event = await _make_event(session, category=other)

    match = await compute_interest_match(session, user.id, event)
    assert match == 0.0


@pytest.mark.asyncio
async def test_interest_match_via_custom_interest_keyword(session):
    user = await _make_user(session)
    custom = CustomInterest(user_id=user.id, phrase="quantum computing")
    session.add(custom)
    await session.flush()
    session.add(UserInterest(user_id=user.id, custom_interest_id=custom.id))
    await session.flush()

    event = await _make_event(session)
    await _add_article(
        session, event, title="Breakthrough in quantum computing", content="Details."
    )

    match = await compute_interest_match(session, user.id, event)
    assert 0.0 < match < 1.0  # a real but lesser-weighted match


@pytest.mark.asyncio
async def test_interest_match_custom_interest_no_keyword_hit(session):
    user = await _make_user(session)
    custom = CustomInterest(user_id=user.id, phrase="quantum computing")
    session.add(custom)
    await session.flush()
    session.add(UserInterest(user_id=user.id, custom_interest_id=custom.id))
    await session.flush()

    event = await _make_event(session)
    await _add_article(session, event, title="Local weather forecast", content="Sunny today.")

    match = await compute_interest_match(session, user.id, event)
    assert match == 0.0


@pytest.mark.asyncio
async def test_geo_relevance_boosts_uzbek_language_users_on_relevant_content(session):
    uz_user = await _make_user(session, language="uz")
    event = await _make_event(session)
    await _add_article(
        session, event, title="New metro line opens in Tashkent", content="Details here."
    )

    relevance = await compute_geo_relevance(session, uz_user, event)
    assert relevance == 1.0


@pytest.mark.asyncio
async def test_geo_relevance_does_not_apply_to_non_uzbek_users(session):
    en_user = await _make_user(session, language="en")
    event = await _make_event(session)
    await _add_article(
        session, event, title="New metro line opens in Tashkent", content="Details here."
    )

    relevance = await compute_geo_relevance(session, en_user, event)
    assert relevance == 0.0


@pytest.mark.asyncio
async def test_geo_relevance_zero_for_unrelated_content_even_for_uzbek_user(session):
    uz_user = await _make_user(session, language="uz")
    event = await _make_event(session)
    await _add_article(session, event, title="Stock market update", content="Shares rose today.")

    relevance = await compute_geo_relevance(session, uz_user, event)
    assert relevance == 0.0


@pytest.mark.asyncio
async def test_repeat_penalty_after_event_was_already_digested(session):
    user = await _make_user(session)
    event = await _make_event(session)

    digest = Digest(
        user_id=user.id, digest_type=DigestType.MORNING, sent_at=NOW, status=DigestStatus.SENT
    )
    session.add(digest)
    await session.flush()
    session.add(
        DigestItem(digest_id=digest.id, event_id=event.id, rank_position=1, final_score=0.5)
    )
    await session.flush()

    penalty = await compute_repeat_penalty(session, user.id, event)
    assert penalty == 1.0


@pytest.mark.asyncio
async def test_no_repeat_penalty_for_never_sent_event(session):
    user = await _make_user(session)
    event = await _make_event(session)

    penalty = await compute_repeat_penalty(session, user.id, event)
    assert penalty == 0.0


@pytest.mark.asyncio
async def test_get_candidate_events_excludes_archived(session):
    active = await _make_event(session, importance_score=0.5)
    archived_event = NewsEvent(
        first_seen_at=NOW,
        last_updated_at=NOW,
        source_count=1,
        avg_reliability=0.5,
        importance_score=0.9,
        status=EventStatus.ARCHIVED,
    )
    session.add(archived_event)
    await session.flush()

    candidates = await get_candidate_events(session)
    candidate_ids = {c.id for c in candidates}
    assert active.id in candidate_ids
    assert archived_event.id not in candidate_ids


@pytest.mark.asyncio
async def test_rank_events_for_user_orders_by_final_score_descending(session):
    user = await _make_user(session)
    category = await _make_category(session)
    session.add(UserInterest(user_id=user.id, category_id=category.id))
    await session.flush()

    matched_high_importance = await _make_event(session, category=category, importance_score=0.7)
    unmatched_low_importance = await _make_event(session, importance_score=0.1)

    ranked = await rank_events_for_user(
        session, user, candidate_events=[unmatched_low_importance, matched_high_importance]
    )

    assert ranked[0].event.id == matched_high_importance.id
    assert ranked[0].final_score > ranked[1].final_score


@pytest.mark.asyncio
async def test_rank_events_for_user_respects_limit(session):
    user = await _make_user(session)
    events = [await _make_event(session, importance_score=0.1 * i) for i in range(1, 6)]

    ranked = await rank_events_for_user(session, user, candidate_events=events, limit=2)

    assert len(ranked) == 2


@pytest.mark.asyncio
async def test_rank_events_for_user_important_unmatched_beats_trivial_matched(session):
    """End-to-end version of the pure-formula test in
    tests/unit/test_relevance.py — proves the override actually happens
    with real DB-backed interest matching, not just the isolated formula.
    """
    user = await _make_user(session)
    category = await _make_category(session)
    session.add(UserInterest(user_id=user.id, category_id=category.id))
    await session.flush()

    trivial_matched = await _make_event(session, category=category, importance_score=0.05)
    important_unmatched = await _make_event(session, importance_score=0.9)

    ranked = await rank_events_for_user(
        session, user, candidate_events=[trivial_matched, important_unmatched]
    )

    assert ranked[0].event.id == important_unmatched.id
