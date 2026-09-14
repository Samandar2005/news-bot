"""Request/response models for /api/v1/sources (admin-only, spec Phase 8.1
/ 8.2)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from shared.enums import SourceType


class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: SourceType
    language: str
    default_category_id: int | None = None
    reliability_score: float = 0.5
    is_state_affiliated: bool = False
    fetch_interval_minutes: int = 15


class SourceUpdate(BaseModel):
    """All fields optional — PATCH only touches what's provided.

    Changing reliability_score triggers a recompute of every event this
    source has contributed to (spec Phase 3 stage 8) — see
    backend/services/sources/service.py, not this schema.
    """

    name: str | None = None
    url: str | None = None
    source_type: SourceType | None = None
    language: str | None = None
    default_category_id: int | None = None
    reliability_score: float | None = None
    is_state_affiliated: bool | None = None
    is_active: bool | None = None
    fetch_interval_minutes: int | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    source_type: SourceType
    language: str
    default_category_id: int | None
    reliability_score: float
    is_state_affiliated: bool
    is_active: bool
    fetch_interval_minutes: int
    last_fetched_at: dt.datetime | None
