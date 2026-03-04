"""Thread-safe WebSocket broadcast hub for live metric snapshots.

The ``SnapshotBroadcaster`` bridges the aggregator daemon thread (which
produces ``MetricSnapshot`` objects) with the asyncio event loop that serves
WebSocket clients.  Thread safety is achieved via ``loop.call_soon_threadsafe``
and a lock protecting the client set.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger

if TYPE_CHECKING:
    from loadforge.metrics.models import MetricSnapshot

logger = get_logger("dashboard.broadcaster")

_CLIENT_QUEUE_MAX = 50


class SnapshotBroadcaster:
    """Fans out serialized metric snapshots to connected WebSocket clients.

    Each connected client gets an ``asyncio.Queue`` that the WebSocket handler
    reads from.  When the aggregator thread calls ``on_snapshot``, the snapshot
    is serialized once and pushed onto every client queue via
    ``loop.call_soon_threadsafe``.

    Attributes:
        client_count: Number of currently subscribed clients.
    """

    def __init__(self) -> None:
        """Initialize the broadcaster with an empty client set."""
        self._clients: set[asyncio.Queue[str]] = set()
        self._clients_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the asyncio event loop reference for thread-safe dispatch.

        Args:
            loop: The event loop running in the dashboard server thread.
        """
        self._loop = loop

    @property
    def client_count(self) -> int:
        """Return the number of currently subscribed clients."""
        with self._clients_lock:
            return len(self._clients)

    def subscribe(self) -> asyncio.Queue[str]:
        """Register a new WebSocket client and return its message queue.

        Returns:
            A bounded asyncio queue that the WebSocket handler should read from.
        """
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=_CLIENT_QUEUE_MAX)
        with self._clients_lock:
            self._clients.add(q)
            count = len(self._clients)
        logger.debug("Client subscribed (total=%d)", count)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        """Remove a WebSocket client's queue from the broadcast set.

        Args:
            q: The queue previously returned by ``subscribe()``.
        """
        with self._clients_lock:
            self._clients.discard(q)
            count = len(self._clients)
        logger.debug("Client unsubscribed (total=%d)", count)

    def on_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Serialize a snapshot and fan out to all connected clients.

        Called from the aggregator daemon thread.  Uses
        ``loop.call_soon_threadsafe`` to safely enqueue messages on the
        asyncio event loop.

        Args:
            snapshot: The metric snapshot to broadcast.
        """
        if self._loop is None:
            return

        with self._clients_lock:
            if not self._clients:
                return
            clients = set(self._clients)

        json_str = _serialize_snapshot(snapshot)

        for q in clients:
            with contextlib.suppress(asyncio.QueueFull, RuntimeError):
                self._loop.call_soon_threadsafe(q.put_nowait, json_str)


def _serialize_snapshot(snapshot: MetricSnapshot) -> str:
    """Convert a MetricSnapshot to the WebSocket JSON wire format.

    Builds the dict manually (not ``dataclasses.asdict``) because the wire
    format differs from the dataclass layout: latency is a nested object,
    and endpoints are a list instead of a dict.

    Args:
        snapshot: The metric snapshot to serialize.

    Returns:
        JSON string matching the dashboard wire format.
    """
    msg = {
        "type": "snapshot",
        "data": {
            "timestamp": snapshot.timestamp,
            "elapsed_seconds": snapshot.elapsed_seconds,
            "active_users": snapshot.active_users,
            "rps": snapshot.requests_per_second,
            "total_requests": snapshot.total_requests,
            "latency": {
                "p50": snapshot.latency_p50,
                "p75": snapshot.latency_p75,
                "p90": snapshot.latency_p90,
                "p95": snapshot.latency_p95,
                "p99": snapshot.latency_p99,
                "p999": snapshot.latency_p999,
                "min": snapshot.latency_min,
                "max": snapshot.latency_max,
                "avg": snapshot.latency_avg,
            },
            "errors": {
                "total": snapshot.total_errors,
                "rate": snapshot.error_rate,
                "by_status": {str(k): v for k, v in snapshot.errors_by_status.items()},
            },
            "endpoints": [
                {
                    "name": ep.name,
                    "rps": ep.requests_per_second,
                    "request_count": ep.request_count,
                    "error_count": ep.error_count,
                    "error_rate": ep.error_rate,
                    "p50": ep.latency_p50,
                    "p75": ep.latency_p75,
                    "p90": ep.latency_p90,
                    "p95": ep.latency_p95,
                    "p99": ep.latency_p99,
                    "min": ep.latency_min,
                    "max": ep.latency_max,
                    "avg": ep.latency_avg,
                }
                for ep in snapshot.endpoints.values()
            ],
        },
    }
    return json.dumps(msg)
