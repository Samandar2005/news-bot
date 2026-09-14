"""Request/response models for /api/v1/interests and
/api/v1/users/{telegram_id}/interests.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name_en: str
    name_ru: str
    name_uz: str
    default_weight: float


class UserInterestsSet(BaseModel):
    """Replaces a user's full set of predefined-category interests.

    Custom (free-text) interests are managed separately — see spec Phase
    1.4: onboarding only covers predefined categories in the MVP.
    """

    category_ids: list[int]


class UserInterestsRead(BaseModel):
    categories: list[CategoryRead]
