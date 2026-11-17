import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional
from fastapi import Request

from app.core.exceptions import RateLimitException


class SlidingWindowRateLimiter:
    """In-memory thread-safe-capable sliding-window rate limiter."""

    def __init__(self) -> None:
        self._history: Dict[str, List[float]] = defaultdict(list)
        self.enabled: bool = True

    def reset(self) -> None:
        """Clear all recorded request timestamps."""
        self._history.clear()

    def check(self, key: str, max_requests: int, window_seconds: int) -> None:
        """Verify if key has exceeded max_requests in the sliding window."""
        if not self.enabled:
            return

        now = time.time()
        cutoff = now - window_seconds
        timestamps = self._history[key]

        # Filter out expired timestamps
        valid_timestamps = [t for t in timestamps if t > cutoff]
        self._history[key] = valid_timestamps

        if len(valid_timestamps) >= max_requests:
            retry_after = int(window_seconds - (now - valid_timestamps[0])) + 1
            raise RateLimitException(
                message=f"Rate limit exceeded: maximum {max_requests} requests per {window_seconds}s. Please retry in {retry_after}s.",
                code="TOO_MANY_REQUESTS",
                details={
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                    "retry_after_seconds": max(1, retry_after),
                },
            )

        self._history[key].append(now)


# Global rate limiter instance
limiter = SlidingWindowRateLimiter()


def reset_rate_limiter() -> None:
    """Reset rate limiter state (used in tests)."""
    limiter.reset()


def rate_limit(
    max_requests: int,
    window_seconds: int,
    scope: str = "default",
) -> Callable:
    """FastAPI dependency factory enforcing a sliding-window rate limit."""

    async def rate_limit_dependency(request: Request) -> None:
        # Determine client identity (User ID if authenticated or Client IP)
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None) if user else getattr(request.state, "user_id", None)

        if user_id:
            identifier = f"user:{user_id}"
        else:
            # Client IP detection with X-Forwarded-For fallback
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            elif request.client and request.client.host:
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"
            identifier = f"ip:{client_ip}"

        rate_limit_key = f"{scope}:{identifier}"
        limiter.check(rate_limit_key, max_requests, window_seconds)

    return rate_limit_dependency
