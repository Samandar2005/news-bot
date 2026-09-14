"""Celery app. Run a worker with:
    celery -A workers.celery_app worker --loglevel=INFO
Run beat (scheduler) with:
    celery -A workers.celery_app beat --loglevel=INFO
Or both in one process (fine for the single-worker MVP; split them once
there's more than one worker replica):
    celery -A workers.celery_app worker --beat --loglevel=INFO
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from shared.config import settings
from workers.beat_schedule import BEAT_SCHEDULE

app = Celery(
    "news_bot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Every module defining an @app.task must be listed here — a task
    # referenced in beat_schedule.py by name string but never imported
    # into the worker process is silently unreachable (Celery raises
    # "Received unregistered task" at dispatch time, not at startup).
    # Caught via tests/unit/test_celery_app.py, which simulates real
    # worker startup and asserts every beat-scheduled task name actually
    # registers — add new task modules to both this list and that test.
    include=[
        "workers.tasks.collection_tasks",
        "workers.tasks.processing_tasks",
        "workers.tasks.scoring_tasks",
        "workers.tasks.summarization_tasks",
        "workers.tasks.digest_tasks",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Digest dispatch is scheduled at fixed local times (07:00/19:00,
    # spec Phase 1 item 16) — the crontab entries in beat_schedule.py
    # mean nothing without this matching the product's actual target
    # timezone. Everything else in this app already runs on a plain
    # interval, so this only visibly matters for digest_tasks.py, but it
    # must be set on the app as a whole.
    timezone=settings.default_timezone,
    enable_utc=True,
    # Collection tasks do their own per-source error handling and are safe
    # to retry as a whole; a hard time limit stops one wedged HTTP call
    # from blocking a worker slot indefinitely.
    task_time_limit=300,
    task_soft_time_limit=240,
)

app.conf.beat_schedule = BEAT_SCHEDULE

# crontab's `.tz` is a cached_property resolved from `.app.timezone`, and
# `.app` falls back to Celery's *default* app (UTC) unless explicitly
# bound — which the crontab(...) calls in beat_schedule.py can't do
# themselves, since they run at import time, before this `app` object
# (with its Asia/Tashkent timezone) exists yet. Bind it explicitly here,
# before Beat's scheduler ever accesses `.tz` and caches the wrong value
# permanently. Verified directly (not assumed) via
# tests/unit/test_celery_app.py, which checks the resolved tz on every
# crontab-scheduled entry.
for _entry in BEAT_SCHEDULE.values():
    if isinstance(_entry["schedule"], crontab):
        _entry["schedule"].app = app
