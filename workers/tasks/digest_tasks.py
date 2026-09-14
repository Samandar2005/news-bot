"""Celery tasks: dispatch morning and evening digests (spec Phase 1 item
16: 07:00 and 19:00 local time — see workers/beat_schedule.py's crontab
entries and workers/celery_app.py's timezone setting, which together
make those times actually mean Asia/Tashkent, not UTC).

A fresh aiogram Bot is created per task run, used only for outbound
send_message calls (no polling/dispatcher here — that's bot/main.py's
job, a completely separate process) and closed at the end, matching the
same "create fresh, dispose at the end" pattern as the DB engine in every
other task module.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from backend.db.session import engine, session_scope
from pipeline.digest.dispatch import dispatch_digests
from shared.config import settings
from shared.enums import DigestType
from workers.celery_app import app

logger = logging.getLogger(__name__)


async def _run_dispatch(digest_type: DigestType) -> dict:
    bot = Bot(token=settings.telegram_bot_token)
    try:
        async with session_scope() as session:
            stats = await dispatch_digests(session, bot, digest_type)

        summary = {
            "digest_type": digest_type.value,
            "users_considered": stats.users_considered,
            "sent": stats.sent,
            "skipped_no_content": stats.skipped_no_content,
            "failed": stats.failed,
        }
        logger.info("Digest dispatch complete: %s", summary)
        return summary
    finally:
        await bot.session.close()
        await engine.dispose()


@app.task(
    name="workers.tasks.digest_tasks.dispatch_morning_digest_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_morning_digest_task() -> dict:
    return asyncio.run(_run_dispatch(DigestType.MORNING))


@app.task(
    name="workers.tasks.digest_tasks.dispatch_evening_digest_task",
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 4},
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_evening_digest_task() -> dict:
    return asyncio.run(_run_dispatch(DigestType.EVENING))
