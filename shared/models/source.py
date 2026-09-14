"""news_sources — configured feeds/APIs the collectors pull from."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import SourceType
from shared.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from shared.models.article import NewsArticle
    from shared.models.interest import InterestCategory


class NewsSource(Base, TimestampMixin):
    __tablename__ = "news_sources"
    __table_args__ = (UniqueConstraint("url", name="uq_news_sources_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    default_category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interest_categories.id", ondelete="SET NULL"), nullable=True
    )
    # Static, manually curated for MVP (spec Phase 3, stage 8 / Phase 5).
    reliability_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    # Spec Phase 3 stage 8's explicit edge case: "state-affiliated or
    # heavily biased outlets — flag, don't necessarily exclude." Kept as
    # its own boolean rather than folded into reliability_score, since
    # "state-affiliated" and "factually unreliable" are related but
    # distinct judgments — a state outlet can still be accurate on
    # non-political stories, and collapsing both into one number would
    # lose the more specific, more useful signal for anything downstream
    # (a digest UI badge, a ranking penalty that only applies to
    # political/world-news categories, etc.) that wants to reason about
    # them separately.
    is_state_affiliated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    last_fetched_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    default_category: Mapped["InterestCategory | None"] = relationship(back_populates="sources")
    articles: Mapped[list["NewsArticle"]] = relationship(back_populates="source")

    def __repr__(self) -> str:
        return f"<NewsSource name={self.name!r} type={self.source_type}>"
