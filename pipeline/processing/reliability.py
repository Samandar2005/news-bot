"""Source reliability changes and their downstream effects (spec Phase 3,
stage 8).

`NewsSource.reliability_score` and `is_state_affiliated` are set at seed
time (backend/db/seed_sources.py) and editable later via
`PATCH /api/v1/sources/{id}` (backend/api/v1/sources.py) — that's the
"curated static table, later augmented" part of the spec. This module is
the other documented edge case: **"score changes need re-computation of
affected open events."** `NewsEvent.avg_reliability` is a denormalized
snapshot (see pipeline/processing/clustering.py), so it goes stale the
moment an admin edits a source's score unless something recomputes it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.processing.clustering import refresh_event_aggregates
from shared.models import NewsArticle, NewsEvent


async def recompute_events_for_source(session: AsyncSession, source_id: int) -> int:
    """Refreshes avg_reliability (and source_count/last_updated_at, which
    come along for free from the same recomputation) on every event that
    has at least one article from this source. Returns the number of
    events touched.

    Called from backend/services/sources/service.py whenever an admin
    changes a source's reliability_score — not on every request, so this
    doesn't need to be cheap, just correct.
    """
    result = await session.execute(
        select(NewsArticle.event_id)
        .where(NewsArticle.source_id == source_id, NewsArticle.event_id.is_not(None))
        .distinct()
    )
    event_ids = [row[0] for row in result.all()]

    for event_id in event_ids:
        event = await session.get(NewsEvent, event_id)
        if event is not None:
            await refresh_event_aggregates(session, event)
            # Without this flush, the recomputed value only exists as a
            # pending in-memory attribute change — a later
            # session.refresh() on this event (as callers reasonably do,
            # e.g. right after a PATCH /sources/{id} request) reloads
            # from the database and silently discards it, reverting to
            # the stale pre-recompute number. Caught by
            # tests/integration/test_reliability.py.
            await session.flush()

    return len(event_ids)
