"""Integration tests for pipeline.ai.summarizer — real Postgres, but a
FAKE SummarizationProvider (no network call, no API key needed). This is
exactly the split M10's roadmap test criterion calls for: mocked unit
tests for the summarization *logic* (caching, batching, truncation,
importance gating), separate from a real-API test
(Google Gemini provider integration) that's skipped without a
real key.
"""

from __future__ import annotations

import datetime as dt
import itertools

import pytest

from pipeline.ai.provider_base import SummaryResult
from pipeline.ai.summarizer import summarize_event, summarize_top_events
from shared.config import settings
from shared.enums import EventStatus, SourceType
from shared.models import NewsArticle, NewsEvent, NewsSource

NOW = dt.datetime.now(dt.UTC)
_id_counter = itertools.count()


class FakeProvider:
    """Records every call it receives so tests can assert on exactly what
    was sent, without needing a real Google Gemini call."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    async def summarize(self, source_texts: list[str], target_language: str) -> SummaryResult:
        self.calls.append((source_texts, target_language))
        return SummaryResult(
            text=f"Fake {target_language} summary of {len(source_texts)} source(s).",
            input_tokens=100,
            output_tokens=20,
        )


async def _make_source(session) -> NewsSource:
    source = NewsSource(
        name="Summarizer Test Source",
        url=f"https://summarizer-test.example/{next(_id_counter)}",
        source_type=SourceType.RSS,
        language="en",
    )
    session.add(source)
    await session.flush()
    return source


async def _make_event(session, importance_score=0.5, status=EventStatus.ACTIVE) -> NewsEvent:
    event = NewsEvent(
        first_seen_at=NOW,
        last_updated_at=NOW,
        source_count=1,
        avg_reliability=0.7,
        importance_score=importance_score,
        status=status,
    )
    session.add(event)
    await session.flush()
    return event


async def _add_article(session, source, event, *, title="T", content="C", published_at=NOW):
    article = NewsArticle(
        source_id=source.id,
        url=f"https://summarizer-test.example/articles/{next(_id_counter)}",
        title=title,
        content=content,
        content_hash=f"hash-{next(_id_counter)}",
        language="en",
        event_id=event.id,
        published_at=published_at,
        fetched_at=NOW,
    )
    session.add(article)
    await session.flush()
    return article


@pytest.mark.asyncio
async def test_summarize_event_calls_provider_and_stores_result(session):
    source = await _make_source(session)
    event = await _make_event(session)
    await _add_article(session, source, event, title="Breaking story", content="Details here.")
    provider = FakeProvider()

    outcome = await summarize_event(session, event, "en", provider)

    assert outcome.was_cached is False
    assert outcome.summary.language == "en"
    assert "Fake en summary" in outcome.summary.summary_text
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_summarize_event_second_call_hits_cache_not_provider(session):
    source = await _make_source(session)
    event = await _make_event(session)
    await _add_article(session, source, event)
    provider = FakeProvider()

    first = await summarize_event(session, event, "en", provider)
    second = await summarize_event(session, event, "en", provider)

    assert first.was_cached is False
    assert second.was_cached is True
    assert second.summary.id == first.summary.id
    assert len(provider.calls) == 1  # not called twice


@pytest.mark.asyncio
async def test_summarize_event_different_languages_are_independent(session):
    source = await _make_source(session)
    event = await _make_event(session)
    await _add_article(session, source, event)
    provider = FakeProvider()

    en_outcome = await summarize_event(session, event, "en", provider)
    ru_outcome = await summarize_event(session, event, "ru", provider)

    assert en_outcome.summary.id != ru_outcome.summary.id
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_summarize_event_with_no_articles_raises(session):
    event = await _make_event(session)
    provider = FakeProvider()

    with pytest.raises(ValueError, match="no articles"):
        await summarize_event(session, event, "en", provider)


@pytest.mark.asyncio
async def test_summarize_event_truncates_long_content(session):
    source = await _make_source(session)
    event = await _make_event(session)
    long_content = "x" * (settings.summarization_max_article_chars + 500)
    await _add_article(session, source, event, title="T", content=long_content)
    provider = FakeProvider()

    await summarize_event(session, event, "en", provider)

    sent_text = provider.calls[0][0][0]
    # title + "\n" + truncated content
    assert len(sent_text) <= len("T\n") + settings.summarization_max_article_chars


@pytest.mark.asyncio
async def test_summarize_event_caps_number_of_articles_sent(session):
    source = await _make_source(session)
    event = await _make_event(session)
    extra = settings.summarization_max_articles_per_event + 3
    for i in range(extra):
        await _add_article(session, source, event, title=f"Article {i}", content="content")
    provider = FakeProvider()

    await summarize_event(session, event, "en", provider)

    sent_source_texts = provider.calls[0][0]
    assert len(sent_source_texts) == settings.summarization_max_articles_per_event


@pytest.mark.asyncio
async def test_summarize_top_events_skips_events_below_importance_threshold(session):
    source = await _make_source(session)
    below = await _make_event(
        session, importance_score=settings.summarization_importance_threshold - 0.1
    )
    await _add_article(session, source, below)
    provider = FakeProvider()

    stats = await summarize_top_events(session, provider, languages=("en",))

    assert stats.events_considered == 0
    assert stats.summaries_created == 0
    assert len(provider.calls) == 0


@pytest.mark.asyncio
async def test_summarize_top_events_includes_events_at_or_above_threshold(session):
    source = await _make_source(session)
    at_threshold = await _make_event(
        session, importance_score=settings.summarization_importance_threshold
    )
    await _add_article(session, source, at_threshold)
    provider = FakeProvider()

    stats = await summarize_top_events(session, provider, languages=("en",))

    assert stats.events_considered == 1
    assert stats.summaries_created == 1


@pytest.mark.asyncio
async def test_summarize_top_events_ignores_archived_events(session):
    source = await _make_source(session)
    archived = await _make_event(session, importance_score=0.9, status=EventStatus.ARCHIVED)
    await _add_article(session, source, archived)
    provider = FakeProvider()

    stats = await summarize_top_events(session, provider, languages=("en",))

    assert stats.events_considered == 0


@pytest.mark.asyncio
async def test_summarize_top_events_generates_for_every_requested_language(session):
    source = await _make_source(session)
    event = await _make_event(session, importance_score=0.9)
    await _add_article(session, source, event)
    provider = FakeProvider()

    stats = await summarize_top_events(session, provider, languages=("en", "ru", "uz"))

    assert stats.summaries_created == 3
    assert {call[1] for call in provider.calls} == {"en", "ru", "uz"}


@pytest.mark.asyncio
async def test_summarize_top_events_second_run_only_hits_cache(session):
    source = await _make_source(session)
    event = await _make_event(session, importance_score=0.9)
    await _add_article(session, source, event)
    provider = FakeProvider()

    await summarize_top_events(session, provider, languages=("en",))
    second_stats = await summarize_top_events(session, provider, languages=("en",))

    assert second_stats.summaries_created == 0
    assert second_stats.summaries_already_cached == 1
    assert len(provider.calls) == 1  # still just the one real call from the first run
