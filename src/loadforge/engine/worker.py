"""Single-process and multi-process async workers with uvloop event loop."""

from __future__ import annotations

import asyncio
import contextlib
import queue
import random
import sys
import time
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger, setup_logging
from loadforge.dsl.http_client import HttpClient
from loadforge.engine.protocol import WorkerCommand, WorkerResult
from loadforge.engine.rate_limiter import TokenBucketRateLimiter
from loadforge.engine.session import TestSession
from loadforge.metrics.collector import MetricCollector

if TYPE_CHECKING:
    from multiprocessing import Queue as MpQueue

    from loadforge.dsl.http_client import RequestMetric
    from loadforge.dsl.scenario import ScenarioDefinition, TaskDefinition
    from loadforge.metrics.models import TestResult
    from loadforge.patterns.base import LoadPattern

logger = get_logger("engine.worker")


def _install_uvloop() -> None:
    """Install uvloop as the default event loop policy if available.

    Falls back silently to the default asyncio event loop on Windows
    or if uvloop is not installed.
    """
    if sys.platform == "win32":
        return

    try:
        import uvloop

        uvloop.install()
        logger.debug("uvloop installed as event loop policy")
    except ImportError:
        logger.debug("uvloop not available, using default asyncio event loop")


def run_worker(
    scenario: ScenarioDefinition,
    pattern: LoadPattern,
    duration_seconds: float,
    *,
    tick_interval: float = 1.0,
    rate_limit: float | None = None,
    worker_id: int = 0,
    log_level: int = 20,
) -> TestResult:
    """Execute a load test in the current process.

    This is the main entry point for Phase 3 single-worker execution.
    Installs uvloop, sets up logging, creates a TestSession, and runs
    it to completion.

    Args:
        scenario: The scenario definition to execute.
        pattern: Traffic pattern controlling concurrency.
        duration_seconds: Total test duration in seconds.
        tick_interval: Seconds between concurrency adjustments.
        rate_limit: Optional max requests per second.
        worker_id: Worker process identifier.
        log_level: Logging level (default: logging.INFO = 20).

    Returns:
        TestResult containing all snapshots and summary.

    Raises:
        EngineError: If the test fails to execute.
    """
    _install_uvloop()
    setup_logging(level=log_level)

    return asyncio.run(
        _run_session(
            scenario=scenario,
            pattern=pattern,
            duration_seconds=duration_seconds,
            tick_interval=tick_interval,
            rate_limit=rate_limit,
            worker_id=worker_id,
        )
    )


async def _run_session(
    scenario: ScenarioDefinition,
    pattern: LoadPattern,
    duration_seconds: float,
    *,
    tick_interval: float = 1.0,
    rate_limit: float | None = None,
    worker_id: int = 0,
) -> TestResult:
    """Async entry point that creates and runs a TestSession.

    Args:
        scenario: The scenario definition to execute.
        pattern: Traffic pattern controlling concurrency.
        duration_seconds: Total test duration in seconds.
        tick_interval: Seconds between concurrency adjustments.
        rate_limit: Optional max requests per second.
        worker_id: Worker process identifier.

    Returns:
        TestResult from the session execution.
    """
    session = TestSession(
        scenario=scenario,
        pattern=pattern,
        duration_seconds=duration_seconds,
        tick_interval=tick_interval,
        rate_limit=rate_limit,
        worker_id=worker_id,
    )
    return await session.run()


# =============================================================================
# Multi-process worker entry point (Phase 4)
# =============================================================================


def run_worker_process(
    scenario_path: str,
    command_queue: MpQueue[WorkerCommand],
    metric_queue: MpQueue[list[RequestMetric]],
    result_queue: MpQueue[WorkerResult],
    worker_id: int,
    duration_seconds: float,
    tick_interval: float = 1.0,
    rate_limit: float | None = None,
    log_level: int = 20,
) -> None:
    """Entry point for a worker subprocess.

    Loads the scenario from file, creates virtual users driven by
    commands from the coordinator, and sends metric batches back
    via the metric queue.

    Args:
        scenario_path: Absolute path to the scenario .py file.
        command_queue: Queue receiving WorkerCommand from coordinator.
        metric_queue: Queue for sending RequestMetric batches to aggregator.
        result_queue: Queue for sending WorkerResult on exit.
        worker_id: Worker process identifier.
        duration_seconds: Maximum test duration in seconds.
        tick_interval: Seconds between ticks.
        rate_limit: Optional max requests per second for this worker.
        log_level: Logging level.
    """
    _install_uvloop()
    setup_logging(level=log_level)

    from loadforge.dsl.loader import load_scenario

    total_requests = 0
    error_count = 0
    success = True
    error_message: str | None = None

    try:
        scenario = load_scenario(scenario_path)
        result = asyncio.run(
            _run_worker_loop(
                scenario=scenario,
                command_queue=command_queue,
                metric_queue=metric_queue,
                worker_id=worker_id,
                duration_seconds=duration_seconds,
                tick_interval=tick_interval,
                rate_limit=rate_limit,
            )
        )
        total_requests, error_count = result
    except KeyboardInterrupt:
        logger.info("Worker %d: KeyboardInterrupt, shutting down", worker_id)
    except Exception as exc:
        success = False
        error_message = str(exc)
        logger.exception("Worker %d: failed", worker_id)
    finally:
        result_queue.put(
            WorkerResult(
                worker_id=worker_id,
                total_requests=total_requests,
                error_count=error_count,
                success=success,
                error_message=error_message,
            )
        )


async def _run_worker_loop(
    scenario: ScenarioDefinition,
    command_queue: MpQueue[WorkerCommand],
    metric_queue: MpQueue[list[RequestMetric]],
    worker_id: int,
    duration_seconds: float,
    tick_interval: float,
    rate_limit: float | None,
) -> tuple[int, int]:
    """Async event loop for a managed worker process.

    Polls the command queue each tick for scale/stop commands, manages
    virtual users as asyncio tasks, and flushes metrics to the metric
    queue.

    Args:
        scenario: Loaded scenario definition.
        command_queue: Queue receiving WorkerCommand from coordinator.
        metric_queue: Queue for sending RequestMetric batches to aggregator.
        worker_id: Worker process identifier.
        duration_seconds: Maximum test duration in seconds.
        tick_interval: Seconds between ticks.
        rate_limit: Optional max requests per second.

    Returns:
        Tuple of (total_requests, error_count).
    """
    collector = MetricCollector(worker_id=worker_id)
    rate_limiter: TokenBucketRateLimiter | None = None
    if rate_limit is not None:
        rate_limiter = TokenBucketRateLimiter(rate=rate_limit)

    user_tasks: list[tuple[int, asyncio.Task[None]]] = []
    next_user_id = 0
    stop_event = asyncio.Event()
    start_time = time.monotonic()
    total_requests = 0
    total_errors = 0

    try:
        while not stop_event.is_set():
            elapsed = time.monotonic() - start_time
            if elapsed >= duration_seconds:
                break

            # Poll command queue
            while True:
                try:
                    cmd = command_queue.get_nowait()
                except (queue.Empty, EOFError):
                    break

                if cmd.kind == "stop":
                    stop_event.set()
                    break
                if cmd.kind == "scale":
                    user_tasks, next_user_id = await _scale_users(
                        target=cmd.target_concurrency,
                        user_tasks=user_tasks,
                        next_user_id=next_user_id,
                        scenario=scenario,
                        collector=collector,
                        rate_limiter=rate_limiter,
                        worker_id=worker_id,
                        stop_event=stop_event,
                    )

            if stop_event.is_set():
                break

            # Flush metrics and send batch
            snapshot = collector.flush(
                elapsed_seconds=elapsed,
                active_users=len(user_tasks),
            )
            if snapshot.total_requests > 0:
                # Send raw metrics (drained from collector) via the batch
                # We reconstruct from the snapshot counts
                total_requests += snapshot.total_requests
                total_errors += snapshot.total_errors

            # Send the raw metrics that were drained
            drained = collector.get_drained_metrics()
            if drained:
                metric_queue.put(drained)

            # Sleep until next tick
            next_tick_time = start_time + (elapsed // tick_interval + 1) * tick_interval
            sleep_time = next_tick_time - time.monotonic()
            if sleep_time > 0 and not stop_event.is_set():
                await asyncio.sleep(sleep_time)

    finally:
        await _shutdown_all_users(user_tasks, stop_event)

        # Final flush
        final_elapsed = time.monotonic() - start_time
        final_snapshot = collector.flush(
            elapsed_seconds=final_elapsed,
            active_users=0,
        )
        total_requests += final_snapshot.total_requests
        total_errors += final_snapshot.total_errors
        drained = collector.get_drained_metrics()
        if drained:
            metric_queue.put(drained)

    return total_requests, total_errors


async def _run_virtual_user(
    user_id: int,
    scenario: ScenarioDefinition,
    collector: MetricCollector,
    rate_limiter: TokenBucketRateLimiter | None,
    worker_id: int,
    stop_event: asyncio.Event,
) -> None:
    """Run a single virtual user lifecycle in a managed worker.

    Args:
        user_id: Unique identifier for this virtual user.
        scenario: Scenario definition to execute.
        collector: Metric collector for this worker.
        rate_limiter: Optional rate limiter.
        worker_id: Worker process identifier.
        stop_event: Event signaling shutdown.
    """
    instance = scenario.cls()
    async with HttpClient(
        base_url=scenario.base_url,
        headers=dict(scenario.default_headers),
        metric_callback=collector.record,
        worker_id=worker_id,
    ) as client:
        try:
            # Setup phase
            if scenario.setup_func is not None:
                await scenario.setup_func(instance, client)

            # Task loop
            while not stop_event.is_set():
                task_def = _pick_weighted_task(scenario)
                try:
                    if rate_limiter is not None:
                        await rate_limiter.acquire()
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
                min_t, max_t = scenario.think_time
                await asyncio.sleep(random.uniform(min_t, max_t))  # noqa: S311

        except asyncio.CancelledError:
            pass
        finally:
            if scenario.teardown_func is not None:
                try:
                    await scenario.teardown_func(instance, client)
                except Exception:
                    logger.warning(
                        "Teardown failed for user %d",
                        user_id,
                        exc_info=True,
                    )


def _pick_weighted_task(scenario: ScenarioDefinition) -> TaskDefinition:
    """Select a task using weighted-random distribution.

    Args:
        scenario: Scenario to pick a task from.

    Returns:
        The selected TaskDefinition.
    """
    tasks = scenario.tasks
    weights = [t.weight for t in tasks]
    return random.choices(tasks, weights=weights, k=1)[0]  # noqa: S311


async def _scale_users(
    target: int,
    user_tasks: list[tuple[int, asyncio.Task[None]]],
    next_user_id: int,
    scenario: ScenarioDefinition,
    collector: MetricCollector,
    rate_limiter: TokenBucketRateLimiter | None,
    worker_id: int,
    stop_event: asyncio.Event,
) -> tuple[list[tuple[int, asyncio.Task[None]]], int]:
    """Adjust the number of active virtual users to match target.

    Args:
        target: Desired number of active virtual users.
        user_tasks: Current list of (user_id, task) tuples.
        next_user_id: Next user ID to assign.
        scenario: Scenario definition.
        collector: Metric collector.
        rate_limiter: Optional rate limiter.
        worker_id: Worker identifier.
        stop_event: Shutdown event.

    Returns:
        Updated (user_tasks, next_user_id) tuple.
    """
    # Clean up completed tasks first
    user_tasks = [(uid, t) for uid, t in user_tasks if not t.done()]
    current = len(user_tasks)

    if target > current:
        for _ in range(target - current):
            uid = next_user_id
            next_user_id += 1
            task = asyncio.create_task(
                _run_virtual_user(
                    user_id=uid,
                    scenario=scenario,
                    collector=collector,
                    rate_limiter=rate_limiter,
                    worker_id=worker_id,
                    stop_event=stop_event,
                ),
                name=f"worker-{worker_id}-user-{uid}",
            )
            user_tasks.append((uid, task))
    elif target < current:
        to_remove = current - target
        for _ in range(to_remove):
            if user_tasks:
                _uid, task = user_tasks.pop()
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)

    return user_tasks, next_user_id


async def _shutdown_all_users(
    user_tasks: list[tuple[int, asyncio.Task[None]]],
    stop_event: asyncio.Event,
) -> None:
    """Gracefully shut down all virtual users.

    Args:
        user_tasks: List of (user_id, task) tuples.
        stop_event: Shutdown event.
    """
    stop_event.set()

    if user_tasks:
        tasks = [t for _, t in user_tasks]
        _done, pending = await asyncio.wait(tasks, timeout=5.0)

        for task in pending:
            task.cancel()

        if pending:
            await asyncio.wait(pending, timeout=2.0)

    user_tasks.clear()
    logger.debug("All virtual users shut down")
