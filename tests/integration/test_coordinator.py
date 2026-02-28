"""Integration tests for the multi-process Coordinator."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from loadforge.engine.coordinator import Coordinator
from loadforge.metrics.aggregator import MetricAggregator
from loadforge.metrics.store import MetricStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.timeout(30)
class TestCoordinator:
    def test_spawns_workers_and_runs_to_completion(
        self, scenario_file: Path
    ):
        coordinator = Coordinator(
            scenario_path=str(scenario_file),
            num_workers=2,
            duration_seconds=3.0,
            tick_interval=0.5,
        )
        store = MetricStore()
        aggregator = MetricAggregator(
            coordinator.metric_queues, store, tick_interval=0.5
        )

        coordinator.start()
        aggregator.start()

        # Scale to 4 users (2 per worker)
        coordinator.scale_to(4)
        time.sleep(2.0)

        # Stop aggregator before coordinator to avoid reading closed queues
        aggregator.stop()
        results = coordinator.stop()

        assert len(results) == 2
        assert all(r.success for r in results)
        assert len(store) >= 1

    def test_distributes_concurrency_evenly(
        self, scenario_file: Path
    ):
        coordinator = Coordinator(
            scenario_path=str(scenario_file),
            num_workers=2,
            duration_seconds=3.0,
            tick_interval=0.5,
        )
        store = MetricStore()
        aggregator = MetricAggregator(
            coordinator.metric_queues, store, tick_interval=0.5
        )

        coordinator.start()
        aggregator.start()

        # Scale to 5 users — worker 0 gets 3, worker 1 gets 2
        coordinator.scale_to(5)
        time.sleep(2.0)

        aggregator.stop()
        results = coordinator.stop()

        total_requests = sum(r.total_requests for r in results)
        assert total_requests > 0

    def test_graceful_stop(self, scenario_file: Path):
        coordinator = Coordinator(
            scenario_path=str(scenario_file),
            num_workers=2,
            duration_seconds=30.0,  # Long duration
            tick_interval=0.5,
        )

        coordinator.start()
        coordinator.scale_to(4)
        time.sleep(1.0)

        # Stop well before duration expires
        results = coordinator.stop(timeout=10.0)

        assert len(results) == 2
        assert not coordinator.is_alive

    def test_zero_concurrency(self, scenario_file: Path):
        coordinator = Coordinator(
            scenario_path=str(scenario_file),
            num_workers=2,
            duration_seconds=3.0,
            tick_interval=0.5,
        )

        coordinator.start()
        # Don't scale to any users
        time.sleep(1.0)

        results = coordinator.stop()
        assert len(results) == 2
        # Workers should exit cleanly even with 0 users
        assert all(r.success for r in results)
