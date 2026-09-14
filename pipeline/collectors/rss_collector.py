"""RSS/Atom collector (spec Phase 3, stage 1 + Phase 5 pipeline entry point).

feedparser is synchronous; fetching is done with httpx (async, retried) and
parsing happens on the already-downloaded bytes, which is fast enough not
to need offloading to a thread for the MVP's feed sizes. Revisit with
`asyncio.to_thread(feedparser.parse, ...)` if a very large feed ever blocks
the event loop noticeably.
"""

from __future__ import annotations

import logging
from calendar import timegm
from datetime import UTC, datetime

import feedparser
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pipeline.collectors.base import BaseCollector, RawArticle

logger = logging.getLogger(__name__)

_USER_AGENT = "NewsBot/0.1 (+https://github.com/; RSS collector)"


class FeedFetchError(RuntimeError):
    """Raised when a feed can't be fetched or contains no usable entries
    at all — a single bad *entry* within an otherwise-good feed is not an
    error (see RssCollector.collect), only a wholly unusable feed is.
    """


class RssCollector(BaseCollector):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch(self, source_url: str) -> bytes:
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
        ) as client:
            response = await client.get(source_url)
            response.raise_for_status()
            return response.content

    async def collect(self, source_url: str) -> list[RawArticle]:
        try:
            raw_bytes = await self._fetch(source_url)
        except httpx.HTTPStatusError as exc:
            raise FeedFetchError(
                f"{source_url}: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.TransportError as exc:
            raise FeedFetchError(f"{source_url}: transport error: {exc}") from exc

        parsed = feedparser.parse(raw_bytes)

        # feedparser is deliberately lenient — `bozo` just means *something*
        # was off (a stray namespace, a bad date). It still does its best to
        # extract entries. Only treat it as a real failure if that left us
        # with nothing at all.
        if parsed.bozo and not parsed.entries:
            raise FeedFetchError(
                f"{source_url}: unparseable feed ({parsed.get('bozo_exception')})"
            )
        if parsed.bozo:
            logger.warning(
                "Feed %s parsed with warnings (%s), continuing with %d entries",
                source_url,
                parsed.get("bozo_exception"),
                len(parsed.entries),
            )

        articles: list[RawArticle] = []
        for entry in parsed.entries:
            article = self._entry_to_article(entry, source_url)
            if article is not None:
                articles.append(article)
        return articles

    @staticmethod
    def _entry_to_article(entry: feedparser.FeedParserDict, source_url: str) -> RawArticle | None:
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            # Missing the two fields we can't do anything without — skip
            # this one entry rather than failing the whole feed (spec
            # Phase 3, stage 1 edge cases).
            logger.warning("Skipping entry with no url/title from %s", source_url)
            return None

        content = RssCollector._extract_content(entry)
        published_at = RssCollector._extract_published_at(entry)

        return RawArticle(url=url, title=title.strip(), content=content, published_at=published_at)

    @staticmethod
    def _extract_content(entry: feedparser.FeedParserDict) -> str:
        # Prefer full Atom <content>, fall back to RSS <description>/summary.
        # Actual HTML stripping/boilerplate removal happens in normalization
        # (M5) — this layer's job is just "get the best text we were given."
        if entry.get("content"):
            return entry["content"][0].get("value", "") or ""
        return entry.get("summary", "") or ""

    @staticmethod
    def _extract_published_at(entry: feedparser.FeedParserDict) -> datetime | None:
        for field in ("published_parsed", "updated_parsed"):
            time_struct = entry.get(field)
            if time_struct is not None:
                return datetime.fromtimestamp(timegm(time_struct), tz=UTC)
        return None
