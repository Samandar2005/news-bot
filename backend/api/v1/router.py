"""Aggregates all /api/v1 resource routers into one."""

from fastapi import APIRouter

from backend.api.v1 import digest, interests, notifications, sources, users

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)
router.include_router(interests.router)
router.include_router(sources.router)
router.include_router(notifications.router)
router.include_router(digest.router)
