"""
API Key Authentication
-----------------------
Simple API key auth for Wulira.
Keys stored in Redis (persistent) or memory (dev).
"""

import hashlib
import secrets
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("wulira-auth")

# Public endpoints that don't require auth
PUBLIC_PATHS = {
    "/api/health",
    "/api/docs",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/",
}


def generate_api_key() -> str:
    """Generate a new API key."""
    return f"wulira_{secrets.token_urlsafe(32)}"


def hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


class APIKeyManager:
    """Manage API keys with metadata."""

    def __init__(self, store: Any = None) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        self._store = store  # Redis store if available
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load master key from environment."""
        import os
        master = os.environ.get("WULIRA_API_KEY")
        if master:
            self._keys[hash_key(master)] = {
                "name": "master",
                "created_at": datetime.now().isoformat(),
                "role": "admin",
            }
            logger.info("Master API key loaded from environment")

    def create_key(self, name: str, role: str = "user") -> str:
        """Create and register a new API key. Returns the raw key."""
        raw = generate_api_key()
        hashed = hash_key(raw)
        self._keys[hashed] = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "role": role,
        }
        logger.info(f"API key created: {name} ({role})")
        return raw

    def validate(self, raw_key: str) -> Optional[dict[str, Any]]:
        """Validate an API key. Returns key metadata or None."""
        hashed = hash_key(raw_key)
        return self._keys.get(hashed)

    def revoke(self, raw_key: str) -> bool:
        """Revoke an API key."""
        hashed = hash_key(raw_key)
        return self._keys.pop(hashed, None) is not None

    def list_keys(self) -> list[dict[str, Any]]:
        """List all registered keys (without hashes)."""
        return [
            {"name": v["name"], "role": v["role"], "created_at": v["created_at"]}
            for v in self._keys.values()
        ]

    @property
    def enabled(self) -> bool:
        """Auth is enabled if any keys are registered."""
        return len(self._keys) > 0


def is_public_path(path: str) -> bool:
    """Check if a path is public (no auth needed)."""
    if path in PUBLIC_PATHS:
        return True
    # Static files and WebSocket
    if path.startswith("/ws/") or path.startswith("/static"):
        return True
    # Allow the dashboard
    if path == "/" or path.startswith("/index"):
        return True
    return False
