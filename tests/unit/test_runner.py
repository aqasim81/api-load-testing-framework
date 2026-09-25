"""Unit tests for LoadTestRunner shutdown, with the coordinator and aggregator faked."""

from __future__ import annotations

import logging
import signal
from types import SimpleNamespace
from typing import ClassVar

import pytest

from loadforge._internal.errors import EngineError
from loadforge.engine import runner as runner_module
from loadforge.engine.runner import LoadTestRunner
from loadforge.patterns.constant import ConstantPattern


class SucceedingCoordinator:
    """Coordinator whose start() and stop() both succeed."""

    def __init__(self, **_kwargs: object) -> None:
        self.metric_queues: list[object] = []

    def start(self) -> None:
        return None

    def scale_to(self, target_concurrency: int) -> None:
        return None

    def stop(self, timeout: float = 10.0) -> list[object]:
        return []


class StopFailingCoordinator(SucceedingCoordinator):
    """Coordinator whose start() succeeds and whose stop() fails."""

    def stop(self, timeout: float = 10.0) -> list[object]:
        msg = "stop failed"
        raise RuntimeError(msg)


class FailingCoordinator(StopFailingCoordinator):
    """Coordinator whose start() and stop() both fail."""

    def start(self) -> None:
        msg = "start failed"
        raise RuntimeError(msg)


class RecordingAggregator:
    """Aggregator that records whether stop() was called."""

    instances: ClassVar[list[RecordingAggregator]] = []

    def __init__(self, **_kwargs: object) -> None:
        self.stopped = False
        RecordingAggregator.instances.append(self)

    def start(self) -> None:
        return None

    def set_active_users(self, count: int) -> None:
        return None

    def stop(self) -> None:
        self.stopped = True


class StopFailingAggregator(RecordingAggregator):
    """Aggregator whose stop() records the call and then fails."""

    def stop(self) -> None:
        self.stopped = True
        msg = "aggregator stop failed"
        raise RuntimeError(msg)


def _make_runner(
    monkeypatch: pytest.MonkeyPatch,
    coordinator_cls: type[object],
    aggregator_cls: type[RecordingAggregator] = RecordingAggregator,
) -> LoadTestRunner:
    """Build a runner wired to the given fake coordinator and recording aggregator."""
    RecordingAggregator.instances.clear()
    monkeypatch.setattr(runner_module, "Coordinator", coordinator_cls)
    monkeypatch.setattr(runner_module, "MetricAggregator", aggregator_cls)
    monkeypatch.setattr(runner_module, "load_scenario", lambda _path: SimpleNamespace(name="fake"))
    monkeypatch.setattr(runner_module, "setup_logging", lambda level: None)
    return LoadTestRunner(
        scenario_path=__file__,
        pattern=ConstantPattern(users=1),
        duration_seconds=0.01,
        tick_interval=0.01,
        num_workers=1,
    )


class TestLoadTestRunnerShutdown:
    """Tests for cleanup and error reporting in LoadTestRunner.run() when shutdown fails."""

    def test_run_wraps_coordinator_stop_failure_in_engine_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = _make_runner(monkeypatch, StopFailingCoordinator)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with pytest.raises(EngineError, match="Worker shutdown failed") as exc_info:
            runner.run()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == "stop failed"
        assert RecordingAggregator.instances[0].stopped is True
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm

    def test_run_keeps_original_error_when_coordinator_stop_also_raises(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        runner = _make_runner(monkeypatch, FailingCoordinator)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(EngineError, match="Load test failed") as exc_info,
        ):
            runner.run()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == "start failed"
        assert "Worker shutdown failed" in caplog.text
        assert RecordingAggregator.instances[0].stopped is True
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm

    def test_run_wraps_aggregator_stop_failure_in_engine_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = _make_runner(monkeypatch, SucceedingCoordinator, StopFailingAggregator)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with pytest.raises(EngineError, match="Metric aggregator shutdown failed") as exc_info:
            runner.run()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == "aggregator stop failed"
        assert RecordingAggregator.instances[0].stopped is True
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm

    def test_run_keeps_original_error_when_aggregator_stop_also_raises(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        runner = _make_runner(monkeypatch, FailingCoordinator, StopFailingAggregator)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(EngineError, match="Load test failed") as exc_info,
        ):
            runner.run()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == "start failed"
        assert "Worker shutdown failed" in caplog.text
        assert "Metric aggregator shutdown failed" in caplog.text
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm

    def test_run_keeps_worker_shutdown_error_when_aggregator_stop_also_raises(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        runner = _make_runner(monkeypatch, StopFailingCoordinator, StopFailingAggregator)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(EngineError, match="Worker shutdown failed") as exc_info,
        ):
            runner.run()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert str(exc_info.value.__cause__) == "stop failed"
        assert "Metric aggregator shutdown failed" in caplog.text
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm
