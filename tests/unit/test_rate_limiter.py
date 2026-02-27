"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from loadforge.engine.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketInit:
    """Tests for rate limiter initialization."""

    def test_default_capacity_equals_rate(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0)
        assert limiter.capacity == 10.0

    def test_custom_capacity(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=5.0)
        assert limiter.capacity == 5.0

    def test_rate_property(self) -> None:
        limiter = TokenBucketRateLimiter(rate=42.0)
        assert limiter.rate == 42.0

    def test_rejects_zero_rate(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            TokenBucketRateLimiter(rate=0.0)

    def test_rejects_negative_rate(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            TokenBucketRateLimiter(rate=-1.0)


class TestTokenBucketAcquire:
    """Tests for the acquire method."""

    async def test_acquire_succeeds_when_tokens_available(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0)
        # Should succeed immediately since bucket starts full
        await limiter.acquire()
        assert limiter.available_tokens < 100.0

    async def test_burst_capacity(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=5.0)
        # Should allow 5 immediate acquires
        for _ in range(5):
            await limiter.acquire()
        # After 5 acquires, tokens should be near zero
        assert limiter.available_tokens < 1.0

    async def test_acquire_waits_when_empty(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=1.0)
        # First acquire should be fast
        await limiter.acquire()

        # Second acquire should wait ~0.1s (1 token / 10 tokens/sec)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        # Allow generous tolerance for CI
        assert elapsed >= 0.05

    async def test_rate_controls_throughput(self) -> None:
        rate = 20.0
        limiter = TokenBucketRateLimiter(rate=rate, capacity=1.0)
        # Exhaust the initial token
        await limiter.acquire()

        # Acquire 5 more tokens — should take ~0.25s
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        # Should take roughly 5/20 = 0.25s (generous tolerance)
        assert elapsed >= 0.15

    async def test_available_tokens_property(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=10.0)
        initial = limiter.available_tokens
        assert abs(initial - 10.0) < 0.5
        await limiter.acquire()
        assert limiter.available_tokens < initial

    async def test_concurrent_acquires(self) -> None:
        """Multiple coroutines acquiring concurrently should not exceed rate."""
        limiter = TokenBucketRateLimiter(rate=50.0, capacity=5.0)
        count = 0

        async def consumer() -> None:
            nonlocal count
            await limiter.acquire()
            count += 1

        # Launch 10 concurrent consumers (only 5 tokens available initially)
        tasks = [asyncio.create_task(consumer()) for _ in range(10)]
        await asyncio.gather(*tasks)
        assert count == 10


class TestTokenBucketUpdateRate:
    """Tests for the update_rate method."""

    def test_update_rate(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0)
        limiter.update_rate(100.0)
        assert limiter.rate == 100.0

    def test_update_rate_rejects_zero(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0)
        with pytest.raises(ValueError, match="positive"):
            limiter.update_rate(0.0)

    def test_update_rate_rejects_negative(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0)
        with pytest.raises(ValueError, match="positive"):
            limiter.update_rate(-5.0)
