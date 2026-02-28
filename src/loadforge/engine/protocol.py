"""Protocol types for inter-process communication between coordinator and workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WorkerCommand:
    """Command sent from coordinator to a worker process.

    Attributes:
        kind: Command type — "scale" adjusts concurrency, "stop" triggers shutdown.
        target_concurrency: Desired number of virtual users for this worker.
            Only relevant when kind is "scale".
    """

    kind: Literal["scale", "stop"]
    target_concurrency: int = 0


@dataclass(frozen=True)
class WorkerResult:
    """Result sent from a worker process back to the coordinator on exit.

    Attributes:
        worker_id: Identifier of the worker that produced this result.
        total_requests: Total HTTP requests made by this worker.
        error_count: Number of failed requests.
        success: Whether the worker exited cleanly.
        error_message: Error description if the worker failed.
    """

    worker_id: int
    total_requests: int
    error_count: int
    success: bool
    error_message: str | None = None
