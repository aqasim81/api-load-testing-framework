"""Unit tests for Coordinator.stop() using fake queues and processes."""

from __future__ import annotations

import queue

import pytest

from loadforge.engine.coordinator import Coordinator
from loadforge.engine.protocol import WorkerCommand, WorkerResult


class FakeQueue:
    """Stand-in for a multiprocessing queue: records puts, scripts get()."""

    def __init__(self, get_outcome: object = None) -> None:
        self.items: list[object] = []
        self.closed = False
        self.close_error: OSError | None = None
        self._get_outcome = get_outcome

    def put(self, item: object) -> None:
        self.items.append(item)

    def get(self, timeout: float | None = None) -> object:
        if isinstance(self._get_outcome, BaseException):
            raise self._get_outcome
        return self._get_outcome

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeProcess:
    """Stand-in for a worker process."""

    def __init__(self, name: str, *, hangs: bool = False) -> None:
        self.name = name
        self.terminated = False
        self._hangs = hangs

    def join(self, timeout: float | None = None) -> None:
        return None

    def is_alive(self) -> bool:
        return self._hangs and not self.terminated

    def terminate(self) -> None:
        self.terminated = True


def _make_coordinator(
    result_outcomes: list[object],
    *,
    processes: list[FakeProcess] | None = None,
) -> tuple[Coordinator, list[FakeQueue]]:
    """Build a Coordinator wired to fakes; returns it and all its fake queues."""
    n = len(result_outcomes)
    coordinator = Coordinator("scenario.py", num_workers=n, duration_seconds=1.0)
    command_queues = [FakeQueue() for _ in range(n)]
    metric_queues = [FakeQueue() for _ in range(n)]
    result_queues = [FakeQueue(outcome) for outcome in result_outcomes]
    coordinator._command_queues = command_queues  # type: ignore[assignment]
    coordinator._metric_queues = metric_queues  # type: ignore[assignment]
    coordinator._result_queues = result_queues  # type: ignore[assignment]
    coordinator._processes = processes or [  # type: ignore[assignment]
        FakeProcess(f"loadforge-worker-{i}") for i in range(n)
    ]
    return coordinator, command_queues + metric_queues + result_queues


def _ok(worker_id: int) -> WorkerResult:
    return WorkerResult(worker_id=worker_id, total_requests=10, error_count=1, success=True)


class TestCoordinatorStop:
    """Tests for Coordinator.stop() result collection and cleanup."""

    def test_stop_returns_worker_results_in_order(self) -> None:
        coordinator, queues = _make_coordinator([_ok(0), _ok(1)])

        results = coordinator.stop()

        assert results == [_ok(0), _ok(1)]
        for cmd_q in coordinator._command_queues:
            assert cmd_q.items == [WorkerCommand(kind="stop")]  # type: ignore[attr-defined]
        assert all(q.closed for q in queues)

    def test_stop_records_failure_when_result_missing(self) -> None:
        coordinator, queues = _make_coordinator([_ok(0), queue.Empty()])

        results = coordinator.stop()

        assert results[0] == _ok(0)
        assert results[1] == WorkerResult(
            worker_id=1,
            total_requests=0,
            error_count=0,
            success=False,
            error_message="No result received",
        )
        assert all(q.closed for q in queues)

    @pytest.mark.parametrize("error", [EOFError(), OSError("handle is closed")])
    def test_stop_records_failure_when_result_pipe_broken(self, error: Exception) -> None:
        coordinator, queues = _make_coordinator([error, _ok(1)])

        results = coordinator.stop()

        assert results[0].worker_id == 0
        assert results[0].success is False
        assert results[0].error_message is not None
        assert results[0].error_message.startswith("Result pipe broken:")
        assert results[1] == _ok(1)
        assert all(q.closed for q in queues)

    def test_stop_propagates_unexpected_error_and_closes_queues(self) -> None:
        coordinator, queues = _make_coordinator([_ok(0), RuntimeError("bug")])

        with pytest.raises(RuntimeError, match="bug"):
            coordinator.stop()

        assert all(q.closed for q in queues)

    def test_stop_closes_remaining_queues_when_one_close_fails(self) -> None:
        coordinator, queues = _make_coordinator([_ok(0), _ok(1)])
        queues[0].close_error = OSError("close failed")

        results = coordinator.stop()

        assert results == [_ok(0), _ok(1)]
        assert all(q.closed for q in queues[1:])

    def test_stop_keeps_unexpected_error_when_close_also_fails(self) -> None:
        coordinator, queues = _make_coordinator([RuntimeError("bug"), _ok(1)])
        queues[0].close_error = OSError("close failed")

        with pytest.raises(RuntimeError, match="bug"):
            coordinator.stop()

        assert all(q.closed for q in queues[1:])

    def test_stop_terminates_worker_that_does_not_exit(self) -> None:
        hung = FakeProcess("loadforge-worker-0", hangs=True)
        coordinator, _ = _make_coordinator([_ok(0)], processes=[hung])

        coordinator.stop()

        assert hung.terminated is True
