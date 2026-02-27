"""Token-bucket rate limiter for controlling request throughput."""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Controls the rate at which virtual users can make requests. Each
    ``acquire()`` call consumes one token. Tokens are replenished at
    ``rate`` tokens per second. The bucket can hold at most ``capacity``
    tokens (allowing short bursts).

    When tokens are exhausted, ``acquire()`` awaits until a token becomes
    available.

    Attributes:
        rate: Tokens added per second.
        capacity: Maximum token count (burst capacity).
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            rate: Tokens per second. Must be positive.
            capacity: Maximum tokens. Defaults to ``rate`` (1 second of burst).

        Raises:
            ValueError: If rate is not positive.
        """
        if rate <= 0:
            msg = f"rate must be positive, got {rate}"
            raise ValueError(msg)

        self._rate = rate
        self._capacity = capacity if capacity is not None else rate
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def rate(self) -> float:
        """Return the current token replenishment rate."""
        return self._rate

    @property
    def capacity(self) -> float:
        """Return the maximum token capacity."""
        return self._capacity

    @property
    def available_tokens(self) -> float:
        """Return the current number of available tokens (approximate).

        Performs a time-based refill calculation without acquiring the lock.
        The result is approximate since another coroutine may modify tokens
        concurrently.
        """
        elapsed = time.monotonic() - self._last_refill
        return min(self._capacity, self._tokens + elapsed * self._rate)

    async def acquire(self) -> None:
        """Acquire a single token, waiting if necessary.

        Blocks the calling coroutine until a token is available. Uses
        ``asyncio.sleep()`` for the wait, allowing other coroutines to run.
        """
        async with self._lock:
            self._refill()
            while self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rate
                # Release lock during sleep so other coroutines can proceed
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                finally:
                    await self._lock.acquire()
                self._refill()
            self._tokens -= 1.0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def update_rate(self, new_rate: float) -> None:
        """Update the replenishment rate.

        Refills tokens at the current rate before applying the new rate,
        ensuring no tokens are lost during the transition.

        Args:
            new_rate: New tokens-per-second rate. Must be positive.

        Raises:
            ValueError: If new_rate is not positive.
        """
        if new_rate <= 0:
            msg = f"rate must be positive, got {new_rate}"
            raise ValueError(msg)
        self._refill()
        self._rate = new_rate
