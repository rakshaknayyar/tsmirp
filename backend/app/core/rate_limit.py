"""Simple in-memory rate limiter (sliding window).

Keeps the times of recent attempts per key (for login: IP address + e-mail). If a key has
already used up its attempts within the window, the request is refused with HTTP 429.

Limitation: counts live in this one API process. With several API processes a shared store
(e.g. Redis) would be needed. That is fine for this single-process prototype.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status

from app.core.config import settings


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()  # forget attempts older than the window
            if len(hits) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - hits[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter(settings.login_rate_limit, settings.login_rate_window_seconds)
sos_limiter = RateLimiter(settings.sos_rate_limit, settings.sos_rate_window_seconds)
classify_limiter = RateLimiter(settings.classify_rate_limit, settings.classify_rate_window_seconds)
