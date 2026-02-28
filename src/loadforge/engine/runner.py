"""Top-level load test orchestrator."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loadforge._internal.errors import EngineError
from loadforge._internal.logging import get_logger, setup_logging
from loadforge.dsl.loader import load_scenario
from loadforge.dsl.scenario import registry
from loadforge.engine.coordinator import Coordinator
from loadforge.engine.scheduler import Scheduler
from loadforge.metrics.aggregator import MetricAggregator
from loadforge.metrics.models import TestResult
from loadforge.metrics.store import MetricStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from loadforge.metrics.models import MetricSnapshot
    from loadforge.patterns.base import LoadPattern

logger = get_logger("engine.runner")


class LoadTestRunner:
    """Orchestrates a distributed load test.

    Wires together: scenario loading, worker coordination, metric
    aggregation, and result generation. Provides the main ``run()``
    method that blocks until the test completes.

    Attributes:
        scenario_path: Absolute path to the scenario file.
        num_workers: Number of worker processes.
    """

    def __init__(
        self,
        scenario_path: str | Path,
        pattern: LoadPattern,
        duration_seconds: float,
        *,
        num_workers: int | None = None,
        tick_interval: float = 1.0,
        rate_limit: float | None = None,
        on_snapshot: Callable[[MetricSnapshot], None] | None = None,
        log_level: int = 20,
    ) -> None:
        """Initialize the runner.

        Args:
            scenario_path: Path to the scenario .py file.
            pattern: Traffic pattern controlling concurrency.
            duration_seconds: Total test duration in seconds.
            num_workers: Number of worker processes. Defaults to CPU count.
            tick_interval: Seconds between concurrency adjustments.
            rate_limit: Optional max requests per second (global).
            on_snapshot: Optional callback invoked with each MetricSnapshot.
            log_level: Logging level.

        Raises:
            EngineError: If the scenario file does not exist.
        """
        self.scenario_path = str(Path(scenario_path).resolve())
        self._pattern = pattern
        self._duration_seconds = duration_seconds
        self._tick_interval = tick_interval
        self._rate_limit = rate_limit
        self._on_snapshot = on_snapshot
        self._log_level = log_level

        # Determine worker count
        cpu_count = os.cpu_count() or 1
        self.num_workers = min(num_workers or cpu_count, cpu_count)
        # Don't spawn more workers than there will be users
        max_users = _get_max_concurrency(pattern, duration_seconds, tick_interval)
        if max_users > 0:
            self.num_workers = min(self.num_workers, max_users)
        self.num_workers = max(self.num_workers, 1)

        if not Path(self.scenario_path).exists():
            msg = f"Scenario file not found: {self.scenario_path}"
            raise EngineError(msg)

        self._stop_requested = False

    def _should_stop(self) -> bool:
        """Check if a stop has been requested (e.g., via signal handler)."""
        return self._stop_requested

    def run(self) -> TestResult:
        """Execute the load test and return results.

        This is a blocking call that runs until the test duration expires
        or a stop signal (SIGINT/SIGTERM) is received.

        Returns:
            TestResult containing all snapshots and the final summary.

        Raises:
            EngineError: If the test fails to execute.
        """
        setup_logging(level=self._log_level)

        # Clear registry to avoid duplicate registration when loading
        # the same scenario file multiple times (e.g., in tests)
        registry.clear()

        # Load scenario for metadata
        scenario = load_scenario(self.scenario_path)

        logger.info(
            "Starting load test: scenario=%s, workers=%d, duration=%.1fs, pattern=%s",
            scenario.name,
            self.num_workers,
            self._duration_seconds,
            self._pattern.describe(),
        )

        store = MetricStore()
        coordinator = Coordinator(
            scenario_path=self.scenario_path,
            num_workers=self.num_workers,
            duration_seconds=self._duration_seconds,
            tick_interval=self._tick_interval,
            rate_limit=self._rate_limit,
            log_level=self._log_level,
        )
        aggregator = MetricAggregator(
            metric_queues=coordinator.metric_queues,
            store=store,
            on_snapshot=self._on_snapshot,
            tick_interval=self._tick_interval,
        )

        # Install signal handlers
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        self._stop_requested = False

        def _signal_handler(signum: int, _frame: object) -> None:
            logger.info("Signal %d received, initiating graceful shutdown", signum)
            self._stop_requested = True

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        start_time = time.monotonic()

        try:
            coordinator.start()
            aggregator.start()

            scheduler = Scheduler(
                self._pattern, self._duration_seconds, self._tick_interval
            )

            for command in scheduler.iter_commands():
                if self._should_stop():
                    break

                # Wait until the right time for this tick, checking for
                # stop signal every 100ms
                target_time = start_time + command.elapsed_seconds
                now = time.monotonic()
                while target_time > now:
                    sleep_time = min(target_time - now, 0.1)
                    time.sleep(sleep_time)
                    if self._should_stop():
                        break
                    now = time.monotonic()

                if self._should_stop():
                    break

                coordinator.scale_to(command.target_concurrency)
                aggregator.set_active_users(command.target_concurrency)

        except Exception as exc:
            logger.exception("Load test failed")
            raise EngineError("Load test failed") from exc
        finally:
            # Graceful shutdown
            worker_results = coordinator.stop(timeout=10.0)
            aggregator.stop()

            # Restore signal handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

        end_time = time.monotonic()
        total_duration = end_time - start_time

        # Log worker results
        total_requests = sum(r.total_requests for r in worker_results)
        failed_workers = [r for r in worker_results if not r.success]
        if failed_workers:
            for r in failed_workers:
                logger.warning(
                    "Worker %d failed: %s", r.worker_id, r.error_message
                )

        # Build final result
        final_summary = aggregator.get_final_snapshot(elapsed_seconds=total_duration)
        snapshots = store.get_all()

        logger.info(
            "Load test completed: duration=%.1fs, total_requests=%d, "
            "avg_rps=%.1f, p95=%.1fms, error_rate=%.2f%%",
            total_duration,
            total_requests,
            final_summary.requests_per_second,
            final_summary.latency_p95,
            final_summary.error_rate * 100,
        )

        return TestResult(
            scenario_name=scenario.name,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=total_duration,
            pattern_description=self._pattern.describe(),
            snapshots=snapshots,
            final_summary=final_summary,
        )


def _get_max_concurrency(
    pattern: LoadPattern,
    duration_seconds: float,
    tick_interval: float,
) -> int:
    """Compute the maximum concurrency from a pattern.

    Args:
        pattern: Load pattern to inspect.
        duration_seconds: Test duration.
        tick_interval: Tick interval.

    Returns:
        Maximum concurrency value, or 0 if pattern yields nothing.
    """
    max_users = 0
    for _elapsed, concurrency in pattern.iter_concurrency(duration_seconds, tick_interval):
        if concurrency > max_users:
            max_users = concurrency
    return max_users
