"""Celery Beat periodic schedule — kept separate from celery_app.py so the
*what runs when* list stays easy to scan as more tasks (processing,
scoring, digest dispatch) land in later milestones.
"""

from __future__ import annotations

from celery.schedules import crontab

BEAT_SCHEDULE = {
    "collect-all-sources-every-15-minutes": {
        "task": "workers.tasks.collection_tasks.collect_all_sources_task",
        "schedule": 15 * 60,
    },
    "cluster-new-articles-every-15-minutes": {
        "task": "workers.tasks.processing_tasks.cluster_new_articles_task",
        "schedule": 15 * 60,
        # Runs on the same cadence as collection but offset so a batch of
        # freshly-collected articles has landed before clustering looks
        # for is_processed=False rows — otherwise the two tasks would fire
        # in the same instant with no guaranteed ordering between them.
        "options": {"countdown": 5 * 60},
    },
    "score-active-events-every-15-minutes": {
        "task": "workers.tasks.scoring_tasks.score_active_events_task",
        "schedule": 15 * 60,
        # A further 5 minutes after clustering, so newly-clustered events
        # have source_count/avg_reliability set before scoring reads
        # them. Also re-scores every still-active event on every cycle
        # regardless of whether clustering touched it — freshness decays
        # continuously (see pipeline/scoring/importance.py).
        "options": {"countdown": 10 * 60},
    },
    "summarize-top-events-every-15-minutes": {
        "task": "workers.tasks.summarization_tasks.summarize_top_events_task",
        "schedule": 15 * 60,
        # After scoring, so importance_score reflects this cycle's data
        # before the importance-threshold gate (spec Phase 5.2) decides
        # what's worth an LLM call. Aggressive caching in summarizer.py
        # means re-running this often costs nothing extra for events
        # already summarized — it only spends on genuinely new,
        # high-importance events.
        "options": {"countdown": 12 * 60},
    },
    "dispatch-morning-digest": {
        "task": "workers.tasks.digest_tasks.dispatch_morning_digest_task",
        # Fixed local time, not an interval (spec Phase 1 item 16) — this
        # only means 07:00 *Asia/Tashkent* because celery_app.py sets the
        # whole app's timezone to settings.default_timezone; a crontab
        # here alone, with the default UTC app timezone, would fire at
        # the wrong wall-clock time for the product's actual users.
        "schedule": crontab(hour=7, minute=0),
    },
    "dispatch-evening-digest": {
        "task": "workers.tasks.digest_tasks.dispatch_evening_digest_task",
        "schedule": crontab(hour=19, minute=0),
    },
}
