"""Integration tests for the live dashboard server and WebSocket streaming."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

import aiohttp
import pytest

from loadforge.dashboard.broadcaster import SnapshotBroadcaster
from loadforge.dashboard.server import DashboardServer, create_app
from tests.conftest import _get_free_port, make_snapshot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def dashboard(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[DashboardServer, SnapshotBroadcaster, int]]:
    """Start a dashboard server on a free port and yield (server, broadcaster, port)."""
    port = _get_free_port()
    broadcaster = SnapshotBroadcaster()
    app = create_app(broadcaster)
    server = DashboardServer(app, broadcaster, port, host="127.0.0.1")
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
        snapshot = make_snapshot()
        broadcaster.on_snapshot(snapshot)

        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
        assert msg.type == aiohttp.WSMsgType.TEXT

        data = json.loads(msg.data)
        assert data["type"] == "snapshot"
        assert data["data"]["active_users"] == 50
        assert data["data"]["rps"] == 50.0


async def test_snapshot_immediately_after_connect_is_delivered(
    dashboard: tuple[DashboardServer, SnapshotBroadcaster, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: the handler must subscribe before completing the handshake.

    A slow ``subscribe`` widens the window that made CI flaky: if the server
    accepted first, a snapshot broadcast right after ``ws_connect`` returned
    was dropped because no client queue existed yet.
    """
    _, broadcaster, port = dashboard
    original_subscribe = broadcaster.subscribe

    def slow_subscribe() -> asyncio.Queue[str]:
        time.sleep(0.3)  # runs on the server thread; simulates a slow runner
        return original_subscribe()

    monkeypatch.setattr(broadcaster, "subscribe", slow_subscribe)

    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(f"http://localhost:{port}/ws/metrics") as ws,
    ):
        broadcaster.on_snapshot(make_snapshot())
        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
        assert json.loads(msg.data)["type"] == "snapshot"


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

        snapshot = make_snapshot(active_users=42)
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
        snapshot = make_snapshot()
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
        snapshot = make_snapshot()
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


def test_dashboard_server_start_timeout() -> None:
    """DashboardServer raises DashboardError when startup times out."""
    from unittest.mock import MagicMock, patch

    from loadforge import DashboardError

    port = _get_free_port()
    broadcaster = SnapshotBroadcaster()
    app = create_app(broadcaster)
    server = DashboardServer(app, broadcaster, port, host="127.0.0.1")

    # Replace the uvicorn server with a mock whose ``started`` is always
    # False.  The background thread will call mock.serve() which returns
    # a coroutine-like mock — harmless.
    fake_server = MagicMock()
    fake_server.started = False
    fake_server.serve = MagicMock(return_value=asyncio.sleep(10))
    server._server = fake_server

    with (
        patch("loadforge.dashboard.server._STARTUP_TIMEOUT_SECS", 0.2),
        patch("loadforge.dashboard.server._STARTUP_POLL_INTERVAL", 0.05),
        pytest.raises(DashboardError, match="failed to start"),
    ):
        server.start()

    # Cleanup: the background thread is running asyncio.sleep(10),
    # just let it be reaped as a daemon thread.
