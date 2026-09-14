"""FastAPI application entrypoint.

Run directly with: uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from backend.api.v1.router import router as api_v1_router
from backend.core.logging import configure_logging
from backend.core.metrics import increment, prometheus_text
from backend.db.session import session_scope

configure_logging()

app = FastAPI(
    title="News Bot Backend",
    description=(
        "Internal API for the Telegram News Intelligence Bot — "
        "bot-facing only (spec Phase 8.1)."
    ),
    version="0.1.0",
)

app.include_router(api_v1_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Unauthenticated on purpose — used by Docker's HEALTHCHECK (spec
    docker/Dockerfile.backend), which doesn't send custom headers."""
    increment("health_checks_total")
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    """Readiness probe: only healthy when the database is reachable."""
    async with session_scope() as session:
        await session.execute(text("SELECT 1"))
    increment("readiness_checks_total")
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse, tags=["health"])
async def metrics() -> str:
    """Dependency-free Prometheus text endpoint for basic operational metrics."""
    return prometheus_text()
