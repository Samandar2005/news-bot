"""Minimal logging configuration.

Structured/JSON logging and log shipping are an M15 (hardening) concern —
this gives every process a consistent, readable format in the meantime
rather than aiogram/FastAPI/SQLAlchemy's differing defaults.
"""

from __future__ import annotations

import logging

from backend.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # SQLAlchemy's own logger is chatty at INFO; only surface it if we're
    # explicitly asking for DEBUG-level output.
    if settings.log_level.upper() != "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
