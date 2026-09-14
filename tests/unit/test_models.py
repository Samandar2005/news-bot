"""Model-level tests: relationships, constraints, and pgvector round-tripping.

These exist to catch schema mistakes early (wrong cascade, missing unique
constraint, etc.) — the kind of bug that's cheap to catch here and
expensive to discover mid-pipeline later.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from shared.enums import DigestStatus, DigestType, SourceType
from shared.models import (
    Digest,
    DigestItem,
    InterestCategory,
    NewsArticle,
    NewsEvent,
    NewsSource,
    User,
    UserInterest,
)


async def _make_category(session, key="technology") -> InterestCategory:
    cat = InterestCategory(
        key=key, name_en="Technology", name_ru="Технологии", name_uz="Texnologiya"
    )
    session.add(cat)
    await session.flush()
    return cat


async def _make_user(session, telegram_id=111) -> User:
    user = User(telegram_id=telegram_id, language="en")
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_create_user(session):
    user = await _make_user(session)
    assert user.id is not None
    assert user.language == "en"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_telegram_id_unique(session):
    await _make_user(session, telegram_id=222)
    session.add(User(telegram_id=222, language="en"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_user_interest_requires_exactly_one_target(session):
    """CHECK constraint: category_id XOR custom_interest_id must be set."""
    user = await _make_user(session, telegram_id=333)
    # Neither category nor custom interest set -> should violate the CHECK.
    session.add(UserInterest(user_id=user.id, created_at=dt.datetime.now(dt.UTC)))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_user_interest_with_category_succeeds(session):
    user = await _make_user(session, telegram_id=444)
    cat = await _make_category(session, key="science")
    session.add(
        UserInterest(user_id=user.id, category_id=cat.id, created_at=dt.datetime.now(dt.UTC))
    )
    await session.flush()  # should not raise


@pytest.mark.asyncio
async def test_cascade_delete_user_removes_interests(session):
    user = await _make_user(session, telegram_id=555)
    cat = await _make_category(session, key="space")
    session.add(
        UserInterest(user_id=user.id, category_id=cat.id, created_at=dt.datetime.now(dt.UTC))
    )
    await session.flush()

    await session.delete(user)
    await session.flush()

    from sqlalchemy import select

    result = await session.execute(select(UserInterest).where(UserInterest.user_id == user.id))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_article_embedding_roundtrip(session):
    """pgvector column actually stores and returns a real vector."""
    source = NewsSource(
        name="Test Feed", url="https://example.com/rss", source_type=SourceType.RSS, language="en"
    )
    session.add(source)
    await session.flush()

    embedding = [0.1] * 1024
    article = NewsArticle(
        source_id=source.id,
        url="https://example.com/article-1",
        title="Test Article",
        content="Some article content.",
        content_hash="a" * 64,
        embedding=embedding,
        published_at=dt.datetime.now(dt.UTC),
        fetched_at=dt.datetime.now(dt.UTC),
    )
    session.add(article)
    await session.flush()
    await session.refresh(article)

    assert len(article.embedding) == 1024
    assert article.embedding[0] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_article_unique_per_source_url(session):
    source = NewsSource(
        name="Dup Feed", url="https://example.com/rss2", source_type=SourceType.RSS, language="en"
    )
    session.add(source)
    await session.flush()

    kwargs = dict(
        source_id=source.id,
        url="https://example.com/same-article",
        title="A",
        content="A",
        content_hash="b" * 64,
        published_at=dt.datetime.now(dt.UTC),
        fetched_at=dt.datetime.now(dt.UTC),
    )
    session.add(NewsArticle(**kwargs))
    await session.flush()

    session.add(NewsArticle(**{**kwargs, "title": "duplicate"}))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_event_clusters_multiple_articles(session):
    source = NewsSource(
        name="Feed A", url="https://a.example.com/rss", source_type=SourceType.RSS, language="en"
    )
    session.add(source)
    await session.flush()

    event = NewsEvent(
        first_seen_at=dt.datetime.now(dt.UTC),
        last_updated_at=dt.datetime.now(dt.UTC),
        source_count=2,
        avg_reliability=0.7,
        importance_score=0.55,
    )
    session.add(event)
    await session.flush()

    for i in range(2):
        session.add(
            NewsArticle(
                source_id=source.id,
                url=f"https://a.example.com/article-{i}",
                title=f"Article {i}",
                content="content",
                content_hash=f"{i}" * 64,
                published_at=dt.datetime.now(dt.UTC),
                fetched_at=dt.datetime.now(dt.UTC),
                event_id=event.id,
            )
        )
    await session.flush()
    await session.refresh(event, attribute_names=["articles"])
    assert len(event.articles) == 2


@pytest.mark.asyncio
async def test_digest_item_links_digest_to_event(session):
    user = await _make_user(session, telegram_id=666)
    event = NewsEvent(
        first_seen_at=dt.datetime.now(dt.UTC),
        last_updated_at=dt.datetime.now(dt.UTC),
        source_count=1,
        avg_reliability=0.5,
        importance_score=0.4,
    )
    session.add(event)
    await session.flush()

    digest = Digest(
        user_id=user.id,
        digest_type=DigestType.MORNING,
        sent_at=dt.datetime.now(dt.UTC),
        status=DigestStatus.SENT,
    )
    session.add(digest)
    await session.flush()

    session.add(
        DigestItem(digest_id=digest.id, event_id=event.id, rank_position=1, final_score=0.9)
    )
    await session.flush()
    await session.refresh(digest, attribute_names=["items"])
    assert len(digest.items) == 1
    assert digest.items[0].event_id == event.id
