"""Single-process async worker with uvloop event loop."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger, setup_logging
from loadforge.engine.session import TestSession

if TYPE_CHECKING:
    from loadforge.dsl.scenario import ScenarioDefinition
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
