"""Simple file-based HTTP response cache."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from history_tales_agent.utils.logging import get_logger

logger = get_logger(__name__)


class ResponseCache:
    """File-based cache for HTTP responses to reduce duplicate API calls."""

    def __init__(self, cache_dir: str | Path = ".cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def _key(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Generate a cache key from URL and params."""
        raw = url + json.dumps(params or {}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, url: str, params: dict[str, Any] | None = None) -> Optional[Any]:
        """Return cached response or None."""
        key = self._key(url, params)
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("_cached_at", 0) > self.ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            logger.debug("cache_hit", url=url)
            return data.get("payload")
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def set(self, url: str, payload: Any, params: dict[str, Any] | None = None) -> None:
        """Store a response in the cache."""
        key = self._key(url, params)
        path = self._path(key)
        data = {"_cached_at": time.time(), "url": url, "payload": payload}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        logger.debug("cache_set", url=url)


# Global cache instance
_cache: Optional[ResponseCache] = None


def get_cache(cache_dir: str = ".cache") -> ResponseCache:
    """Return (or create) the global cache instance."""
    global _cache
    if _cache is None:
        _cache = ResponseCache(cache_dir=cache_dir)
    return _cache
