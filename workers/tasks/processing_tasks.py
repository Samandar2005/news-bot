"""Celery task: cluster newly-ingested, not-yet-processed articles.

Same shape as workers/tasks/collection_tasks.py — sync Celery task,
asyncio.run bridge, dispose the engine at the end for the same reason
(pooled asyncpg connections are bound to the event loop they were created
on; the next task run gets its own loop).
"""

from __future__ import annotations

import asyncio
import logging

from backend.db.session import engine, session_scope
from pipeline.processing.clustering import cluster_new_articles
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_clustering() -> dict:
    try:
        async with session_scope() as session:
            stats = await cluster_new_articles(session)

        summary = {
            "articles_processed": stats.processed,
            "new_events_created": stats.new_events,
            "attached_to_existing_events": stats.attached_to_existing,
        }
        logger.info("Clustering cycle complete: %s", summary)
        return summary
    finally:
        await engine.dispose()


@app.task(
    name="workers.tasks.processing_tasks.cluster_new_articles_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def cluster_new_articles_task() -> dict:
    return asyncio.run(_run_clustering())
