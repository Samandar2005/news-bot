"""Celery task: recompute importance_score for all active events.

Same shape as collection_tasks.py / processing_tasks.py. Runs on its own
schedule, independent of collection/clustering activity — see
pipeline/scoring/importance.py's module docstring for why freshness decay
means this needs to keep running even when nothing new has come in.
"""

from __future__ import annotations

import asyncio
import logging

from backend.db.session import engine, session_scope
from pipeline.scoring.importance import score_all_active_events
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_scoring() -> dict:
    try:
        async with session_scope() as session:
            scored_count = await score_all_active_events(session)

        summary = {"events_scored": scored_count}
        logger.info("Importance scoring cycle complete: %s", summary)
        return summary
    finally:
        await engine.dispose()


@app.task(
    name="workers.tasks.scoring_tasks.score_active_events_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def score_active_events_task() -> dict:
    return asyncio.run(_run_scoring())
