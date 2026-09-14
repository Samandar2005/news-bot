"""Seed data for news_sources (spec Phase 3 / M4 milestone).

Run with: python -m backend.db.seed_sources

Confidence levels, stated plainly rather than glossed over:
- VERIFIED = fetched live and confirmed returning valid RSS during
  development of this seed list.
- PATTERN = not fetched this session, but follows a long-stable, widely
  documented URL structure from the same already-verified domain (e.g.
  BBC's per-category feeds share feeds.bbci.co.uk/news/<category>/rss.xml
  with the verified root feed).
- UNVERIFIED = a reasonable, well-known candidate that was not fetched
  live this session.
Any source can go stale — that's why `is_active` and `last_fetched_at`
exist. Treat a source that starts failing consistently as a signal to
find a replacement, not a bug in the collector.

The Uzbek-language source below is a confirmed Latin Uzbek RSS endpoint;
source availability is still monitored by the collector at runtime.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import session_scope
from shared.enums import SourceType
from shared.models import InterestCategory, NewsSource

# name, url, source_type, language, category_key, reliability_score, confidence note (comment only)
SOURCES: list[tuple[str, str, SourceType, str, str, float]] = [
    # --- English — VERIFIED live this session ---
    ("BBC News", "http://feeds.bbci.co.uk/news/rss.xml", SourceType.RSS, "en", "world_news", 0.85),
    # --- English — PATTERN (same domain/structure as the verified BBC root feed) ---
    (
        "BBC Politics",
        "http://feeds.bbci.co.uk/news/politics/rss.xml",
        SourceType.RSS,
        "en",
        "politics",
        0.75,
    ),
    (
        "BBC Business",
        "http://feeds.bbci.co.uk/news/business/rss.xml",
        SourceType.RSS,
        "en",
        "business",
        0.75,
    ),
    # --- English — UNVERIFIED (well-known, long-stable feeds) ---
    (
        "The Verge",
        "https://www.theverge.com/rss/index.xml",
        SourceType.RSS,
        "en",
        "technology",
        0.65,
    ),
    ("Hacker News", "https://hnrss.org/frontpage", SourceType.RSS, "en", "programming", 0.55),
    (
        "Python Insider",
        "https://blog.python.org/feeds/posts/default",
        SourceType.RSS,
        "en",
        "python",
        0.9,
    ),
    (
        "TechCrunch AI",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        SourceType.RSS,
        "en",
        "artificial_intelligence",
        0.6,
    ),
    (
        "Krebs on Security",
        "https://krebsonsecurity.com/feed/",
        SourceType.RSS,
        "en",
        "cybersecurity",
        0.8,
    ),
    (
        "ScienceDaily",
        "https://www.sciencedaily.com/rss/all.xml",
        SourceType.RSS,
        "en",
        "science",
        0.7,
    ),
    (
        "Yahoo Finance",
        "https://finance.yahoo.com/news/rssindex",
        SourceType.RSS,
        "en",
        "finance",
        0.6,
    ),
    (
        "USGS Significant Earthquakes",
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.atom",
        SourceType.RSS,
        "en",
        "natural_disasters",
        0.9,
    ),
    ("NASA", "https://www.nasa.gov/news-release/feed/", SourceType.RSS, "en", "space", 0.85),
    (
        "TechCrunch Startups",
        "https://techcrunch.com/category/startups/feed/",
        SourceType.RSS,
        "en",
        "startups",
        0.6,
    ),
    (
        "Stack Overflow Blog",
        "https://stackoverflow.blog/feed/",
        SourceType.RSS,
        "en",
        "software_development",
        0.65,
    ),
    # --- Russian — VERIFIED live this session ---
    ("NUZ.UZ", "https://nuz.uz/feed", SourceType.RSS, "ru", "world_news", 0.55),
    (
        "Gazeta.uz O'zbekcha",
        "https://www.gazeta.uz/oz/rss/",
        SourceType.RSS,
        "uz",
        "world_news",
        0.65,
    ),
    # --- Russian — UNVERIFIED, state-affiliated (spec Phase 3 stage 8: flag, don't exclude) ---
    ("TASS", "https://tass.ru/rss/v2.xml", SourceType.RSS, "ru", "politics", 0.45),
]

# Sources whose is_state_affiliated flag should be True — kept as a
# separate lookup rather than a 7th tuple field on every row above, since
# only one source currently needs it and a positional 7-tuple would be
# easy to transcribe wrong across 16 entries for a flag that's False on
# all but one of them.
STATE_AFFILIATED_SOURCE_NAMES = {"TASS"}


async def seed_sources(session: AsyncSession) -> None:
    result = await session.execute(select(InterestCategory))
    categories_by_key = {c.key: c for c in result.scalars().all()}

    required_keys = {category_key for _, _, _, _, category_key, _ in SOURCES}
    missing_keys = required_keys - set(categories_by_key)
    if missing_keys:
        raise RuntimeError(
            f"Categories {sorted(missing_keys)} not found — run "
            "`python -m backend.db.seed` first to seed categories."
        )

    result = await session.execute(select(NewsSource))
    existing = {s.url: s for s in result.scalars().all()}

    created, updated = 0, 0
    for name, url, source_type, language, category_key, reliability in SOURCES:
        category = categories_by_key[category_key]
        state_affiliated = name in STATE_AFFILIATED_SOURCE_NAMES
        if url in existing:
            source = existing[url]
            source.name = name
            source.source_type = source_type
            source.language = language
            source.default_category_id = category.id
            source.reliability_score = reliability
            source.is_state_affiliated = state_affiliated
            updated += 1
        else:
            session.add(
                NewsSource(
                    name=name,
                    url=url,
                    source_type=source_type,
                    language=language,
                    default_category_id=category.id,
                    reliability_score=reliability,
                    is_state_affiliated=state_affiliated,
                )
            )
            created += 1

    print(f"Sources: {created} created, {updated} updated.")


async def main() -> None:
    async with session_scope() as session:
        await seed_sources(session)


if __name__ == "__main__":
    asyncio.run(main())
