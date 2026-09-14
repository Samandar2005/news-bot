"""Integration tests for pipeline.digest.assembly — real Postgres."""

from __future__ import annotations

import datetime as dt
import itertools

import pytest

from pipeline.digest.assembly import build_digest_for_user
from shared.enums import EventStatus, SourceType
from shared.models import (
    EventSummary,
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
    user = User(telegram_id=next(_id_counter) + 800_000_000, language=language)
    session.add(user)
    await session.flush()
    return user


async def _make_category(session) -> InterestCategory:
    cat = InterestCategory(
        key=f"assembly-test-{next(_id_counter)}", name_en="Test", name_ru="Тест", name_uz="Test"
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


async def _add_article(session, event) -> NewsArticle:
    source = NewsSource(
        name="Assembly Test Source",
        url=f"https://assembly-test.example/{next(_id_counter)}",
        source_type=SourceType.RSS,
        language="en",
    )
    session.add(source)
    await session.flush()
    article = NewsArticle(
        source_id=source.id,
        url=f"https://assembly-test.example/articles/{next(_id_counter)}",
        title="T",
        content="C",
        content_hash=f"hash-{next(_id_counter)}",
        language="en",
        event_id=event.id,
        published_at=NOW,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    return article


async def _add_summary(session, event, language, text="A summary.") -> EventSummary:
    summary = EventSummary(
        event_id=event.id, language=language, summary_text=text, generated_at=NOW
    )
    session.add(summary)
    await session.flush()
    return summary


@pytest.mark.asyncio
async def test_no_content_when_no_events_at_all(session):
    user = await _make_user(session)
    build = await build_digest_for_user(session, user)

    assert build.has_content is False
    assert build.rendered_text is None
    assert build.included == []


@pytest.mark.asyncio
async def test_no_content_when_events_exist_but_no_summary_in_users_language(session):
    user = await _make_user(session, language="en")
    event = await _make_event(session, importance_score=0.9)
    await _add_article(session, event)
    await _add_summary(session, event, language="ru")  # wrong language for this user

    build = await build_digest_for_user(session, user)

    assert build.has_content is False


@pytest.mark.asyncio
async def test_has_content_when_matching_summary_exists(session):
    user = await _make_user(session, language="en")
    event = await _make_event(session, importance_score=0.9)
    await _add_article(session, event)
    await _add_summary(session, event, language="en", text="NASA launched a new mission today.")

    build = await build_digest_for_user(session, user)

    assert build.has_content is True
    assert "NASA launched a new mission today." in build.rendered_text
    assert len(build.included) == 1
    assert build.included[0].event.id == event.id


@pytest.mark.asyncio
async def test_only_includes_events_with_summaries_others_are_silently_excluded(session):
    user = await _make_user(session, language="en")

    with_summary = await _make_event(session, importance_score=0.9)
    await _add_article(session, with_summary)
    await _add_summary(session, with_summary, language="en", text="Has a summary.")

    without_summary = await _make_event(session, importance_score=0.8)
    await _add_article(session, without_summary)
    # deliberately no summary added for this one

    build = await build_digest_for_user(session, user)

    included_ids = {r.event.id for r in build.included}
    assert with_summary.id in included_ids
    assert without_summary.id not in included_ids


@pytest.mark.asyncio
async def test_included_events_preserve_ranked_order(session):
    user = await _make_user(session, language="en")
    category = await _make_category(session)
    session.add(UserInterest(user_id=user.id, category_id=category.id))
    await session.flush()

    high = await _make_event(session, category=category, importance_score=0.9)
    await _add_article(session, high)
    await _add_summary(session, high, "en", text="High importance story.")

    low = await _make_event(session, category=category, importance_score=0.1)
    await _add_article(session, low)
    await _add_summary(session, low, "en", text="Low importance story.")

    build = await build_digest_for_user(session, user)

    assert build.included[0].event.id == high.id
    assert "1. High importance story." in build.rendered_text


@pytest.mark.asyncio
async def test_switching_user_language_changes_digest_content(session):
    """M14's roadmap test criterion: switch language, verify digest
    content actually changes to match. event_summaries are cached per
    (event, language) — this exercises that the lookup genuinely reacts
    to the user's *current* language rather than something decided once
    at an earlier point.

    UNVERIFIED AS OF WRITING (M14): this sandbox's network egress broke
    for essentially every allowlisted domain (pypi.org, github.com,
    archive.ubuntu.com — not just the news/embeddings domains that were
    already known to be blocked), following a full container reset, so
    the Python venv and PostgreSQL could not be reinstalled to actually
    run this test. Written carefully against the same helpers and
    patterns as every other test in this file, and syntax-checked with
    `py_compile`, but not run against a real database like this
    project's other ~230 tests were. Should be the first thing verified
    once environment access is restored.
    """
    user = await _make_user(session, language="en")
    event = await _make_event(session, importance_score=0.9)
    await _add_article(session, event)
    await _add_summary(session, event, language="en", text="English summary text.")
    await _add_summary(session, event, language="uz", text="O'zbekcha xulosa matni.")

    en_build = await build_digest_for_user(session, user)
    assert en_build.has_content is True
    assert "English summary text." in en_build.rendered_text
    assert "O'zbekcha" not in en_build.rendered_text

    user.language = "uz"
    await session.flush()

    uz_build = await build_digest_for_user(session, user)
    assert uz_build.has_content is True
    assert "O'zbekcha xulosa matni." in uz_build.rendered_text
    assert "English summary" not in uz_build.rendered_text
