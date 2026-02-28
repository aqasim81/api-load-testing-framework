"""Shared virtual user utilities for single-worker and multi-worker engines.

Provides common functions used by both ``TestSession`` (Phase 3) and
``run_worker_process`` (Phase 4) to avoid code duplication.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger

if TYPE_CHECKING:
    from loadforge.dsl.scenario import TaskDefinition

logger = get_logger("engine.user_utils")


def pick_weighted_task(tasks: list[TaskDefinition]) -> TaskDefinition:
    """Select a task using weighted-random distribution.

    Args:
        tasks: List of task definitions to choose from.

    Returns:
        The selected TaskDefinition.
    """
    weights = [t.weight for t in tasks]
    return random.choices(tasks, weights=weights, k=1)[0]  # noqa: S311


async def shutdown_all_users(
    user_tasks: list[tuple[int, asyncio.Task[None]]],
    stop_event: asyncio.Event,
) -> None:
    """Gracefully shut down all virtual users.

    Sets the stop event, waits up to 5 seconds for tasks to finish,
    then cancels any remaining tasks and waits for cancellation.

    Args:
        user_tasks: List of (user_id, task) tuples to shut down.
        stop_event: Event to signal shutdown to running users.
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
