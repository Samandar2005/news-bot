"""Celery task: summarize top-importance active events.

Same shape as the other pipeline tasks. The provider is instantiated
fresh per task run (cheap — it's just an HTTP client wrapper) rather than
module-level, so a bad GOOGLE_API_KEY doesn't prevent the whole worker
process from starting — it just makes this specific task's runs fail
(and log why) until fixed.
"""

from __future__ import annotations

import asyncio
import logging

from backend.db.session import engine, session_scope
from pipeline.ai.google_provider import GoogleSummarizationProvider
from pipeline.ai.summarizer import summarize_top_events
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_summarization() -> dict:
    try:
        provider = GoogleSummarizationProvider()
        async with session_scope() as session:
            stats = await summarize_top_events(session, provider)

        summary = {
            "events_considered": stats.events_considered,
            "summaries_created": stats.summaries_created,
            "summaries_already_cached": stats.summaries_already_cached,
        }
        logger.info("Summarization cycle complete: %s", summary)
        return summary
    finally:
        await engine.dispose()


@app.task(
    name="workers.tasks.summarization_tasks.summarize_top_events_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def summarize_top_events_task() -> dict:
    return asyncio.run(_run_summarization())
