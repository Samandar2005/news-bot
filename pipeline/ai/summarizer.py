"""Summarization orchestration (spec Phase 3 stage 11 / Phase 5.2).

Two entry points:
- `summarize_event` — one event, one language. Checks the cache
  (`event_summaries`, unique on event_id+language) first; only calls the
  provider on a genuine cache miss.
- `summarize_top_events` — the batch pass a Celery task runs: only
  considers active events above `settings.summarization_importance_threshold`
  (spec Phase 5.2's "gate summarization by importance" — the single
  biggest cost lever after per-event-not-per-article summarization,
  which clustering already gives us for free by the time an event
  reaches this stage).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.ai.provider_base import SummarizationProvider
from shared.config import settings
from shared.enums import EventStatus
from shared.models import EventSummary, NewsArticle, NewsEvent

DEFAULT_LANGUAGES = ("en", "ru", "uz")


@dataclass(frozen=True, slots=True)
class SummaryOutcome:
    summary: EventSummary
    was_cached: bool


@dataclass(frozen=True, slots=True)
class SummarizationStats:
    events_considered: int
    summaries_created: int
    summaries_already_cached: int


async def summarize_event(
    session: AsyncSession, event: NewsEvent, language: str, provider: SummarizationProvider
) -> SummaryOutcome:
    """Idempotent: calling this twice for the same (event, language) hits
    the cache the second time rather than spending a second API call —
    this is the mechanism, not just a side effect of the batch function's
    own bookkeeping, so it's safe to call directly too.
    """
    existing = await session.execute(
        select(EventSummary).where(
            EventSummary.event_id == event.id, EventSummary.language == language
        )
    )
    cached = existing.scalar_one_or_none()
    if cached is not None:
        return SummaryOutcome(summary=cached, was_cached=True)

    articles_result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.event_id == event.id)
        .order_by(NewsArticle.published_at.asc())
        .limit(settings.summarization_max_articles_per_event)
    )
    articles = list(articles_result.scalars().all())
    if not articles:
        raise ValueError(f"Event {event.id} has no articles to summarize")

    max_chars = settings.summarization_max_article_chars
    source_texts = [f"{a.title}\n{a.content[:max_chars]}" for a in articles]

    result = await provider.summarize(source_texts, language)

    summary = EventSummary(
        event_id=event.id,
        language=language,
        summary_text=result.text,
        generated_at=datetime.now(UTC),
    )
    session.add(summary)
    await session.flush()

    return SummaryOutcome(summary=summary, was_cached=False)


async def summarize_top_events(
    session: AsyncSession,
    provider: SummarizationProvider,
    languages: tuple[str, ...] = DEFAULT_LANGUAGES,
    batch_limit: int = 20,
) -> SummarizationStats:
    result = await session.execute(
        select(NewsEvent)
        .where(
            NewsEvent.status == EventStatus.ACTIVE,
            NewsEvent.importance_score >= settings.summarization_importance_threshold,
        )
        .order_by(NewsEvent.importance_score.desc())
        .limit(batch_limit)
    )
    events = list(result.scalars().all())

    created = 0
    already_cached = 0
    for event in events:
        for language in languages:
            outcome = await summarize_event(session, event, language, provider)
            if outcome.was_cached:
                already_cached += 1
            else:
                created += 1

    return SummarizationStats(
        events_considered=len(events),
        summaries_created=created,
        summaries_already_cached=already_cached,
    )
