"""Integration tests for the live dashboard server and WebSocket streaming."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import aiohttp
import pytest

from loadforge.dashboard.broadcaster import SnapshotBroadcaster
from loadforge.dashboard.server import DashboardServer, create_app
from loadforge.metrics.models import EndpointMetrics, MetricSnapshot
from tests.conftest import _get_free_port

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_snapshot(**overrides: object) -> MetricSnapshot:
    """Create a MetricSnapshot with sensible defaults."""
    defaults: dict[str, object] = {
        "timestamp": 1000.0,
        "elapsed_seconds": 10.0,
        "active_users": 50,
        "total_requests": 500,
        "requests_per_second": 50.0,
        "latency_min": 1.0,
        "latency_max": 200.0,
        "latency_avg": 15.0,
        "latency_p50": 10.0,
        "latency_p75": 20.0,
        "latency_p90": 30.0,
        "latency_p95": 50.0,
        "latency_p99": 100.0,
        "latency_p999": 180.0,
        "total_errors": 5,
        "error_rate": 0.01,
        "errors_by_status": {500: 3, 503: 2},
        "errors_by_type": {"ConnectionError": 2},
        "endpoints": {
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
        },
    }
    defaults.update(overrides)
    return MetricSnapshot(**defaults)  # type: ignore[arg-type]


@pytest.fixture
async def dashboard(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[DashboardServer, SnapshotBroadcaster, int]]:
    """Start a dashboard server on a free port and yield (server, broadcaster, port)."""
    port = _get_free_port()
    broadcaster = SnapshotBroadcaster()
    app = create_app(broadcaster)
    server = DashboardServer(app, broadcaster, port)
    server.start()
    try:
        yield server, broadcaster, port
    finally:
        server.stop()


async def test_health_endpoint(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    _server, _, port = dashboard
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"http://localhost:{port}/api/health") as resp,
    ):
        assert resp.status == 200
        data = await resp.json()
        assert data == {"status": "ok"}


async def test_websocket_connect_and_receive(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    _, broadcaster, port = dashboard
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(f"http://localhost:{port}/ws/metrics") as ws,
    ):
        snapshot = _make_snapshot()
        broadcaster.on_snapshot(snapshot)

        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
        assert msg.type == aiohttp.WSMsgType.TEXT

        data = json.loads(msg.data)
        assert data["type"] == "snapshot"
        assert data["data"]["active_users"] == 50
        assert data["data"]["rps"] == 50.0


async def test_websocket_multiple_clients(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    _, broadcaster, port = dashboard
    url = f"http://localhost:{port}/ws/metrics"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws1,
        session.ws_connect(url) as ws2,
    ):
        assert broadcaster.client_count == 2

        snapshot = _make_snapshot(active_users=42)
        broadcaster.on_snapshot(snapshot)

        msg1 = await asyncio.wait_for(ws1.receive(), timeout=5.0)
        msg2 = await asyncio.wait_for(ws2.receive(), timeout=5.0)

        data1 = json.loads(msg1.data)
        data2 = json.loads(msg2.data)

        assert data1["data"]["active_users"] == 42
        assert data2["data"]["active_users"] == 42


async def test_websocket_disconnect_cleanup(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    _, broadcaster, port = dashboard
    async with aiohttp.ClientSession() as session:
        ws = await session.ws_connect(f"http://localhost:{port}/ws/metrics")
        assert broadcaster.client_count == 1

        await ws.close()

        # The server-side handler unsubscribes when it detects the
        # disconnect (on its next send attempt or read).  Send a snapshot
        # to trigger the server to attempt a write, then wait.
        snapshot = _make_snapshot()
        broadcaster.on_snapshot(snapshot)
        await asyncio.sleep(0.5)
        assert broadcaster.client_count == 0


async def test_message_format_validation(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    _, broadcaster, port = dashboard
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(f"http://localhost:{port}/ws/metrics") as ws,
    ):
        snapshot = _make_snapshot()
        broadcaster.on_snapshot(snapshot)

        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
        data = json.loads(msg.data)

        # Validate top-level structure
        assert data["type"] == "snapshot"
        payload = data["data"]

        # Validate all required fields
        assert isinstance(payload["timestamp"], float)
        assert isinstance(payload["elapsed_seconds"], float)
        assert isinstance(payload["active_users"], int)
        assert isinstance(payload["rps"], float)
        assert isinstance(payload["total_requests"], int)

        # Validate latency nested object
        latency = payload["latency"]
        for key in ("p50", "p75", "p90", "p95", "p99", "p999", "min", "max", "avg"):
            assert key in latency
            assert isinstance(latency[key], float)

        # Validate errors nested object
        errors = payload["errors"]
        assert isinstance(errors["total"], int)
        assert isinstance(errors["rate"], float)
        assert isinstance(errors["by_status"], dict)

        # Validate endpoints list
        endpoints = payload["endpoints"]
        assert isinstance(endpoints, list)
        assert len(endpoints) == 1
        ep = endpoints[0]
        assert ep["name"] == "List Items"
        assert isinstance(ep["rps"], float)


async def test_server_start_stop(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
) -> None:
    server, _, port = dashboard
    # Server should be running (health check)
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"http://localhost:{port}/api/health") as resp,
    ):
        assert resp.status == 200

    # Stop is handled by fixture teardown — verify it doesn't raise
    server.stop()
