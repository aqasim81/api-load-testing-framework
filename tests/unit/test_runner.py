"""Unit tests for LoadTestRunner shutdown, with the coordinator and aggregator faked."""

from __future__ import annotations

import signal
from types import SimpleNamespace
from typing import ClassVar

import pytest

from loadforge._internal.errors import EngineError
from loadforge.engine import runner as runner_module
from loadforge.engine.runner import LoadTestRunner
from loadforge.patterns.constant import ConstantPattern


class FailingCoordinator:
    """Coordinator whose start() and stop() both fail."""

    def __init__(self, **_kwargs: object) -> None:
        self.metric_queues: list[object] = []

    def start(self) -> None:
        msg = "start failed"
        raise RuntimeError(msg)

    def stop(self, timeout: float = 10.0) -> list[object]:
        msg = "stop failed"
        raise RuntimeError(msg)


class RecordingAggregator:
    """Aggregator that records whether stop() was called."""

    instances: ClassVar[list[RecordingAggregator]] = []

    def __init__(self, **_kwargs: object) -> None:
        self.stopped = False
        RecordingAggregator.instances.append(self)

    def start(self) -> None:
        return None

    def stop(self) -> None:
        self.stopped = True


class TestLoadTestRunnerShutdown:
    """Tests for cleanup in LoadTestRunner.run() when shutdown fails."""

    def test_run_cleans_up_when_coordinator_stop_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        RecordingAggregator.instances.clear()
        monkeypatch.setattr(runner_module, "Coordinator", FailingCoordinator)
        monkeypatch.setattr(runner_module, "MetricAggregator", RecordingAggregator)
        monkeypatch.setattr(
            runner_module, "load_scenario", lambda _path: SimpleNamespace(name="fake")
        )
        monkeypatch.setattr(runner_module, "setup_logging", lambda level: None)
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        runner = LoadTestRunner(
            scenario_path=__file__,
            pattern=ConstantPattern(users=1),
            duration_seconds=1.0,
            num_workers=1,
        )

        with pytest.raises(RuntimeError, match="stop failed") as exc_info:
            runner.run()

        assert isinstance(exc_info.value.__context__, EngineError)
        assert RecordingAggregator.instances[0].stopped is True
        assert signal.getsignal(signal.SIGINT) is original_sigint
        assert signal.getsignal(signal.SIGTERM) is original_sigterm
