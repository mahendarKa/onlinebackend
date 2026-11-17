"""Tiny in-process sliding-window rate limiter.

No external dependency — keeps state in a module-level dict. Suitable
for a single-worker deployment; if the app ever runs multiple uvicorn
workers, swap the store for Redis so limits are shared.
"""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow at most ``max_hits`` calls per ``window`` seconds per key."""

    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Record a hit for ``key``; True if within limit, else False."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_hits:
                return False
            q.append(now)
            # Bound memory: drop keys whose windows have fully expired.
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items()
                          if not v or v[-1] < cutoff]:
                    del self._hits[k]
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest hit leaves the window (for 429s)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return 0
            return max(1, int(self.window - (now - q[0])) + 1)
