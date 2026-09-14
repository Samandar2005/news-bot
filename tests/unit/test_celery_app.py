"""Regression tests for two real bugs found and fixed while building M12:

1. A task module referenced by name in workers/beat_schedule.py but never
   imported into the worker process (via celery_app.py's `include` list)
   is silently unreachable — Celery raises "Received unregistered task"
   at dispatch time, not at import time, so nothing catches this without
   an explicit test. Every task added since M7 (clustering, scoring,
   summarization) had exactly this bug until it was found and fixed here.

2. crontab's `.tz` is a cached_property resolved from `.app.timezone`,
   and `.app` falls back to Celery's *default* app (UTC) unless
   explicitly bound. The crontab(...) calls in beat_schedule.py run at
   import time, before the real `news_bot` app (with its Asia/Tashkent
   timezone) exists — so without the explicit binding added at the
   bottom of celery_app.py, the digest crontabs would silently fire at
   07:00/19:00 UTC (12:00/00:00 Tashkent) instead of local time.
"""

from __future__ import annotations

from celery.schedules import crontab

from workers.beat_schedule import BEAT_SCHEDULE
from workers.celery_app import app


def test_every_scheduled_task_is_actually_registered():
    """Simulates real `celery worker` startup (which processes the
    `include` list) and checks every task name referenced in
    BEAT_SCHEDULE is genuinely registered — not just that the modules
    happen to import without error.
    """
    app.loader.import_default_modules()
    registered = set(app.tasks.keys())

    scheduled_task_names = {entry["task"] for entry in BEAT_SCHEDULE.values()}
    missing = scheduled_task_names - registered

    assert not missing, (
        f"Task(s) referenced in beat_schedule.py but not registered "
        f"with the app (missing from celery_app.py's `include` list): {missing}"
    )


def test_every_crontab_entry_resolves_to_the_configured_timezone():
    """Every fixed-local-time schedule entry (currently: the two digest
    dispatch times) must resolve to the product's actual configured
    timezone, not silently fall back to UTC.
    """
    crontab_entries = {
        name: entry["schedule"]
        for name, entry in BEAT_SCHEDULE.items()
        if isinstance(entry["schedule"], crontab)
    }
    assert crontab_entries, "expected at least the two digest crontab entries"

    for name, sched in crontab_entries.items():
        assert str(sched.tz) == app.conf.timezone, (
            f"{name}'s crontab resolved to tz={sched.tz!r}, "
            f"expected {app.conf.timezone!r} (app.conf.timezone)"
        )


def test_digest_crontabs_fire_at_the_intended_local_hour():
    """Belt-and-suspenders on top of the tz check: confirms the actual
    hour/minute fields are what the product spec calls for (07:00 and
    19:00, spec Phase 1 item 16), so a typo in beat_schedule.py's
    crontab(hour=..., minute=...) call doesn't slip through even with a
    correct timezone.
    """
    morning = BEAT_SCHEDULE["dispatch-morning-digest"]["schedule"]
    evening = BEAT_SCHEDULE["dispatch-evening-digest"]["schedule"]

    assert morning.hour == {7}
    assert morning.minute == {0}
    assert evening.hour == {19}
    assert evening.minute == {0}
