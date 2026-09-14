"""Collector interface.

One subclass per source_type (spec Phase 3, stage 1). Only RSS is
implemented for the MVP (spec Phase 1.4) — `NewsSource.source_type` is
already a real column for `api`/`web`, so adding collectors later doesn't
need a schema change, just a new class here and a dispatch entry in
workers/tasks/collection_tasks.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RawArticle:
    """What a collector hands back for one item — pre-normalization,
    pre-hashing. `pipeline/processing/normalizer.py` (M5) takes it from here.
    """

    url: str
    title: str
    content: str
    published_at: datetime | None


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, source_url: str) -> list[RawArticle]:
        """Fetch and parse everything currently available from one source.

        Must not raise on a single bad item within an otherwise-good feed —
        skip it and keep going (spec Phase 3, stage 1 edge cases: malformed
        entries alongside good ones are common in the wild). Raising is
        reserved for the whole source being unreachable/unparseable, which
        the caller (pipeline/collectors/rss_collector.py's caller) is
        expected to catch per-source so one bad feed doesn't stop the
        others in the same collection cycle.
        """
        raise NotImplementedError
