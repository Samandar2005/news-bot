"""Internal service auth (spec Phase 8.1).

The API is bot-facing only in the MVP — no public clients — so a static
shared-secret header is sufficient. `/health` is deliberately excluded
(Docker's healthcheck doesn't send custom headers).
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from backend.core.config import settings


async def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing internal token"
        )


async def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin token"
        )
