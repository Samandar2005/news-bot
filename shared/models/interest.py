"""interest_categories — the shared taxonomy for both user interests and
article/event categorization (see spec Phase 4.1 for why these are one table
instead of two).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.article import NewsArticle
    from shared.models.event import NewsEvent
    from shared.models.source import NewsSource
    from shared.models.user import UserInterest


class InterestCategory(Base):
    __tablename__ = "interest_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    name_uz: Mapped[str] = mapped_column(String(128), nullable=False)
    is_predefined: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Category-level base importance weight (the "C" term in the ranking
    # formula, spec Phase 6). Curated manually; e.g. World News/Politics
    # default higher than a niche category like Programming.
    default_weight: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    user_interests: Mapped[list["UserInterest"]] = relationship(back_populates="category")
    sources: Mapped[list["NewsSource"]] = relationship(back_populates="default_category")
    articles: Mapped[list["NewsArticle"]] = relationship(back_populates="category")
    events: Mapped[list["NewsEvent"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<InterestCategory key={self.key!r}>"
