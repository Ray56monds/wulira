"""
Persistent Job Storage
-----------------------
Redis-backed storage with automatic in-memory fallback.
Jobs survive server restarts when Redis is available.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("wulira-storage")


class JobStore:
    """Abstract job storage interface."""

    def save(self, job_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    def delete(self, job_id: str) -> bool:
        raise NotImplementedError

    def list_all(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        raise NotImplementedError

    def count_by_status(self) -> dict[str, int]:
        raise NotImplementedError

    def cleanup_expired(self, max_age_seconds: int) -> int:
        raise NotImplementedError


class RedisJobStore(JobStore):
    """Redis-backed persistent storage."""

    PREFIX = "wulira:job:"

    def __init__(self, redis_url: str) -> None:
        import redis
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.r.ping()
        logger.info(f"Redis connected: {redis_url}")

    def save(self, job_id: str, data: dict[str, Any]) -> None:
        key = f"{self.PREFIX}{job_id}"
        self.r.set(key, json.dumps(data, default=str))
        self.r.sadd("wulira:jobs", job_id)

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        raw = self.r.get(f"{self.PREFIX}{job_id}")
        return json.loads(raw) if raw else None

    def delete(self, job_id: str) -> bool:
        deleted = self.r.delete(f"{self.PREFIX}{job_id}")
        self.r.srem("wulira:jobs", job_id)
        return deleted > 0

    def list_all(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        all_ids = sorted(self.r.smembers("wulira:jobs"), reverse=True)
        page = all_ids[offset:offset + limit]
        results = []
        for jid in page:
            data = self.get(jid)
            if data:
                results.append(data)
        return results

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for jid in self.r.smembers("wulira:jobs"):
            data = self.get(jid)
            if data:
                status = data.get("status", "unknown")
                counts[status] = counts.get(status, 0) + 1
        return counts

    def cleanup_expired(self, max_age_seconds: int) -> int:
        removed = 0
        now = datetime.now()
        for jid in list(self.r.smembers("wulira:jobs")):
            data = self.get(jid)
            if not data:
                continue
            created = data.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created)
                if (now - created_dt).total_seconds() > max_age_seconds:
                    self.delete(jid)
                    removed += 1
            except (ValueError, TypeError):
                pass
        return removed


class MemoryJobStore(JobStore):
    """In-memory fallback (no persistence across restarts)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        logger.info("Using in-memory job store (no Redis)")

    def save(self, job_id: str, data: dict[str, Any]) -> None:
        self._store[job_id] = data

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        return self._store.get(job_id)

    def delete(self, job_id: str) -> bool:
        return self._store.pop(job_id, None) is not None

    def list_all(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        items = sorted(
            self._store.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
        return items[offset:offset + limit]

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for data in self._store.values():
            status = data.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def cleanup_expired(self, max_age_seconds: int) -> int:
        now = datetime.now()
        expired = []
        for jid, data in self._store.items():
            try:
                created_dt = datetime.fromisoformat(data.get("created_at", ""))
                if (now - created_dt).total_seconds() > max_age_seconds:
                    expired.append(jid)
            except (ValueError, TypeError):
                pass
        for jid in expired:
            del self._store[jid]
        return len(expired)


def create_store(redis_url: str | None = None) -> JobStore:
    """Create the best available store."""
    if redis_url:
        try:
            return RedisJobStore(redis_url)
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to memory")
    return MemoryJobStore()
