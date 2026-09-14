"""news_articles — one row per collected article.

No separate article_sources join table: an article has exactly one source
and, once clustered, belongs to at most one event (spec Phase 4.1).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base
from shared.models.user import EMBEDDING_DIM

if TYPE_CHECKING:
    from shared.models.event import NewsEvent
    from shared.models.interest import InterestCategory
    from shared.models.source import NewsSource


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (UniqueConstraint("source_id", "url", name="uq_source_url"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of normalized content — cheap exact-duplicate pre-filter
    # before the more expensive embedding similarity check (Phase 3, stage 6).
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    language: Mapped[str | None] = mapped_column(String(2), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interest_categories.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("news_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    clickbait_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source: Mapped["NewsSource"] = relationship(back_populates="articles")
    category: Mapped["InterestCategory | None"] = relationship(back_populates="articles")
    event: Mapped["NewsEvent | None"] = relationship(back_populates="articles")

    def __repr__(self) -> str:
        return f"<NewsArticle id={self.id} title={self.title[:40]!r}>"
