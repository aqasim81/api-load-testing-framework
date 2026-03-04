"""Unit tests for the SnapshotBroadcaster."""

from __future__ import annotations

import asyncio
import json
import threading

from loadforge.dashboard.broadcaster import SnapshotBroadcaster, _serialize_snapshot
from loadforge.metrics.models import EndpointMetrics
from tests.conftest import make_snapshot


class TestSerializeSnapshot:
    """Tests for the _serialize_snapshot helper."""

    def test_top_level_structure(self) -> None:
        snapshot = make_snapshot()
        result = json.loads(_serialize_snapshot(snapshot))

        assert result["type"] == "snapshot"
        assert "data" in result

    def test_data_fields(self) -> None:
        snapshot = make_snapshot()
        data = json.loads(_serialize_snapshot(snapshot))["data"]

        assert data["timestamp"] == 1000.0
        assert data["elapsed_seconds"] == 10.0
        assert data["active_users"] == 50
        assert data["rps"] == 50.0
        assert data["total_requests"] == 500

    def test_latency_nested_object(self) -> None:
        snapshot = make_snapshot()
        latency = json.loads(_serialize_snapshot(snapshot))["data"]["latency"]

        assert latency["p50"] == 10.0
        assert latency["p95"] == 50.0
        assert latency["p99"] == 100.0
        assert latency["p999"] == 180.0
        assert latency["min"] == 1.0
        assert latency["max"] == 200.0
        assert latency["avg"] == 15.0

    def test_errors_object(self) -> None:
        snapshot = make_snapshot()
        errors = json.loads(_serialize_snapshot(snapshot))["data"]["errors"]

        assert errors["total"] == 5
        assert errors["rate"] == 0.01
        assert errors["by_status"] == {"500": 3, "503": 2}

    def test_endpoints_as_list(self) -> None:
        snapshot = make_snapshot()
        endpoints = json.loads(_serialize_snapshot(snapshot))["data"]["endpoints"]

        assert isinstance(endpoints, list)
        assert len(endpoints) == 1
        ep = endpoints[0]
        assert ep["name"] == "List Items"
        assert ep["rps"] == 30.0
        assert ep["request_count"] == 300
        assert ep["error_count"] == 2
        assert ep["p50"] == 8.0
        assert ep["p95"] == 40.0

    def test_multiple_endpoints(self) -> None:
        endpoints = {
            "List Items": EndpointMetrics(
                name="List Items",
                request_count=300,
                error_count=2,
                error_rate=0.0067,
                requests_per_second=30.0,
                latency_min=1.0,
                latency_max=150.0,
                latency_avg=12.0,
                latency_p50=8.0,
                latency_p75=16.0,
                latency_p90=25.0,
                latency_p95=40.0,
                latency_p99=90.0,
            ),
            "Create Item": EndpointMetrics(
                name="Create Item",
                request_count=200,
                error_count=3,
                error_rate=0.015,
                requests_per_second=20.0,
                latency_min=5.0,
                latency_max=300.0,
                latency_avg=25.0,
                latency_p50=18.0,
                latency_p75=30.0,
                latency_p90=50.0,
                latency_p95=80.0,
                latency_p99=200.0,
            ),
        }
        snapshot = make_snapshot(endpoints=endpoints)
        result = json.loads(_serialize_snapshot(snapshot))["data"]["endpoints"]

        assert len(result) == 2
        names = {ep["name"] for ep in result}
        assert names == {"List Items", "Create Item"}

        create = next(ep for ep in result if ep["name"] == "Create Item")
        assert create["rps"] == 20.0
        assert create["request_count"] == 200
        assert create["error_count"] == 3
        assert create["p50"] == 18.0
        assert create["p99"] == 200.0

    def test_empty_endpoints(self) -> None:
        snapshot = make_snapshot(endpoints={})
        data = json.loads(_serialize_snapshot(snapshot))["data"]

        assert data["endpoints"] == []

    def test_empty_errors(self) -> None:
        snapshot = make_snapshot(
            total_errors=0,
            error_rate=0.0,
            errors_by_status={},
        )
        errors = json.loads(_serialize_snapshot(snapshot))["data"]["errors"]

        assert errors["total"] == 0
        assert errors["rate"] == 0.0
        assert errors["by_status"] == {}


class TestSnapshotBroadcaster:
    """Tests for the SnapshotBroadcaster class."""

    def test_initial_state(self) -> None:
        broadcaster = SnapshotBroadcaster()
        assert broadcaster.client_count == 0

    def test_subscribe_unsubscribe(self) -> None:
        broadcaster = SnapshotBroadcaster()
        loop = asyncio.new_event_loop()
        broadcaster.set_loop(loop)

        try:
            q1 = loop.run_until_complete(_subscribe_async(broadcaster))
            q2 = loop.run_until_complete(_subscribe_async(broadcaster))
            assert broadcaster.client_count == 2

            broadcaster.unsubscribe(q1)
            assert broadcaster.client_count == 1

            broadcaster.unsubscribe(q2)
            assert broadcaster.client_count == 0
        finally:
            loop.close()

    def test_unsubscribe_idempotent(self) -> None:
        broadcaster = SnapshotBroadcaster()
        loop = asyncio.new_event_loop()
        broadcaster.set_loop(loop)

        try:
            q = loop.run_until_complete(_subscribe_async(broadcaster))
            broadcaster.unsubscribe(q)
            broadcaster.unsubscribe(q)  # Should not raise
            assert broadcaster.client_count == 0
        finally:
            loop.close()

    def test_on_snapshot_without_loop_is_noop(self) -> None:
        broadcaster = SnapshotBroadcaster()
        snapshot = make_snapshot()
        # Should not raise
        broadcaster.on_snapshot(snapshot)

    def test_on_snapshot_fans_out(self) -> None:
        broadcaster = SnapshotBroadcaster()
        loop = asyncio.new_event_loop()
        broadcaster.set_loop(loop)

        try:
            q1 = loop.run_until_complete(_subscribe_async(broadcaster))
            q2 = loop.run_until_complete(_subscribe_async(broadcaster))

            snapshot = make_snapshot()
            broadcaster.on_snapshot(snapshot)

            # Process the call_soon_threadsafe callbacks
            loop.run_until_complete(_drain_loop(loop))

            assert not q1.empty()
            assert not q2.empty()

            msg1 = q1.get_nowait()
            msg2 = q2.get_nowait()
            assert msg1 == msg2

            parsed = json.loads(msg1)
            assert parsed["type"] == "snapshot"
            assert parsed["data"]["active_users"] == 50
        finally:
            loop.close()

    def test_on_snapshot_drops_when_queue_full(self) -> None:
        broadcaster = SnapshotBroadcaster()
        loop = asyncio.new_event_loop()
        broadcaster.set_loop(loop)

        try:
            q = loop.run_until_complete(_subscribe_async(broadcaster))

            snapshot = make_snapshot()

            # Fill the queue
            for _ in range(50):
                broadcaster.on_snapshot(snapshot)
                loop.run_until_complete(_drain_loop(loop))

            assert q.full()

            # This should silently drop (no exception)
            broadcaster.on_snapshot(snapshot)
        finally:
            loop.close()

    def test_on_snapshot_from_another_thread(self) -> None:
        broadcaster = SnapshotBroadcaster()
        loop = asyncio.new_event_loop()
        broadcaster.set_loop(loop)

        try:
            q = loop.run_until_complete(_subscribe_async(broadcaster))
            snapshot = make_snapshot()

            received: list[str] = []

            def _sender() -> None:
                broadcaster.on_snapshot(snapshot)

            thread = threading.Thread(target=_sender)
            thread.start()
            thread.join(timeout=2.0)

            # Process pending callbacks
            loop.run_until_complete(_drain_loop(loop))

            assert not q.empty()
            msg = q.get_nowait()
            received.append(msg)

            parsed = json.loads(received[0])
            assert parsed["type"] == "snapshot"
        finally:
            loop.close()


async def _subscribe_async(broadcaster: SnapshotBroadcaster) -> asyncio.Queue[str]:
    """Subscribe within the event loop context."""
    return broadcaster.subscribe()


async def _drain_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Give the event loop a chance to process call_soon_threadsafe callbacks."""
    await asyncio.sleep(0.01)
