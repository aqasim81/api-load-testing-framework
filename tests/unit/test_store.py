"""Tests for MetricStore."""

from __future__ import annotations

import time

from loadforge.metrics.models import MetricSnapshot
from loadforge.metrics.store import MetricStore


def _make_snapshot(elapsed: float, rps: float = 0.0) -> MetricSnapshot:
    return MetricSnapshot(
        timestamp=time.monotonic(),
        elapsed_seconds=elapsed,
        active_users=10,
        requests_per_second=rps,
    )


class TestMetricStore:
    def test_empty_store(self):
        store = MetricStore()
        assert len(store) == 0
        assert store.get_all() == []
        assert store.get_latest() is None

    def test_append_and_get_all(self):
        store = MetricStore()
        s1 = _make_snapshot(1.0)
        s2 = _make_snapshot(2.0)
        store.append(s1)
        store.append(s2)

        all_snapshots = store.get_all()
        assert len(all_snapshots) == 2
        assert all_snapshots[0] is s1
        assert all_snapshots[1] is s2

    def test_get_all_returns_copy(self):
        store = MetricStore()
        store.append(_make_snapshot(1.0))

        result = store.get_all()
        result.clear()

        assert len(store) == 1

    def test_get_latest_returns_last(self):
        store = MetricStore()
        s1 = _make_snapshot(1.0)
        s2 = _make_snapshot(2.0)
        store.append(s1)
        store.append(s2)

        assert store.get_latest() is s2

    def test_len(self):
        store = MetricStore()
        assert len(store) == 0

        store.append(_make_snapshot(1.0))
        assert len(store) == 1

        store.append(_make_snapshot(2.0))
        store.append(_make_snapshot(3.0))
        assert len(store) == 3
