from __future__ import annotations

import time
from collections import deque
from threading import Lock

from docuflow.exceptions import RateLimitError


class MemoryRateLimiter:
    """Process-local sliding-window limiter.

    Expired timestamps are dropped on each ``hit``. Empty buckets are
    removed under the same lock. Other keys are evicted using the window
    stored from their last ``hit``, so idle identifiers do not accumulate
    indefinitely. This is not shared across processes or replicas.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._windows: dict[str, int] = {}
        self._lock = Lock()

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._windows[key] = window_seconds
            self._evict_expired(now)
            bucket = self._hits.get(key)
            if bucket is not None and len(bucket) >= limit:
                raise RateLimitError("Too many requests. Try again shortly.")
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            bucket.append(now)
            self._windows[key] = window_seconds

    def _evict_expired(self, now: float) -> None:
        stale: list[str] = []
        for key, bucket in self._hits.items():
            window = self._windows.get(key)
            if window is None:
                continue
            cutoff = now - window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if not bucket:
                stale.append(key)
        for key in stale:
            del self._hits[key]
            self._windows.pop(key, None)
