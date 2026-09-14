"""Event importance scoring (spec Phase 3 stage 9 / Phase 6's formula).

    Importance(event) = w1*log(1+S) + w2*R̄ + w3*C + w4*F - w5*CB

Where S=source_count, R̄=avg_reliability, C=category weight,
F=freshness (exponential decay since first_seen_at), CB=avg clickbait
score across the event's articles. Weights and the freshness decay
constant live in shared/config.py (Settings), not hardcoded here, since
spec Phase 6.3 explicitly frames them as a tunable starting point.

**Why this is a separate pass from clustering, run on its own schedule**
(spec's own stage ordering: clustering is stage 7, importance scoring is
stage 9): source_count and avg_reliability only change when an article
joins or leaves an event, so clustering.py's refresh_event_aggregates
keeps those current as a side effect of clustering itself. Freshness is
different — it decays continuously with wall-clock time even for an
event nobody has touched in hours. An event scored once at creation and
never rescored would keep looking exactly as important at 3am as it did
the moment it broke, which defeats the point of a freshness term at all.
So importance_score needs its own periodic recomputation pass,
independent of whether clustering activity happened.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.enums import EventStatus
from shared.models import InterestCategory, NewsArticle, NewsEvent

# Applied when an event has no category (shouldn't normally happen once
# categorization is working, but scoring must never crash on it) or when
# its category was deleted out from under it.
_DEFAULT_CATEGORY_WEIGHT = 0.5


def compute_importance(
    *,
    source_count: int,
    avg_reliability: float,
    category_weight: float,
    hours_since_first_seen: float,
    avg_clickbait_score: float,
) -> float:
    """Pure function, no DB access — the actual formula, fully
    unit-testable against constructed cases (per M9's roadmap test
    criterion) without needing a database at all.
    """
    # Guards against clock skew or a first_seen_at that's slightly in the
    # future (e.g. a source's published_at timestamp ahead of collection
    # time) producing a nonsensical freshness > 1.
    hours_since_first_seen = max(hours_since_first_seen, 0.0)
    freshness = math.exp(-hours_since_first_seen / settings.freshness_decay_hours)

    return (
        settings.weight_source_count * math.log1p(source_count)
        + settings.weight_reliability * avg_reliability
        + settings.weight_category * category_weight
        - settings.weight_clickbait_penalty * avg_clickbait_score
        + settings.weight_freshness * freshness
    )


async def _avg_clickbait_score(session: AsyncSession, event_id: int) -> float:
    result = await session.execute(
        select(func.avg(NewsArticle.clickbait_score)).where(
            NewsArticle.event_id == event_id, NewsArticle.clickbait_score.is_not(None)
        )
    )
    value = result.scalar()
    return float(value) if value is not None else 0.0


async def _category_weight(session: AsyncSession, category_id: int | None) -> float:
    if category_id is None:
        return _DEFAULT_CATEGORY_WEIGHT
    category = await session.get(InterestCategory, category_id)
    return category.default_weight if category is not None else _DEFAULT_CATEGORY_WEIGHT


async def score_event(session: AsyncSession, event: NewsEvent) -> float:
    """Computes and persists (on the passed event object; caller flushes)
    importance_score for one event. Returns the score for convenience."""
    category_weight = await _category_weight(session, event.category_id)
    avg_clickbait = await _avg_clickbait_score(session, event.id)
    hours_since_first_seen = (datetime.now(UTC) - event.first_seen_at).total_seconds() / 3600

    event.importance_score = compute_importance(
        source_count=event.source_count,
        avg_reliability=event.avg_reliability,
        category_weight=category_weight,
        hours_since_first_seen=hours_since_first_seen,
        avg_clickbait_score=avg_clickbait,
    )
    return event.importance_score


async def score_all_active_events(session: AsyncSession, batch_limit: int = 500) -> int:
    """Recomputes importance_score for every active event — see module
    docstring for why this must re-run periodically even when nothing
    else about an event has changed. Returns the count scored.
    """
    result = await session.execute(
        select(NewsEvent).where(NewsEvent.status == EventStatus.ACTIVE).limit(batch_limit)
    )
    events = list(result.scalars().all())

    for event in events:
        await score_event(session, event)
    await session.flush()

    return len(events)
