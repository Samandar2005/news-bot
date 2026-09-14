"""RssCollector tests against a real (local) HTTP server.

This sandbox can't reach the public internet (only a small package-registry
allowlist), so these tests serve the fixture feeds in tests/fixtures/rss/
over a local http.server instead of mocking httpx — the actual HTTP fetch,
redirect handling, and feedparser parsing all run for real. One fixture
(good_feed.xml) is a trimmed capture of the real, live BBC News RSS feed
(https://feeds.bbci.co.uk/news/rss.xml, confirmed reachable and valid at
the time this was written) rather than synthetic data, so the "happy path"
test reflects real-world feed shape, not an idealized one.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

import httpx
import pytest

from pipeline.collectors.rss_collector import FeedFetchError, RssCollector

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "rss"


@pytest.fixture(scope="module")
def fixture_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES_DIR)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join()


@pytest.mark.asyncio
async def test_collect_parses_real_bbc_feed_capture(fixture_server):
    collector = RssCollector()
    articles = await collector.collect(f"{fixture_server}/good_feed.xml")

    assert len(articles) == 3
    first = articles[0]
    assert first.title == "Harry and Meghan's return to UK reignites questions over security"
    assert first.url.startswith("https://www.bbc.co.uk/news/articles/")
    assert first.published_at is not None
    assert first.published_at.year == 2026


@pytest.mark.asyncio
async def test_collect_empty_feed_returns_empty_list(fixture_server):
    collector = RssCollector()
    articles = await collector.collect(f"{fixture_server}/empty_feed.xml")
    assert articles == []


@pytest.mark.asyncio
async def test_collect_skips_entries_missing_title_or_link(fixture_server):
    collector = RssCollector()
    articles = await collector.collect(f"{fixture_server}/mixed_quality_feed.xml")

    # 4 entries in the fixture, 2 are missing a required field -> only 2 survive
    assert len(articles) == 2
    urls = {a.url for a in articles}
    assert urls == {"http://example.test/articles/1", "http://example.test/articles/4"}


@pytest.mark.asyncio
async def test_collect_strips_html_is_not_done_here_yet(fixture_server):
    """RssCollector hands back raw content — HTML stripping happens in the
    ingestion step (pipeline/processing/normalizer.py), not the collector."""
    collector = RssCollector()
    articles = await collector.collect(f"{fixture_server}/mixed_quality_feed.xml")
    entry_one = next(a for a in articles if a.url == "http://example.test/articles/1")
    assert "<b>" in entry_one.content


@pytest.mark.asyncio
async def test_collect_entry_without_date_gets_none(fixture_server):
    collector = RssCollector()
    articles = await collector.collect(f"{fixture_server}/mixed_quality_feed.xml")
    entry_four = next(a for a in articles if a.url == "http://example.test/articles/4")
    assert entry_four.published_at is None


@pytest.mark.asyncio
async def test_collect_completely_broken_feed_raises(fixture_server):
    collector = RssCollector()
    with pytest.raises(FeedFetchError):
        await collector.collect(f"{fixture_server}/completely_broken.xml")


@pytest.mark.asyncio
async def test_collect_404_raises_feed_fetch_error(fixture_server):
    collector = RssCollector()
    with pytest.raises(FeedFetchError):
        await collector.collect(f"{fixture_server}/does_not_exist.xml")


@pytest.mark.asyncio
async def test_collect_unreachable_host_raises_feed_fetch_error():
    collector = RssCollector(timeout=1.0)
    with pytest.raises(FeedFetchError):
        await collector.collect("http://127.0.0.1:1/nothing-is-listening-here.xml")


@pytest.mark.asyncio
async def test_fetch_retries_on_transport_error(monkeypatch, fixture_server):
    """Confirms the tenacity retry decorator is actually wired up: force
    two transport failures, then let the third attempt succeed."""
    collector = RssCollector()
    attempts = {"count": 0}
    real_get = httpx.AsyncClient.get

    async def flaky_get(self, url, *args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("simulated transient failure")
        return await real_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "get", flaky_get)
    articles = await collector.collect(f"{fixture_server}/good_feed.xml")

    assert attempts["count"] == 3
    assert len(articles) == 3
