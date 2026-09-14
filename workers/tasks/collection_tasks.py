"""Celery task: run RSS collection for every active source.

Celery tasks are sync; the actual work is async (httpx + asyncpg), so this
is a thin `asyncio.run` bridge around `pipeline.collectors.ingest`, which
is the same function called directly from tests — the task adds
scheduling/retry/logging, not logic.
"""

from __future__ import annotations

import asyncio
import logging

from backend.db.session import engine, session_scope
from pipeline.collectors.ingest import collect_all_active_sources
from pipeline.collectors.rss_collector import RssCollector
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_collection() -> dict:
    try:
        async with session_scope() as session:
            results = await collect_all_active_sources(session, RssCollector())

        succeeded = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]

        for r in failed:
            logger.warning("Collection failed for source %r: %s", r.source_name, r.error)

        summary = {
            "sources_attempted": len(results),
            "sources_ok": len(succeeded),
            "sources_failed": len(failed),
            "articles_inserted": sum(r.inserted for r in succeeded),
            "articles_skipped_duplicate": sum(r.skipped_duplicate for r in succeeded),
        }
        logger.info("Collection cycle complete: %s", summary)
        return summary
    finally:
        # Each Celery task run gets a fresh event loop via asyncio.run()
        # below. Pooled asyncpg connections are bound to the loop they were
        # created on, so leaving them open here would break (or silently
        # misbehave on) the *next* task run's loop. Disposing at the end of
        # every run trades a bit of connection-setup overhead per task for
        # correctness — cheap compared to a wedged worker.
        await engine.dispose()


@app.task(
    name="workers.tasks.collection_tasks.collect_all_sources_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def collect_all_sources_task() -> dict:
    return asyncio.run(_run_collection())
