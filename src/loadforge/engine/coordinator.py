"""Multi-process worker coordinator for distributed load testing."""

from __future__ import annotations

import multiprocessing
import multiprocessing.process
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger
from loadforge.engine.protocol import WorkerCommand, WorkerResult
from loadforge.engine.worker import run_worker_process

if TYPE_CHECKING:
    from multiprocessing import Queue as MpQueue

    from loadforge.dsl.http_client import RequestMetric

logger = get_logger("engine.coordinator")


class Coordinator:
    """Manages the lifecycle of N worker processes.

    Spawns worker processes, distributes concurrency targets across
    them, and handles graceful shutdown. Each worker gets its own
    set of queues for commands, metrics, and results.

    Attributes:
        num_workers: Number of worker processes.
        scenario_path: Absolute path to the scenario file.
    """

    def __init__(
        self,
        scenario_path: str,
        num_workers: int,
        duration_seconds: float,
        *,
        tick_interval: float = 1.0,
        rate_limit: float | None = None,
        log_level: int = 20,
    ) -> None:
        """Initialize the coordinator.

        Args:
            scenario_path: Absolute path to the scenario .py file.
            num_workers: Number of worker processes to spawn.
            duration_seconds: Maximum test duration in seconds.
            tick_interval: Seconds between ticks.
            rate_limit: Optional global max RPS (divided across workers).
            log_level: Logging level for workers.
        """
        self.scenario_path = scenario_path
        self.num_workers = num_workers
        self._duration_seconds = duration_seconds
        self._tick_interval = tick_interval
        self._rate_limit = rate_limit
        self._log_level = log_level

        self._ctx = multiprocessing.get_context("spawn")

        # Per-worker queues
        self._command_queues: list[MpQueue[WorkerCommand]] = []
        self._metric_queues: list[MpQueue[list[RequestMetric]]] = []
        self._result_queues: list[MpQueue[WorkerResult]] = []
        self._processes: list[multiprocessing.process.BaseProcess] = []
        self._current_targets: list[int] = [0] * num_workers

    @property
    def metric_queues(self) -> list[MpQueue[list[RequestMetric]]]:
        """Return the per-worker metric queues for the aggregator."""
        return self._metric_queues

    @property
    def is_alive(self) -> bool:
        """Return True if any worker process is still running."""
        return any(p.is_alive() for p in self._processes)

    def start(self) -> None:
        """Spawn all worker processes.

        Each worker re-imports the scenario file and begins listening
        for commands on its command queue.
        """
        per_worker_rate = (
            self._rate_limit / self.num_workers
            if self._rate_limit is not None
            else None
        )

        for i in range(self.num_workers):
            cmd_q: MpQueue[WorkerCommand] = self._ctx.Queue()
            metric_q: MpQueue[list[RequestMetric]] = self._ctx.Queue()
            result_q: MpQueue[WorkerResult] = self._ctx.Queue()

            self._command_queues.append(cmd_q)
            self._metric_queues.append(metric_q)
            self._result_queues.append(result_q)

            process = self._ctx.Process(
                target=run_worker_process,
                args=(
                    self.scenario_path,
                    cmd_q,
                    metric_q,
                    result_q,
                    i,  # worker_id
                    self._duration_seconds,
                    self._tick_interval,
                    per_worker_rate,
                    self._log_level,
                ),
                name=f"loadforge-worker-{i}",
                daemon=False,
            )
            self._processes.append(process)

        for p in self._processes:
            p.start()
            logger.debug("Started worker process: pid=%d, name=%s", p.pid or 0, p.name)

        logger.info("Started %d worker processes", self.num_workers)

    def scale_to(self, target_concurrency: int) -> None:
        """Distribute a global concurrency target across all workers.

        Divides ``target_concurrency`` evenly across workers. The first
        worker receives any remainder.

        Args:
            target_concurrency: Total desired virtual users across all workers.
        """
        base = target_concurrency // self.num_workers
        remainder = target_concurrency % self.num_workers

        for i in range(self.num_workers):
            per_worker = base + (remainder if i == 0 else 0)
            if per_worker != self._current_targets[i]:
                self._current_targets[i] = per_worker
                self._command_queues[i].put(
                    WorkerCommand(kind="scale", target_concurrency=per_worker)
                )

    def stop(self, timeout: float = 10.0) -> list[WorkerResult]:
        """Send stop commands and wait for all workers to exit.

        Args:
            timeout: Maximum seconds to wait for each worker to join.

        Returns:
            List of WorkerResult from all workers.
        """
        # Send stop commands
        for cmd_q in self._command_queues:
            cmd_q.put(WorkerCommand(kind="stop"))

        results: list[WorkerResult] = []

        # Wait for processes to finish
        for p in self._processes:
            p.join(timeout=timeout)
            if p.is_alive():
                logger.warning(
                    "Worker %s did not exit in time, terminating", p.name
                )
                p.terminate()
                p.join(timeout=2.0)

        # Collect results
        for i, result_q in enumerate(self._result_queues):
            try:
                result = result_q.get(timeout=2.0)
                results.append(result)
            except Exception:
                logger.warning("No result from worker %d", i)
                results.append(
                    WorkerResult(
                        worker_id=i,
                        total_requests=0,
                        error_count=0,
                        success=False,
                        error_message="No result received",
                    )
                )

        # Close queues
        for q_list in (self._command_queues, self._metric_queues, self._result_queues):
            for q in q_list:
                q.close()

        logger.info("All %d workers stopped", self.num_workers)
        return results
