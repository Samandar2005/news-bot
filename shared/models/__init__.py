"""Single import point for the full ORM schema.

Alembic's `env.py` imports `Base` from here specifically so that every model
below has been registered on `Base.metadata` before autogenerate runs.
Forgetting to import a new model here is the #1 cause of "alembic
autogenerate produced an empty migration" — so anything new goes in this
list.
"""

from shared.models.article import NewsArticle
from shared.models.base import Base
from shared.models.digest import Digest, DigestItem
from shared.models.event import EventSummary, NewsEvent
from shared.models.interest import InterestCategory
from shared.models.source import NewsSource
from shared.models.user import CustomInterest, NotificationSettings, User, UserInterest

__all__ = [
    "Base",
    "User",
    "UserInterest",
    "CustomInterest",
    "NotificationSettings",
    "InterestCategory",
    "NewsSource",
    "NewsArticle",
    "NewsEvent",
    "EventSummary",
    "Digest",
    "DigestItem",
]
