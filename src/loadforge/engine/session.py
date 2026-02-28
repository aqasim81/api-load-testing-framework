"""Test session lifecycle management and signal handling."""

from __future__ import annotations

import asyncio
import contextlib
import random
import signal
import sys
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

from loadforge._internal.errors import EngineError
from loadforge._internal.logging import get_logger
from loadforge.dsl.http_client import HttpClient
from loadforge.engine._user_utils import pick_weighted_task, shutdown_all_users
from loadforge.engine.rate_limiter import TokenBucketRateLimiter
from loadforge.engine.scheduler import Scheduler
from loadforge.metrics.collector import MetricCollector
from loadforge.metrics.models import MetricSnapshot, TestResult

if TYPE_CHECKING:
    from loadforge.dsl.scenario import ScenarioDefinition
    from loadforge.patterns.base import LoadPattern

logger = get_logger("engine.session")


class SessionState(Enum):
    """State machine for a test session."""

    CREATED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    COMPLETED = auto()
    FAILED = auto()


class TestSession:
    """Manages the lifecycle of a single-worker load test.

    Coordinates the scheduler, virtual users, collector, and signal
    handling. This is the top-level entry point for executing a load
    test in a single process.

    State machine: CREATED -> STARTING -> RUNNING -> STOPPING -> COMPLETED
                                                  -> FAILED (on error)

    Attributes:
        scenario: The scenario being executed.
    """

    def __init__(
        self,
        scenario: ScenarioDefinition,
        pattern: LoadPattern,
        duration_seconds: float,
        *,
        tick_interval: float = 1.0,
        rate_limit: float | None = None,
        worker_id: int = 0,
    ) -> None:
        """Initialize a test session.

        Args:
            scenario: The scenario definition to execute.
            pattern: Traffic pattern controlling concurrency.
            duration_seconds: Total test duration in seconds.
            tick_interval: Seconds between concurrency adjustments.
            rate_limit: Optional max requests per second (token bucket).
                None means no rate limit (concurrency-based only).
            worker_id: Worker identifier for metric tagging.
        """
        self._scenario = scenario
        self._pattern = pattern
        self._duration_seconds = duration_seconds
        self._tick_interval = tick_interval
        self._rate_limit = rate_limit
        self._worker_id = worker_id

        self._state = SessionState.CREATED
        self._collector = MetricCollector(worker_id=worker_id)
        self._rate_limiter: TokenBucketRateLimiter | None = None
        self._user_tasks: list[tuple[int, asyncio.Task[None]]] = []
        self._next_user_id = 0
        self._stop_event = asyncio.Event()

    @property
    def state(self) -> SessionState:
        """Return the current session state."""
        return self._state

    @property
    def active_user_count(self) -> int:
        """Return the number of active virtual users."""
        return len(self._user_tasks)

    async def run(self) -> TestResult:
        """Execute the full test session lifecycle.

        Returns:
            TestResult containing all snapshots and the final summary.

        Raises:
            EngineError: If the session fails to start or encounters
                an unrecoverable error.
        """
        self._state = SessionState.STARTING
        logger.info(
            "Starting test session: scenario=%s, duration=%.1fs, pattern=%s",
            self._scenario.name,
            self._duration_seconds,
            self._pattern.describe(),
        )

        self._install_signal_handlers()

        if self._rate_limit is not None:
            self._rate_limiter = TokenBucketRateLimiter(rate=self._rate_limit)

        scheduler = Scheduler(self._pattern, self._duration_seconds, self._tick_interval)

        start_time = time.monotonic()
        snapshots: list[MetricSnapshot] = []

        self._state = SessionState.RUNNING

        try:
            for command in scheduler.iter_commands():
                if self._stop_event.is_set():
                    break

                # Wait until the right time for this tick
                target_time = start_time + command.elapsed_seconds
                now = time.monotonic()
                if target_time > now:
                    await asyncio.sleep(target_time - now)

                if self._stop_event.is_set():
                    break

                # Adjust concurrency
                await self._scale_users(command.target_concurrency)

                # Flush metrics for this interval
                elapsed = time.monotonic() - start_time
                snapshot = self._collector.flush(
                    elapsed_seconds=elapsed,
                    active_users=self.active_user_count,
                )
                snapshots.append(snapshot)

                logger.debug(
                    "Tick %.1fs: users=%d, rps=%.1f, p95=%.1fms, errors=%d",
                    elapsed,
                    self.active_user_count,
                    snapshot.requests_per_second,
                    snapshot.latency_p95,
                    snapshot.total_errors,
                )

        except Exception as exc:
            self._state = SessionState.FAILED
            logger.exception("Test session failed")
            raise EngineError("Test session failed") from exc
        finally:
            # Graceful shutdown
            if self._state != SessionState.FAILED:
                self._state = SessionState.STOPPING
            await shutdown_all_users(self._user_tasks, self._stop_event)
            self._remove_signal_handlers()

        end_time = time.monotonic()
        total_duration = end_time - start_time

        # Final flush to capture teardown metrics
        self._collector.flush(
            elapsed_seconds=total_duration,
            active_users=0,
        )

        final_summary = self._collector.get_cumulative_snapshot(
            elapsed_seconds=total_duration,
            active_users=0,
        )

        self._state = SessionState.COMPLETED
        logger.info(
            "Test completed: duration=%.1fs, total_requests=%d, avg_rps=%.1f, "
            "p95=%.1fms, error_rate=%.2f%%",
            total_duration,
            final_summary.total_requests,
            final_summary.requests_per_second,
            final_summary.latency_p95,
            final_summary.error_rate * 100,
        )

        return TestResult(
            scenario_name=self._scenario.name,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=total_duration,
            pattern_description=self._pattern.describe(),
            snapshots=snapshots,
            final_summary=final_summary,
        )

    async def stop(self) -> None:
        """Request graceful shutdown of the session.

        Sets state to STOPPING, which causes the main loop to exit
        after the current tick.
        """
        if self._state == SessionState.RUNNING:
            logger.info("Graceful shutdown requested")
            self._state = SessionState.STOPPING
            self._stop_event.set()

    async def _run_virtual_user(self, user_id: int) -> None:
        """Run a single virtual user lifecycle.

        Args:
            user_id: Unique identifier for this virtual user.
        """
        instance = self._scenario.cls()
        async with HttpClient(
            base_url=self._scenario.base_url,
            headers=dict(self._scenario.default_headers),
            metric_callback=self._collector.record,
            worker_id=self._worker_id,
        ) as client:
            try:
                # Setup phase
                if self._scenario.setup_func is not None:
                    await self._scenario.setup_func(instance, client)

                # Task loop
                while not self._stop_event.is_set():
                    task_def = pick_weighted_task(self._scenario.tasks)
                    try:
                        if self._rate_limiter is not None:
                            await self._rate_limiter.acquire()
                        await task_def.func(instance, client)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.debug(
                            "Task %s failed for user %d",
                            task_def.name,
                            user_id,
                            exc_info=True,
                        )

                    # Think time
                    min_t, max_t = self._scenario.think_time
                    await asyncio.sleep(random.uniform(min_t, max_t))  # noqa: S311

            except asyncio.CancelledError:
                pass
            finally:
                # Teardown phase — always runs
                if self._scenario.teardown_func is not None:
                    try:
                        await self._scenario.teardown_func(instance, client)
                    except Exception:
                        logger.warning(
                            "Teardown failed for user %d",
                            user_id,
                            exc_info=True,
                        )

    async def _scale_users(self, target: int) -> None:
        """Adjust the number of active virtual users to match target.

        Args:
            target: Desired number of active virtual users.
        """
        current = self.active_user_count

        if target > current:
            # Scale up: create new virtual user tasks
            for _ in range(target - current):
                user_id = self._next_user_id
                self._next_user_id += 1
                task = asyncio.create_task(
                    self._run_virtual_user(user_id),
                    name=f"virtual-user-{user_id}",
                )
                self._user_tasks.append((user_id, task))

        elif target < current:
            # Scale down: cancel most recently created (LIFO)
            to_remove = current - target
            for _ in range(to_remove):
                if self._user_tasks:
                    _uid, task = self._user_tasks.pop()
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)

        # Clean up completed tasks
        self._user_tasks = [(uid, t) for uid, t in self._user_tasks if not t.done()]

    def _install_signal_handlers(self) -> None:
        """Install SIGINT and SIGTERM handlers for graceful shutdown.

        Handlers transition the session to STOPPING state, which causes
        the main loop to exit after the current tick.
        """
        loop = asyncio.get_running_loop()

        def _signal_handler() -> None:
            logger.info("Signal received, initiating graceful shutdown")
            self._state = SessionState.STOPPING
            self._stop_event.set()

        if sys.platform != "win32":
            loop.add_signal_handler(signal.SIGINT, _signal_handler)
            loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        else:
            # Windows doesn't support add_signal_handler
            signal.signal(signal.SIGINT, lambda _s, _f: _signal_handler())
            signal.signal(signal.SIGTERM, lambda _s, _f: _signal_handler())

    def _remove_signal_handlers(self) -> None:
        """Remove custom signal handlers, restoring defaults."""
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
        else:
            signal.signal(signal.SIGINT, signal.default_int_handler)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
