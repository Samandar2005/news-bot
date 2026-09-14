"""Shared enumerations used across the bot, backend, and pipeline.

Kept in one place (rather than duplicated per-module) since these values are
referenced by SQLAlchemy models, Pydantic schemas, and Celery tasks alike.
"""

from __future__ import annotations

import enum


class Language(enum.StrEnum):
    """Supported UI / digest languages."""

    UZ = "uz"
    RU = "ru"
    EN = "en"


class SourceType(enum.StrEnum):
    """How a news source is collected."""

    RSS = "rss"
    API = "api"
    WEB = "web"


class EventStatus(enum.StrEnum):
    """Lifecycle state of a clustered news event."""

    ACTIVE = "active"  # still receiving new articles / eligible for digests
    ARCHIVED = "archived"  # aged out, no longer eligible for new digests


class DigestType(enum.StrEnum):
    """Why a digest was generated."""

    MORNING = "morning"
    EVENING = "evening"
    ON_DEMAND = "on_demand"


class DigestStatus(enum.StrEnum):
    """Outcome of attempting to send a digest."""

    SENT = "sent"
    FAILED = "failed"
    SKIPPED_NO_CONTENT = "skipped_no_content"
