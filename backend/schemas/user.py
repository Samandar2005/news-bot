"""Request/response models for /api/v1/users."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from shared.enums import Language


class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    language: Language = Language.EN


class UserUpdate(BaseModel):
    username: str | None = None
    language: Language | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    language: Language
    is_active: bool
    created_at: dt.datetime
