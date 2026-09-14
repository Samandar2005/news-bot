"""Deduplication and event clustering (spec Phase 3, stages 6-7).

Two signals, checked in order:
1. **Exact content-hash match** — the cheap, reliable pre-filter (spec
   stage 6). Catches byte-identical reposts and wire-service syndication
   across different sources regardless of embedding quality.
2. **Embedding cosine similarity** (pgvector's `<=>` operator, via
   `NewsArticle.embedding.cosine_distance`) — only checked if the hash
   didn't already find a match. See pipeline/ai/embeddings.py for what
   the embedding actually is (a lexical placeholder, not semantic) and
   why SIMILARITY_THRESHOLD below is set conservatively.

**Why the threshold is set where it is, with real numbers, not a guess:**
measured empirically against realistic same-event/different-event text
pairs during development:
  - same event, heavily reworded repost:   ~0.68 cosine similarity
  - same event, different outlet framing:  ~0.16
  - same event, very different wording:    ~0.17
  - related but genuinely different event: ~0.11
  - unrelated:                             ~0.06

There's no threshold that separates "different framing of the same
event" (~0.16) from "related but different event" (~0.11) — those
overlap. SIMILARITY_THRESHOLD is set at 0.35, well above both, which
means this deliberately **under-clusters** (misses some same-event
articles that are worded very differently) rather than **over-clusters**
(never merges two actually-different events together). Given the
product's core promise of cross-source verification, a false "these are
different events" is a lost corroborating source; a false "these are the
same event" is misinformation. The conservative failure mode is the
correct one for MVP. Real semantic embeddings are what closes this gap
later, not further threshold-tuning of a lexical vector.

**Event clustering strategy**: greedy single-linkage — a new article
joins the existing open event containing the single closest already-
clustered article (by category + time window), if that distance clears
the bar; otherwise it starts a new event. Simple, and correct for the
batch sizes this system deals with; a similarity index/ANN tuning pass is
a scaling concern for later (spec Phase 1.6), not an MVP one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import EventStatus
from shared.models import NewsArticle, NewsEvent, NewsSource

TIME_WINDOW = timedelta(hours=72)
SIMILARITY_THRESHOLD = 0.35  # cosine similarity; see module docstring


@dataclass(frozen=True, slots=True)
class ClusterAssignment:
    event: NewsEvent
    created_new_event: bool


@dataclass(frozen=True, slots=True)
class ClusteringStats:
    processed: int
    new_events: int
    attached_to_existing: int


async def _find_event_by_exact_hash(
    session: AsyncSession, article: NewsArticle, window_start, window_end
) -> int | None:
    result = await session.execute(
        select(NewsArticle.event_id)
        .where(
            NewsArticle.content_hash == article.content_hash,
            NewsArticle.id != article.id,
            NewsArticle.event_id.is_not(None),
            NewsArticle.published_at >= window_start,
            NewsArticle.published_at <= window_end,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _find_event_by_embedding(
    session: AsyncSession, article: NewsArticle, window_start, window_end
) -> int | None:
    if not article.embedding or not any(article.embedding):
        # Zero vector (e.g. empty-content article) carries no similarity
        # signal — pgvector's cosine_distance against an all-zero vector
        # is mathematically undefined (division by zero magnitude), so
        # don't even ask.
        return None

    category_filter = (
        NewsArticle.category_id.is_(None)
        if article.category_id is None
        else NewsArticle.category_id == article.category_id
    )
    distance_col = NewsArticle.embedding.cosine_distance(article.embedding).label("distance")
    result = await session.execute(
        select(NewsArticle.event_id, func.min(distance_col).label("best_distance"))
        .where(
            NewsArticle.event_id.is_not(None),
            NewsArticle.id != article.id,
            category_filter,
            NewsArticle.published_at >= window_start,
            NewsArticle.published_at <= window_end,
        )
        .group_by(NewsArticle.event_id)
        .order_by("best_distance")
        .limit(1)
    )
    row = result.first()
    if row is None or row.best_distance is None:
        return None
    # pgvector's cosine_distance is 1 - cosine_similarity.
    if row.best_distance <= (1 - SIMILARITY_THRESHOLD):
        return row.event_id
    return None


async def refresh_event_aggregates(session: AsyncSession, event: NewsEvent) -> None:
    """Recomputes source_count/avg_reliability/last_updated_at from the
    event's currently-linked articles.

    Public (not module-private) because it has two callers: this module,
    right after linking a new article, and
    pipeline/processing/reliability.py, when a source's reliability_score
    changes and every event that source contributed to needs
    recalculating (spec Phase 3 stage 8's edge case: "score changes need
    re-computation of affected open events").
    """
    result = await session.execute(
        select(NewsArticle.source_id, NewsArticle.published_at).where(
            NewsArticle.event_id == event.id
        )
    )
    rows = result.all()
    if not rows:
        return

    source_ids = {r.source_id for r in rows}
    reliability_result = await session.execute(
        select(func.avg(NewsSource.reliability_score)).where(NewsSource.id.in_(source_ids))
    )
    avg_reliability = reliability_result.scalar()

    event.source_count = len(source_ids)
    event.avg_reliability = float(avg_reliability) if avg_reliability is not None else 0.0
    event.last_updated_at = max(r.published_at for r in rows)


async def cluster_article(session: AsyncSession, article: NewsArticle) -> ClusterAssignment:
    """Assigns one already-ingested, already-categorized article to an
    event — an existing one if it clears the similarity bar, otherwise a
    newly created one. Idempotent to call again on an already-processed
    article (it will simply re-confirm/re-cluster), but callers should
    prefer `cluster_new_articles` for normal operation.
    """
    window_start = article.published_at - TIME_WINDOW
    window_end = article.published_at + TIME_WINDOW

    matched_event_id = await _find_event_by_exact_hash(session, article, window_start, window_end)
    if matched_event_id is None:
        matched_event_id = await _find_event_by_embedding(
            session, article, window_start, window_end
        )

    created_new_event = matched_event_id is None
    if matched_event_id is not None:
        event = await session.get(NewsEvent, matched_event_id)
    else:
        event = NewsEvent(
            category_id=article.category_id,
            first_seen_at=article.published_at,
            last_updated_at=article.published_at,
            status=EventStatus.ACTIVE,
        )
        session.add(event)
        await session.flush()

    article.event_id = event.id
    article.is_processed = True
    await session.flush()

    await refresh_event_aggregates(session, event)
    await session.flush()

    return ClusterAssignment(event=event, created_new_event=created_new_event)


async def cluster_new_articles(session: AsyncSession, batch_limit: int = 200) -> ClusteringStats:
    """Processes up to `batch_limit` not-yet-clustered articles, oldest
    first — chronological order matters here: an early article can
    become the seed a later, differently-worded article about the same
    event successfully matches against.
    """
    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.is_processed.is_(False))
        .order_by(NewsArticle.published_at.asc())
        .limit(batch_limit)
    )
    articles = list(result.scalars().all())

    new_events = 0
    attached_to_existing = 0
    for article in articles:
        assignment = await cluster_article(session, article)
        if assignment.created_new_event:
            new_events += 1
        else:
            attached_to_existing += 1

    return ClusteringStats(
        processed=len(articles), new_events=new_events, attached_to_existing=attached_to_existing
    )
