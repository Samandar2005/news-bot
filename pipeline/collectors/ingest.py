"""Turns a collector's output into `news_articles` rows.

Two levels here on purpose:
- `ingest_source` — one source. Lets a real fetch/parse error
  (FeedFetchError) propagate, since the caller needs to know a specific
  source failed.
- `collect_all_active_sources` — every active source. Catches each
  source's error individually (spec Phase 1.6: "respect per-source error
  isolation") so one dead feed doesn't stop the rest of the collection
  cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.ai.embeddings import compute_embedding
from pipeline.collectors.base import BaseCollector
from pipeline.collectors.rss_collector import FeedFetchError
from pipeline.processing.categorizer import categorize
from pipeline.processing.clickbait import score_clickbait
from pipeline.processing.language_detector import detect_language
from pipeline.processing.normalizer import compute_content_hash, strip_html_lightly
from shared.enums import SourceType
from shared.models import InterestCategory, NewsArticle, NewsSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceIngestResult:
    source_id: int
    source_name: str
    fetched: int
    inserted: int
    skipped_duplicate: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


async def ingest_source(
    session: AsyncSession, source: NewsSource, collector: BaseCollector
) -> SourceIngestResult:
    raw_articles = await collector.collect(source.url)

    # Fetched once per source (not per article) — a handful of rows, no
    # reason to repeat this query for every article in the feed.
    category_result = await session.execute(select(InterestCategory))
    category_id_by_key = {c.key: c.id for c in category_result.scalars().all()}

    inserted = 0
    skipped_duplicate = 0
    for raw in raw_articles:
        existing = await session.execute(
            select(NewsArticle.id).where(
                NewsArticle.source_id == source.id, NewsArticle.url == raw.url
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped_duplicate += 1
            continue

        content = strip_html_lightly(raw.content)
        now = datetime.now(UTC)
        detected_language = detect_language(
            f"{raw.title} {content}", declared_language=source.language
        )
        final_language = detected_language or source.language

        matched_key = categorize(raw.title, content, final_language)
        category_id = category_id_by_key.get(matched_key) or source.default_category_id

        session.add(
            NewsArticle(
                source_id=source.id,
                url=raw.url,
                title=raw.title,
                content=content,
                content_hash=compute_content_hash(raw.title, content),
                embedding=compute_embedding(f"{raw.title} {content}"),
                language=final_language,
                category_id=category_id,
                clickbait_score=score_clickbait(raw.title),
                published_at=raw.published_at or now,
                fetched_at=now,
            )
        )
        inserted += 1

    source.last_fetched_at = datetime.now(UTC)
    await session.flush()

    return SourceIngestResult(
        source_id=source.id,
        source_name=source.name,
        fetched=len(raw_articles),
        inserted=inserted,
        skipped_duplicate=skipped_duplicate,
    )


async def collect_all_active_sources(
    session: AsyncSession, collector: BaseCollector, source_type: SourceType = SourceType.RSS
) -> list[SourceIngestResult]:
    """Runs `collector` against every active source of `source_type`.

    Only RSS exists for the MVP, so this always means "every active RSS
    source" in practice today — the `source_type` filter is here so that
    adding an API or web collector later (spec Phase 1.5) is a matter of
    calling this again with a different collector/type, not a rewrite.
    """
    result = await session.execute(
        select(NewsSource).where(
            NewsSource.is_active.is_(True), NewsSource.source_type == source_type
        )
    )
    sources = list(result.scalars().all())

    results: list[SourceIngestResult] = []
    for source in sources:
        try:
            results.append(await ingest_source(session, source, collector))
        except FeedFetchError as exc:
            logger.warning("Collection failed for source %s: %s", source.name, exc)
            results.append(
                SourceIngestResult(
                    source_id=source.id,
                    source_name=source.name,
                    fetched=0,
                    inserted=0,
                    skipped_duplicate=0,
                    error=str(exc),
                )
            )
    return results
