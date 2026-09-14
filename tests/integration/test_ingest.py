"""Integration tests for pipeline.collectors.ingest — real (isolated) test
database, real local HTTP server serving fixture feeds, real RssCollector.
No mocks anywhere in this file.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from pipeline.collectors.ingest import collect_all_active_sources, ingest_source
from pipeline.collectors.rss_collector import RssCollector
from shared.enums import SourceType
from shared.models import InterestCategory, NewsArticle, NewsSource

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "rss"


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join()


@pytest_asyncio.fixture
async def good_source(session, fixture_server) -> NewsSource:
    source = NewsSource(
        name="Test BBC Capture",
        url=f"{fixture_server}/good_feed.xml",
        source_type=SourceType.RSS,
        language="en",
    )
    session.add(source)
    await session.flush()
    return source


@pytest.mark.asyncio
async def test_ingest_source_inserts_articles(session, good_source):
    result = await ingest_source(session, good_source, RssCollector())

    assert result.ok
    assert result.fetched == 3
    assert result.inserted == 3
    assert result.skipped_duplicate == 0

    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == good_source.id))
    articles = list(rows.scalars().all())
    assert len(articles) == 3
    assert all(a.content_hash for a in articles)
    # Real BBC content -> genuinely detected as "en" with high confidence,
    # not merely inherited from the source (see test below for a case
    # where detection actually overrides a wrong declared_language).
    assert all(a.language == "en" for a in articles)


@pytest.mark.asyncio
async def test_ingest_source_is_idempotent_on_rerun(session, good_source):
    """Running collection twice against the same feed must not duplicate
    rows — this is the URL/hash dedupe-on-ingest requirement from the M4
    milestone spec."""
    first = await ingest_source(session, good_source, RssCollector())
    second = await ingest_source(session, good_source, RssCollector())

    assert first.inserted == 3
    assert second.inserted == 0
    assert second.skipped_duplicate == 3

    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == good_source.id))
    assert len(list(rows.scalars().all())) == 3


@pytest.mark.asyncio
async def test_ingest_source_updates_last_fetched_at(session, good_source):
    assert good_source.last_fetched_at is None
    await ingest_source(session, good_source, RssCollector())
    assert good_source.last_fetched_at is not None


@pytest.mark.asyncio
async def test_ingest_overrides_wrong_declared_language_when_confident(session, fixture_server):
    """A source configured (perhaps mistakenly, or because it occasionally
    publishes off-language content) as English but actually serving
    Russian text should end up with language="ru" on the article — this
    is the real reason detection exists rather than just trusting
    NewsSource.language outright (see pipeline/processing/language_detector.py).
    """
    source = NewsSource(
        name="Misdeclared Feed",
        url=f"{fixture_server}/misdeclared_language_feed.xml",
        source_type=SourceType.RSS,
        language="en",  # wrong on purpose
    )
    session.add(source)
    await session.flush()

    await ingest_source(session, source, RssCollector())

    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == source.id))
    article = rows.scalar_one()
    assert article.language == "ru"


@pytest.mark.asyncio
async def test_ingest_overrides_wrong_source_default_category_when_confident(
    session, fixture_server
):
    """A source configured with the wrong default category (e.g. a mixed
    feed, or a mistake at seed time) should still land clearly-space
    content under `space`, not under whatever default was configured —
    this is the real reason categorization runs at all rather than just
    trusting NewsSource.default_category_id (see
    pipeline/processing/categorizer.py).
    """
    # NOTE: these must use the categorizer's real output keys ("space",
    # "business") — pipeline.collectors.ingest resolves categorize()'s
    # result by exact key match against the DB, so a prefixed test key
    # like "test_space_correct" would never match and this test would
    # silently prove nothing. Safe here (unlike test_api_interests.py's
    # prefixed categories) because this transaction is rolled back and
    # never touches the real seeded `newsbot` dev database.
    wrong_default = InterestCategory(
        key="business", name_en="Business", name_ru="Бизнес", name_uz="Biznes"
    )
    space_category = InterestCategory(
        key="space", name_en="Space", name_ru="Космос", name_uz="Kosmos"
    )
    session.add_all([wrong_default, space_category])
    await session.flush()

    source = NewsSource(
        name="Miscategorized Source",
        url=f"{fixture_server}/miscategorized_source_feed.xml",
        source_type=SourceType.RSS,
        language="en",
        default_category_id=wrong_default.id,
    )
    session.add(source)
    await session.flush()

    await ingest_source(session, source, RssCollector())

    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == source.id))
    article = rows.scalar_one()
    assert article.category_id == space_category.id


@pytest.mark.asyncio
async def test_ingest_falls_back_to_source_default_when_no_keyword_match(session, fixture_server):
    """The inverse case: content with no confident keyword match should
    use the source's configured default rather than leaving category_id
    unset."""
    default_category = InterestCategory(
        key="test_fallback_default", name_en="World News", name_ru="Мир", name_uz="Dunyo"
    )
    session.add(default_category)
    await session.flush()

    source = NewsSource(
        name="Good Feed With Default",
        url=f"{fixture_server}/good_feed.xml",
        source_type=SourceType.RSS,
        language="en",
        default_category_id=default_category.id,
    )
    session.add(source)
    await session.flush()

    await ingest_source(session, source, RssCollector())

    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == source.id))
    articles = list(rows.scalars().all())
    assert len(articles) == 3
    # real BBC front-page content is broad/mixed — none of it should
    # confidently trip a specific keyword category, so all fall back
    assert all(a.category_id == default_category.id for a in articles)


@pytest.mark.asyncio
async def test_ingest_source_content_is_html_stripped(session, fixture_server):
    source = NewsSource(
        name="Mixed Quality Feed",
        url=f"{fixture_server}/mixed_quality_feed.xml",
        source_type=SourceType.RSS,
        language="en",
    )
    session.add(source)
    await session.flush()

    await ingest_source(session, source, RssCollector())

    rows = await session.execute(
        select(NewsArticle).where(
            NewsArticle.source_id == source.id,
            NewsArticle.url == "http://example.test/articles/1",
        )
    )
    article = rows.scalar_one()
    assert "<b>" not in article.content
    assert "valid" in article.content


@pytest.mark.asyncio
async def test_collect_all_active_sources_isolates_per_source_failure(session, fixture_server):
    good = NewsSource(
        name="Good Feed",
        url=f"{fixture_server}/good_feed.xml",
        source_type=SourceType.RSS,
        language="en",
    )
    broken = NewsSource(
        name="Broken Feed",
        url=f"{fixture_server}/completely_broken.xml",
        source_type=SourceType.RSS,
        language="en",
    )
    inactive = NewsSource(
        name="Inactive Feed",
        url=f"{fixture_server}/good_feed.xml?variant=inactive",
        source_type=SourceType.RSS,
        language="en",
        is_active=False,
    )
    session.add_all([good, broken, inactive])
    await session.flush()

    results = await collect_all_active_sources(session, RssCollector())

    # inactive source should never even be attempted
    assert {r.source_name for r in results} == {"Good Feed", "Broken Feed"}

    good_result = next(r for r in results if r.source_name == "Good Feed")
    broken_result = next(r for r in results if r.source_name == "Broken Feed")

    assert good_result.ok
    assert good_result.inserted == 3
    assert not broken_result.ok
    assert broken_result.error is not None

    # the good source's articles should still be committed-ready despite
    # the other source failing
    rows = await session.execute(select(NewsArticle).where(NewsArticle.source_id == good.id))
    assert len(list(rows.scalars().all())) == 3
