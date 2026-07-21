"""Small bounded in-process rate limiter for prototype expensive routes."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowRateLimiter:
    def __init__(self, window_seconds: float = 60.0, max_keys: int = 10_000):
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._events[key]
            cutoff = current - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(current)
            if len(self._events) > self.max_keys:
                stale = [candidate for candidate, values in self._events.items() if not values or values[-1] <= cutoff]
                for candidate in stale:
                    self._events.pop(candidate, None)
            return True
