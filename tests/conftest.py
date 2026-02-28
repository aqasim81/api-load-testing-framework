"""Shared test fixtures for LoadForge test suite."""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import TYPE_CHECKING

import pytest
from aiohttp import web

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path


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
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


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


def _run_echo_server_in_thread(port: int, started: threading.Event) -> asyncio.AbstractEventLoop:
    """Run an aiohttp echo server in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = _create_echo_app()
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "127.0.0.1", port)
    loop.run_until_complete(site.start())
    started.set()
    loop.run_forever()
    loop.run_until_complete(runner.cleanup())
    loop.close()
    return loop


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
