"""Shared test fixtures for LoadForge test suite."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import threading
from typing import TYPE_CHECKING

import pytest
from aiohttp import web

from loadforge.metrics.models import EndpointMetrics, MetricSnapshot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from pathlib import Path


# =============================================================================
# Shared test factories
# =============================================================================


def make_snapshot(**overrides: object) -> MetricSnapshot:
    """Create a MetricSnapshot with sensible defaults for testing."""
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


# =============================================================================
# Pytest configuration
# =============================================================================


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-apply markers based on test directory structure."""
    for item in items:
        test_path = str(item.fspath)
        if "/unit/" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in test_path:
            item.add_marker(pytest.mark.e2e)


# =============================================================================
# Network utilities
# =============================================================================


def _get_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


# =============================================================================
# Network guard (invariant 5: loopback only)
# =============================================================================

_network_allowed = False


def _is_loopback(host: object) -> bool:
    """Return True if ``host`` names a loopback interface."""
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        # Strip an IPv6 zone id such as "fe80::1%lo0".
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _reject_unless_loopback(host: object, target: object, action: str) -> None:
    """Raise if ``host`` is not loopback while the guard is active."""
    if _network_allowed or _is_loopback(host):
        return
    msg = (
        f"Invariant 5: tests may only {action} loopback addresses, got {target!r}. "
        "Bind servers to 127.0.0.1 and use _get_free_port()."
    )
    raise RuntimeError(msg)


def _guard(original: Callable[..., object], action: str) -> Callable[..., object]:
    """Wrap a socket method whose last positional argument is the address."""

    def guarded(sock: socket.socket, *args: object) -> object:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            address = args[-1]
            host = address[0] if isinstance(address, tuple) else address
            _reject_unless_loopback(host, address, action)
        return original(sock, *args)

    return guarded


def _guard_getaddrinfo(original: Callable[..., object]) -> Callable[..., object]:
    """Wrap ``socket.getaddrinfo`` so only loopback names resolve (``None`` = passive)."""

    def guarded(host: object, *args: object, **kwargs: object) -> object:
        if host is not None:
            _reject_unless_loopback(host, host, "resolve")
        return original(host, *args, **kwargs)

    return guarded


@pytest.fixture(scope="session", autouse=True)
def _loopback_only_network() -> Iterator[None]:
    """Reject non-loopback connects, binds, UDP sends and DNS lookups for the session.

    Patches ``socket`` in the test process, so it covers asyncio, aiohttp,
    uvicorn and server threads. Not covered: worker subprocesses (spawned, so they
    never load this conftest) and connects made natively by uvloop, which the
    test process does not install.
    """
    with pytest.MonkeyPatch.context() as mp:
        for name, action in (
            ("connect", "connect to"),
            ("connect_ex", "connect to"),
            ("sendto", "send to"),
            ("bind", "bind to"),
        ):
            mp.setattr(socket.socket, name, _guard(getattr(socket.socket, name), action))
        mp.setattr(socket, "getaddrinfo", _guard_getaddrinfo(socket.getaddrinfo))
        yield


@pytest.fixture(autouse=True)
def _allow_network_marker(request: pytest.FixtureRequest) -> Iterator[None]:
    """Lift the network guard for tests marked ``@pytest.mark.allow_network``.

    Applies to the test body and function-scoped fixtures only; wider-scoped
    fixtures are set up while the guard is still active.
    """
    global _network_allowed
    if request.node.get_closest_marker("allow_network") is None:
        yield
        return
    _network_allowed = True
    try:
        yield
    finally:
        _network_allowed = False


# =============================================================================
# Echo HTTP Server handlers
# =============================================================================


async def _echo_handler(request: web.Request) -> web.Response:
    """Echo back request details as JSON."""
    body = await request.read()
    return web.json_response(
        {
            "method": request.method,
            "path": str(request.path),
            "query": dict(request.query),
            "headers": dict(request.headers),
            "body": body.decode("utf-8", errors="replace"),
        },
        status=200,
    )


async def _delay_handler(request: web.Request) -> web.Response:
    """Respond after a configurable delay (query param: ?delay=0.5)."""
    delay = float(request.query.get("delay", "0.1"))
    await asyncio.sleep(delay)
    return web.json_response({"delayed_by": delay})


async def _error_handler(request: web.Request) -> web.Response:
    """Return a configurable error status (query param: ?status=500)."""
    status = int(request.query.get("status", "500"))
    return web.json_response({"error": True}, status=status)


async def _health_handler(request: web.Request) -> web.Response:
    """Simple health check endpoint."""
    return web.json_response({"status": "ok"})


async def _login_handler(request: web.Request) -> web.Response:
    """Simulate a login endpoint that returns a token."""
    return web.json_response({"token": "test-token-12345"})


async def _logout_handler(request: web.Request) -> web.Response:
    """Simulate a logout endpoint."""
    return web.json_response({"status": "logged_out"})


def _create_echo_app() -> web.Application:
    """Build the echo server app with all test routes."""
    app = web.Application()
    app.router.add_route("*", "/echo{path:.*}", _echo_handler)
    app.router.add_get("/delay", _delay_handler)
    app.router.add_route("*", "/error", _error_handler)
    app.router.add_get("/health", _health_handler)
    app.router.add_post("/auth/login", _login_handler)
    app.router.add_post("/auth/logout", _logout_handler)
    return app


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def echo_server() -> AsyncIterator[str]:
    """Aiohttp echo server fixture.

    Returns the base URL (e.g., 'http://127.0.0.1:54321').
    """
    app = _create_echo_app()
    port = _get_free_port()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    yield f"http://127.0.0.1:{port}"
    await runner.cleanup()


@pytest.fixture
async def echo_server_per_test() -> AsyncIterator[str]:
    """Function-scoped echo server for tests that need isolation."""
    app = _create_echo_app()
    port = _get_free_port()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    yield f"http://127.0.0.1:{port}"
    await runner.cleanup()


@pytest.fixture
def sample_scenario_path(tmp_path: Path) -> Path:
    """Create a temporary scenario file for testing the loader."""
    scenario_code = """\
from __future__ import annotations

from loadforge import scenario, task, HttpClient


@scenario(name="Test Scenario", base_url="{base_url}")
class TestScenario:

    @task(weight=1)
    async def get_echo(self, client: HttpClient) -> None:
        await client.get("/echo/test", name="Echo Test")
"""
    path = tmp_path / "test_scenario.py"
    path.write_text(scenario_code)
    return path


# =============================================================================
# Sync fixtures for multiprocessing tests (Phase 4)
# =============================================================================


@pytest.fixture
def sync_echo_server() -> Iterator[str]:
    """Echo server running in a background thread for sync tests.

    Useful for multiprocessing integration tests where the runner
    blocks the main thread.
    """
    port = _get_free_port()
    started = threading.Event()
    loop_holder: list[asyncio.AbstractEventLoop] = []

    def _thread_target() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = _create_echo_app()
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "127.0.0.1", port)
        loop.run_until_complete(site.start())
        loop_holder.append(loop)
        started.set()
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())
        loop.close()

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    started.wait(timeout=5.0)

    yield f"http://127.0.0.1:{port}"

    if loop_holder:
        loop_holder[0].call_soon_threadsafe(loop_holder[0].stop)
    thread.join(timeout=5.0)


@pytest.fixture
def scenario_file(tmp_path: Path, sync_echo_server: str) -> Path:
    """Create a temporary scenario file pointing at the sync echo server."""
    code = f'''\
from __future__ import annotations

from loadforge import scenario, task, HttpClient


@scenario(
    name="Integration Test Scenario",
    base_url="{sync_echo_server}",
    think_time=(0.01, 0.02),
)
class TestScenario:

    @task(weight=1)
    async def get_echo(self, client: HttpClient) -> None:
        await client.get("/echo/test", name="Echo Test")
'''
    path = tmp_path / "test_scenario.py"
    path.write_text(code)
    return path
