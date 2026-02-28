"""Integration tests for the LoadTestRunner."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from loadforge.engine.runner import LoadTestRunner
from loadforge.metrics.models import MetricSnapshot
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.ramp import RampPattern

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.timeout(30)
class TestLoadTestRunner:
    def test_run_with_constant_pattern(self, scenario_file: Path):
        runner = LoadTestRunner(
            scenario_path=scenario_file,
            pattern=ConstantPattern(users=4),
            duration_seconds=3.0,
            num_workers=2,
            tick_interval=0.5,
        )

        result = runner.run()

        assert result.scenario_name == "Integration Test Scenario"
        assert result.duration_seconds >= 2.0
        assert len(result.snapshots) >= 1
        assert result.final_summary is not None
        assert result.final_summary.total_requests > 0

    def test_run_with_ramp_pattern(self, scenario_file: Path):
        runner = LoadTestRunner(
            scenario_path=scenario_file,
            pattern=RampPattern(start_users=1, end_users=6, ramp_duration=2.0),
            duration_seconds=3.0,
            num_workers=2,
            tick_interval=0.5,
        )

        result = runner.run()

        assert result.duration_seconds >= 2.0
        assert result.final_summary is not None
        assert result.final_summary.total_requests > 0

    def test_on_snapshot_callback(self, scenario_file: Path):
        callbacks: list[MetricSnapshot] = []

        runner = LoadTestRunner(
            scenario_path=scenario_file,
            pattern=ConstantPattern(users=2),
            duration_seconds=3.0,
            num_workers=1,
            tick_interval=0.5,
            on_snapshot=callbacks.append,
        )

        result = runner.run()

        assert len(callbacks) >= 1
        assert result.final_summary is not None

    def test_single_worker_mode(self, scenario_file: Path):
        runner = LoadTestRunner(
            scenario_path=scenario_file,
            pattern=ConstantPattern(users=2),
            duration_seconds=2.0,
            num_workers=1,
            tick_interval=0.5,
        )

        result = runner.run()

        assert result.final_summary is not None
        assert result.final_summary.total_requests > 0

    def test_invalid_scenario_raises(self, tmp_path: Path):
        with pytest.raises(Exception, match="not found"):
            LoadTestRunner(
                scenario_path=tmp_path / "nonexistent.py",
                pattern=ConstantPattern(users=1),
                duration_seconds=1.0,
            )
