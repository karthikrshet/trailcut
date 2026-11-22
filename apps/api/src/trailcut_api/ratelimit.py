"""Per-client token-bucket rate limiting, in memory.

Example:
    >>> limiter = RateLimiter(per_minute=30)
    >>> limiter.allow("203.0.113.7")
    True
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

Clock = Callable[[], float]
MAX_CLIENTS = 50_000


class RateLimiter:
    """``per_minute`` requests per key, refilled continuously; bursts up to ``per_minute``."""

    def __init__(self, *, per_minute: int, clock: Clock = time.monotonic) -> None:
        if per_minute <= 0:
            msg = "per_minute must be positive"
            raise ValueError(msg)
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Spend one token for ``key``; False if none are left."""
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if len(self._buckets) > MAX_CLIENTS:
                self._buckets.clear()
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` has a token again (at least 1)."""
        with self._lock:
            tokens, _ = self._buckets.get(key, (self.capacity, 0.0))
        missing = max(0.0, 1 - tokens)
        return max(1, int(missing / self.rate + 0.999))
