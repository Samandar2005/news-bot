"""Response model for GET /api/v1/users/{telegram_id}/digest/preview
(spec Phase 8.2 — the on-demand /news command's backing endpoint)."""

from __future__ import annotations

from pydantic import BaseModel


class DigestPreviewRead(BaseModel):
    has_content: bool
    text: str | None = None
