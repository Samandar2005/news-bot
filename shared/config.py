"""Application settings, read once from the environment.

Defined here (not duplicated in bot/ and backend/) since DB and Redis
connection info is needed by all three processes. `backend/core/config.py`
and `bot/config.py` re-export this for discoverability within each service.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/newsbot"
    database_url_sync: str = "postgresql+psycopg://postgres:postgres@localhost:5432/newsbot"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Telegram
    telegram_bot_token: str = ""

    # Internal service auth (bot -> backend), see spec Phase 8.1
    internal_api_token: str = "change-me-in-production"
    admin_api_token: str = "change-me-in-production"
    backend_base_url: str = "http://localhost:8000"

    # AI provider: Google Gemini only (no Anthropic dependency).
    google_api_key: str = ""
    summarization_model: str = "gemini-2.0-flash"
    embedding_dimensions: int = 1024

    # Digest schedule (fixed for MVP — see spec Phase 1.4 / 4.2)
    default_timezone: str = "Asia/Tashkent"
    morning_digest_time: str = "07:00"
    evening_digest_time: str = "19:00"

    # Ranking weights (spec Phase 6.3) — starting values, tunable post-launch
    weight_source_count: float = 0.25
    weight_reliability: float = 0.20
    weight_category: float = 0.10
    weight_freshness: float = 0.20
    weight_clickbait_penalty: float = 0.15
    weight_interest_boost: float = 0.50
    weight_geo_bonus: float = 0.05
    weight_repeat_penalty: float = 0.30
    freshness_decay_hours: float = 8.0
    digest_max_items: int = 12

    # Summarization cost controls (spec Phase 5.2). An LLM call is the
    # single most expensive step in the pipeline, so these gate it:
    # only summarize events that have already proven themselves
    # important, cap how much source text (and how many articles) go
    # into one call, and cache aggressively (see pipeline/ai/summarizer.py)
    # so an event is never summarized twice for the same language.
    summarization_importance_threshold: float = 0.3
    summarization_max_articles_per_event: int = 5
    summarization_max_article_chars: int = 600


settings = Settings()
