"""news_events, event_summaries — clustered stories and their per-language
cached AI summaries (spec Phase 4.1: one event can need a summary in more
than one language, hence a separate table rather than a column on the event).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import EventStatus
from shared.models.base import Base

if TYPE_CHECKING:
    from shared.models.article import NewsArticle
    from shared.models.digest import DigestItem
    from shared.models.interest import InterestCategory


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interest_categories.id", ondelete="SET NULL"), nullable=True
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Denormalized for fast scoring reads — updated whenever an article is
    # attached to this event (Phase 3, stages 7-9).
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_reliability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    status: Mapped[EventStatus] = mapped_column(
        String(16), default=EventStatus.ACTIVE, nullable=False
    )

    category: Mapped["InterestCategory | None"] = relationship(back_populates="events")
    articles: Mapped[list["NewsArticle"]] = relationship(back_populates="event")
    summaries: Mapped[list[EventSummary]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    digest_items: Mapped[list["DigestItem"]] = relationship(back_populates="event")

    def __repr__(self) -> str:
        return f"<NewsEvent id={self.id} importance={self.importance_score:.2f}>"


class EventSummary(Base):
    __tablename__ = "event_summaries"
    __table_args__ = (UniqueConstraint("event_id", "language", name="uq_event_language"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("news_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    event: Mapped["NewsEvent"] = relationship(back_populates="summaries")
