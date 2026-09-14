"""Integration tests for pipeline.digest.dispatch.dispatch_digests — real
Postgres, mocked aiogram Bot (see tests/unit/test_digest_delivery.py for
why: no live Telegram access from this sandbox).
"""

from __future__ import annotations

import datetime as dt
import itertools
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select

from pipeline.digest.dispatch import dispatch_digests
from shared.enums import DigestStatus, DigestType, EventStatus, SourceType
from shared.models import (
    Digest,
    DigestItem,
    EventSummary,
    NewsArticle,
    NewsEvent,
    NewsSource,
    NotificationSettings,
    User,
)

NOW = dt.datetime.now(dt.UTC)
_id_counter = itertools.count()


async def _make_user(
    session, *, language="en", morning_enabled=True, evening_enabled=True, is_active=True
) -> User:
    user = User(
        telegram_id=next(_id_counter) + 700_000_000, language=language, is_active=is_active
    )
    session.add(user)
    await session.flush()
    session.add(
        NotificationSettings(
            user_id=user.id, morning_enabled=morning_enabled, evening_enabled=evening_enabled
        )
    )
    await session.flush()
    return user


async def _make_event_with_summary(session, language="en", importance_score=0.9) -> NewsEvent:
    source = NewsSource(
        name="Dispatch Test Source",
        url=f"https://dispatch-test.example/{next(_id_counter)}",
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
        importance_score=importance_score,
        status=EventStatus.ACTIVE,
    )
    session.add(event)
    await session.flush()

    session.add(
        NewsArticle(
            source_id=source.id,
            url=f"https://dispatch-test.example/articles/{next(_id_counter)}",
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
            event_id=event.id, language=language, summary_text="Summary.", generated_at=NOW
        )
    )
    await session.flush()
    return event


def _make_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_dispatch_sends_to_eligible_user_with_content(session):
    await _make_user(session)
    await _make_event_with_summary(session)
    bot = _make_bot()

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.sent == 1
    assert stats.skipped_no_content == 0
    assert stats.failed == 0
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_records_digest_and_digest_items_on_success(session):
    user = await _make_user(session)
    event = await _make_event_with_summary(session)
    bot = _make_bot()

    await dispatch_digests(session, bot, DigestType.MORNING)

    result = await session.execute(select(Digest).where(Digest.user_id == user.id))
    digest = result.scalar_one()
    assert digest.status == DigestStatus.SENT
    assert digest.digest_type == DigestType.MORNING

    items_result = await session.execute(
        select(DigestItem).where(DigestItem.digest_id == digest.id)
    )
    items = list(items_result.scalars().all())
    assert len(items) == 1
    assert items[0].event_id == event.id


@pytest.mark.asyncio
async def test_dispatch_skips_user_with_no_content_and_records_skipped_status(session):
    user = await _make_user(session)
    # no events at all
    bot = _make_bot()

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.skipped_no_content == 1
    bot.send_message.assert_not_awaited()

    result = await session.execute(select(Digest).where(Digest.user_id == user.id))
    digest = result.scalar_one()
    assert digest.status == DigestStatus.SKIPPED_NO_CONTENT


@pytest.mark.asyncio
async def test_dispatch_respects_morning_vs_evening_notification_toggle(session):
    await _make_user(session, morning_enabled=True, evening_enabled=False)
    await _make_event_with_summary(session)
    bot = _make_bot()

    morning_stats = await dispatch_digests(session, bot, DigestType.MORNING)
    evening_stats = await dispatch_digests(session, bot, DigestType.EVENING)

    assert morning_stats.users_considered == 1
    assert evening_stats.users_considered == 0


@pytest.mark.asyncio
async def test_dispatch_ignores_inactive_users(session):
    await _make_user(session, is_active=False)
    await _make_event_with_summary(session)
    bot = _make_bot()

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.users_considered == 0


@pytest.mark.asyncio
async def test_dispatch_deactivates_user_on_blocked_bot_and_records_failed(session):
    user = await _make_user(session)
    await _make_event_with_summary(session)
    bot = _make_bot()
    bot.send_message.side_effect = TelegramForbiddenError(method=AsyncMock(), message="blocked")

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.failed == 1
    await session.refresh(user)
    assert user.is_active is False

    result = await session.execute(select(Digest).where(Digest.user_id == user.id))
    digest = result.scalar_one()
    assert digest.status == DigestStatus.FAILED

    # no digest_items should exist for a failed send — otherwise the
    # repeat-penalty logic in relevance.py would wrongly think this user
    # already received an event they never actually got.
    items_result = await session.execute(
        select(DigestItem).where(DigestItem.digest_id == digest.id)
    )
    assert list(items_result.scalars().all()) == []


@pytest.mark.asyncio
async def test_dispatch_only_includes_summary_in_recipients_language(session):
    await _make_user(session, language="en")
    await _make_user(session, language="ru")
    await _make_event_with_summary(session, language="en")  # only an "en" summary exists
    bot = _make_bot()

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.sent == 1  # only the en user
    assert stats.skipped_no_content == 1  # ru user has nothing to show


@pytest.mark.asyncio
async def test_dispatch_handles_multiple_users_across_batches(session):
    """Exercises the actual batch-splitting logic (not just a single
    small case) — creates more users than one internal batch to confirm
    the batching/sleep logic doesn't drop anyone.
    """
    from pipeline.digest.dispatch import _BATCH_SIZE

    users = [await _make_user(session) for _ in range(_BATCH_SIZE + 3)]
    await _make_event_with_summary(session)
    bot = _make_bot()

    stats = await dispatch_digests(session, bot, DigestType.MORNING)

    assert stats.sent == len(users)
    assert bot.send_message.await_count == len(users)
