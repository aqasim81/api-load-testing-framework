"""Tests for the loopback-only network guard (invariant 5) and the dashboard bind host."""

from __future__ import annotations

import socket

import pytest

from loadforge.dashboard.broadcaster import SnapshotBroadcaster
from loadforge.dashboard.server import DashboardServer, create_app


class TestLoopbackOnlyNetworkGuard:
    """The session-wide guard in conftest.py rejects non-loopback addresses."""

    def test_connect_rejects_external_address(self) -> None:
        # 203.0.113.0/24 is TEST-NET-3; the guard raises before any syscall.
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
            pytest.raises(RuntimeError, match="Invariant 5"),
        ):
            s.connect(("203.0.113.1", 80))

    def test_connect_ex_rejects_external_hostname(self) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
            pytest.raises(RuntimeError, match="Invariant 5"),
        ):
            s.connect_ex(("example.com", 80))

    def test_getaddrinfo_rejects_external_hostname(self) -> None:
        with pytest.raises(RuntimeError, match="Invariant 5"):
            socket.getaddrinfo("example.com", 80)

    def test_getaddrinfo_allows_loopback_and_passive(self) -> None:
        assert socket.getaddrinfo("localhost", None)
        assert socket.getaddrinfo(None, 0, flags=socket.AI_PASSIVE)

    def test_sendto_rejects_external_address(self) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s,
            pytest.raises(RuntimeError, match="Invariant 5"),
        ):
            s.sendto(b"x", ("203.0.113.1", 9))

    @pytest.mark.parametrize("host", ["0.0.0.0", ""])  # noqa: S104
    def test_bind_rejects_all_interfaces(self, host: str) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
            pytest.raises(RuntimeError, match="Invariant 5"),
        ):
            s.bind((host, 0))

    @pytest.mark.parametrize(
        ("family", "host"),
        [
            (socket.AF_INET, "127.0.0.1"),
            (socket.AF_INET, "localhost"),
            (socket.AF_INET, "LOCALHOST"),
            (socket.AF_INET6, "::1"),
        ],
    )
    def test_bind_allows_loopback(self, family: socket.AddressFamily, host: str) -> None:
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            assert s.getsockname()[1] > 0

    @pytest.mark.allow_network
    def test_allow_network_marker_lifts_guard(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))  # noqa: S104
            assert s.getsockname()[1] > 0


class TestDashboardServerHost:
    """DashboardServer binds all interfaces by default and accepts an explicit host."""

    def test_default_host_is_all_interfaces(self) -> None:
        broadcaster = SnapshotBroadcaster()
        server = DashboardServer(create_app(broadcaster), broadcaster)
        assert server._config.host == "0.0.0.0"  # noqa: S104

    def test_explicit_host_is_used(self) -> None:
        broadcaster = SnapshotBroadcaster()
        server = DashboardServer(create_app(broadcaster), broadcaster, host="127.0.0.1")
        assert server._config.host == "127.0.0.1"
