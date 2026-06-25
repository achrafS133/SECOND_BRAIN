from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

from second_brain.config import Settings

logger = logging.getLogger(__name__)


class WorkingMemory:
    """M0 — ephemeral stream and session state (Redis-backed)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: redis.Redis | None = None
        self._local: dict[str, Any] = {}

    async def connect(self) -> None:
        try:
            self._client = redis.from_url(self._settings.redis_url, decode_responses=True)
            await self._client.ping()
            logger.info("Working memory connected to Redis")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable, using in-memory M0 fallback: %s", exc)
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def _key(self, namespace: str, key: str) -> str:
        return f"m0:{namespace}:{key}"

    async def set(self, namespace: str, key: str, value: Any, ttl_seconds: int = 300) -> None:
        payload = json.dumps(value)
        redis_key = self._key(namespace, key)
        if self._client:
            await self._client.setex(redis_key, ttl_seconds, payload)
        else:
            self._local[redis_key] = value

    async def get(self, namespace: str, key: str) -> Any | None:
        redis_key = self._key(namespace, key)
        if self._client:
            raw = await self._client.get(redis_key)
            return json.loads(raw) if raw else None
        return self._local.get(redis_key)

    async def get_pinned(self, session_id: str) -> dict[str, Any]:
        pinned = await self.get("session", f"{session_id}:pinned")
        return pinned or {}

    async def pin(self, session_id: str, data: dict[str, Any], ttl_seconds: int = 600) -> None:
        await self.set("session", f"{session_id}:pinned", data, ttl_seconds=ttl_seconds)

    async def update_iot_window(self, device_id: str, stats: dict[str, Any]) -> None:
        await self.set("iot", device_id, stats, ttl_seconds=120)
