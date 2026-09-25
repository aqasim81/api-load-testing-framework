"""FastAPI application for the LoadForge live dashboard.

Provides a WebSocket endpoint at ``/ws/metrics`` for streaming live metric
snapshots, a health-check endpoint at ``/api/health``, and serves the
pre-built React SPA via ``StaticFiles``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from loadforge._internal.errors import DashboardError
from loadforge._internal.logging import get_logger

if TYPE_CHECKING:
    from loadforge.dashboard.broadcaster import SnapshotBroadcaster

logger = get_logger("dashboard.server")

_STATIC_DIR = Path(__file__).parent / "static"
# All interfaces, so the dashboard is reachable from other machines. Tests bind loopback.
_DEFAULT_HOST = "0.0.0.0"  # noqa: S104
_STARTUP_TIMEOUT_SECS = 5.0
_STARTUP_POLL_INTERVAL = 0.1
_SHUTDOWN_TIMEOUT_SECS = 5.0


def create_app(broadcaster: SnapshotBroadcaster) -> FastAPI:
    """Create the FastAPI application for the live dashboard.

    Args:
        broadcaster: The snapshot broadcaster that WebSocket clients subscribe to.

    Returns:
        A configured FastAPI application instance.
    """
    app = FastAPI(title="LoadForge Dashboard", docs_url=None, redoc_url=None)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        """Return a simple health-check response."""
        return JSONResponse({"status": "ok"})

    @app.websocket("/ws/metrics")
    async def ws_metrics(ws: WebSocket) -> None:
        """Stream live metric snapshots to a connected WebSocket client."""
        # Subscribe before completing the handshake: once the client sees the
        # connection as open, snapshots broadcast from that moment on must reach it.
        q = broadcaster.subscribe()
        try:
            await ws.accept()
            while True:
                msg = await q.get()
                await ws.send_text(msg)
        except WebSocketDisconnect:
            pass
        except (ConnectionError, asyncio.CancelledError, RuntimeError):
            logger.debug("WebSocket connection closed unexpectedly")
        finally:
            broadcaster.unsubscribe(q)

    # Mount static files for the React SPA if the directory exists
    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True))

    return app


class DashboardServer:
    """Manages a FastAPI/uvicorn server running in a background daemon thread.

    The server serves the live dashboard React SPA and streams metric
    snapshots over WebSocket.

    Attributes:
        port: The port the server listens on.
    """

    def __init__(
        self,
        app: FastAPI,
        broadcaster: SnapshotBroadcaster,
        port: int = 8089,
        host: str | None = None,
    ) -> None:
        """Initialize the dashboard server.

        Args:
            app: The FastAPI application to serve.
            broadcaster: The snapshot broadcaster (loop reference will be set).
            port: Port to listen on.
            host: Interface to bind. Defaults to all interfaces (``0.0.0.0``).
        """
        self.port = port
        self._broadcaster = broadcaster
        self._config = uvicorn.Config(
            app,
            host=host if host is not None else _DEFAULT_HOST,
            port=port,
            log_level="warning",
            access_log=False,
            ws="wsproto",
        )
        self._server = uvicorn.Server(self._config)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Return the base URL for the dashboard."""
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        """Start the uvicorn server in a background daemon thread.

        Blocks until the server is accepting connections or a timeout
        is reached.

        Raises:
            DashboardError: If the server fails to start within the timeout.
        """

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._broadcaster.set_loop(loop)
            loop.run_until_complete(self._server.serve())
            loop.close()

        self._thread = threading.Thread(
            target=_run,
            name="loadforge-dashboard",
            daemon=True,
        )
        self._thread.start()

        # Wait for the server to be ready
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECS
        while time.monotonic() < deadline:
            if self._server.started:
                logger.info("Dashboard server started on port %d", self.port)
                return
            time.sleep(_STARTUP_POLL_INTERVAL)

        msg = f"Dashboard server failed to start within {_STARTUP_TIMEOUT_SECS}s"
        raise DashboardError(msg)

    def stop(self) -> None:
        """Gracefully stop the server and join the background thread."""
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=_SHUTDOWN_TIMEOUT_SECS)
            self._thread = None
        logger.info("Dashboard server stopped")
