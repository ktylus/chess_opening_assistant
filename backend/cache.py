"""Fail-open caching for expensive tool results."""

import hashlib
import json
import logging
import os
from collections.abc import Mapping
from typing import Protocol

import redis

from backend.observability import current_event

logger = logging.getLogger("chess_opening_assistant.cache")


def cache_key(namespace: str, inputs: Mapping[str, object]) -> str:
    """Return a stable, compact key for every input that shapes a result."""
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    return f"chess-opening-assistant:{namespace}:{digest}"


def _record(tool: str, outcome: str) -> None:
    current_event().cache_events.append({"tool": tool, "outcome": outcome})


class ToolCache(Protocol):
    def get(self, key: str, *, tool: str) -> str | None: ...

    def set(self, key: str, value: str, *, tool: str, ttl_seconds: int) -> None: ...

    def close(self) -> None: ...


class NoOpCache:
    """A cache used when Redis is not configured."""

    def get(self, key: str, *, tool: str) -> None:
        _record(tool, "disabled")

    def set(self, key: str, value: str, *, tool: str, ttl_seconds: int) -> None:
        return None

    def close(self) -> None:
        return None


class RedisCache:
    """Redis-backed cache that degrades to misses on Redis failures."""

    def __init__(self, client: redis.Redis):
        self._client = client

    def get(self, key: str, *, tool: str) -> str | None:
        try:
            value = self._client.get(key)
        except Exception:
            _record(tool, "read_error")
            logger.warning(
                "cache_read_failed", extra={"cache_tool": tool}, exc_info=True
            )
            return None

        if value is None:
            _record(tool, "miss")
            return None

        _record(tool, "hit")
        return value if isinstance(value, str) else value.decode()

    def set(self, key: str, value: str, *, tool: str, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, value)
        except Exception:
            _record(tool, "write_error")
            logger.warning(
                "cache_write_failed", extra={"cache_tool": tool}, exc_info=True
            )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            logger.warning("cache_close_failed", exc_info=True)


def cache_from_env() -> ToolCache:
    """Create Redis caching when configured, otherwise a no-op cache."""
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return NoOpCache()
    client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    return RedisCache(client)
