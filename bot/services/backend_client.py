"""Thin async wrapper around the backend's /api/v1 endpoints.

The bot never talks to the database directly (spec Phase 8.2) — everything
goes through this client, which is the only place that knows the backend's
URL shape and auth header.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

import httpx


def _from_json(cls: type, data: dict[str, Any]):
    """Constructs a dataclass from a JSON dict, ignoring any keys that
    aren't fields on the dataclass.

    This exists because of a real bug: earlier versions of these DTOs
    used `Cls(**data)` directly, which raises `TypeError` the instant the
    backend's response includes a field the DTO doesn't declare (e.g.
    UserRead's `created_at`, CategoryRead's `default_weight` — present on
    the real backend response the whole time, but never caught because
    every prior test mocked BackendClient entirely rather than parsing a
    real response). A DTO only needs to declare the fields the bot
    actually uses; the backend is free to return more.
    """
    known_field_names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known_field_names})


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: int
    telegram_id: int
    username: str | None
    language: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CategoryDTO:
    id: int
    key: str
    name_en: str
    name_ru: str
    name_uz: str

    def localized_name(self, language: str) -> str:
        return getattr(self, f"name_{language}", None) or self.name_en


@dataclass(frozen=True, slots=True)
class NotificationSettingsDTO:
    morning_enabled: bool
    evening_enabled: bool
    morning_time: str
    evening_time: str
    timezone: str


class BackendError(RuntimeError):
    """Raised when the backend responds with an unexpected error."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        internal_token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # `transport` is a testability hook — tests pass an httpx.MockTransport
        # instead of hitting the network; production code never sets it.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Internal-Token": internal_token},
            timeout=timeout,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_user(self, telegram_id: int) -> UserDTO | None:
        resp = await self._client.get(f"/api/v1/users/{telegram_id}")
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp)
        return _from_json(UserDTO, resp.json())

    async def create_user(
        self, telegram_id: int, username: str | None, language: str
    ) -> UserDTO:
        resp = await self._client.post(
            "/api/v1/users",
            json={"telegram_id": telegram_id, "username": username, "language": language},
        )
        self._raise_for_status(resp)
        return _from_json(UserDTO, resp.json())

    async def update_user_language(self, telegram_id: int, language: str) -> UserDTO:
        resp = await self._client.patch(
            f"/api/v1/users/{telegram_id}", json={"language": language}
        )
        self._raise_for_status(resp)
        return _from_json(UserDTO, resp.json())

    async def list_categories(self) -> list[CategoryDTO]:
        resp = await self._client.get("/api/v1/interests/categories")
        self._raise_for_status(resp)
        return [_from_json(CategoryDTO, c) for c in resp.json()]

    async def get_user_interest_ids(self, telegram_id: int) -> set[int]:
        resp = await self._client.get(f"/api/v1/users/{telegram_id}/interests")
        self._raise_for_status(resp)
        return {c["id"] for c in resp.json()["categories"]}

    async def set_user_interests(self, telegram_id: int, category_ids: list[int]) -> None:
        resp = await self._client.put(
            f"/api/v1/users/{telegram_id}/interests", json={"category_ids": category_ids}
        )
        self._raise_for_status(resp)

    async def get_notification_settings(self, telegram_id: int) -> NotificationSettingsDTO:
        resp = await self._client.get(f"/api/v1/users/{telegram_id}/notifications")
        self._raise_for_status(resp)
        return _from_json(NotificationSettingsDTO, resp.json())

    async def update_notification_settings(
        self,
        telegram_id: int,
        *,
        morning_enabled: bool | None = None,
        evening_enabled: bool | None = None,
    ) -> NotificationSettingsDTO:
        payload = {}
        if morning_enabled is not None:
            payload["morning_enabled"] = morning_enabled
        if evening_enabled is not None:
            payload["evening_enabled"] = evening_enabled
        resp = await self._client.patch(
            f"/api/v1/users/{telegram_id}/notifications", json=payload
        )
        self._raise_for_status(resp)
        return _from_json(NotificationSettingsDTO, resp.json())

    async def get_digest_preview(self, telegram_id: int) -> str | None:
        """Returns rendered digest text, or None if there's nothing to
        show right now (spec Phase 3 stage 13's "fewer than N — send
        fewer" edge case, taken to its limit: zero)."""
        resp = await self._client.get(f"/api/v1/users/{telegram_id}/digest/preview")
        self._raise_for_status(resp)
        body = resp.json()
        return body["text"] if body["has_content"] else None

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise BackendError(f"{resp.status_code} from backend: {resp.text}")
