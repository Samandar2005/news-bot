"""Request/response models for /api/v1/users/{telegram_id}/notifications."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class NotificationSettingsUpdate(BaseModel):
    """Both fields optional — PATCH only touches what's provided, same
    pattern as SourceUpdate/UserUpdate."""

    morning_enabled: bool | None = None
    evening_enabled: bool | None = None


class NotificationSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    morning_enabled: bool
    evening_enabled: bool
    morning_time: dt.time
    evening_time: dt.time
    timezone: str
