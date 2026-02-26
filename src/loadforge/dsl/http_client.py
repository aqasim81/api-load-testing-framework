"""Instrumented HTTP client with auto-timing and metric emission."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Callable


def _noop_callback(metric: RequestMetric) -> None:
    """Default no-op metric callback."""


@dataclass
class RequestMetric:
    """Raw metric emitted for every HTTP request.

    Attributes:
        timestamp: Monotonic timestamp when the request started.
        name: Logical name for metric grouping (e.g., "List Items").
        method: HTTP method (GET, POST, etc.).
        url: Full request URL.
        status_code: HTTP response status code (0 if request failed).
        latency_ms: Response time in milliseconds.
        content_length: Response body size in bytes.
        error: Error message if the request failed, None otherwise.
        worker_id: ID of the worker process that made the request.
    """

    timestamp: float
    name: str
    method: str
    url: str
    status_code: int
    latency_ms: float
    content_length: int
    error: str | None = None
    worker_id: int = 0


class HttpClient:
    """Instrumented async HTTP client wrapping ``aiohttp.ClientSession``.

    Every HTTP request is auto-timed and emits a ``RequestMetric`` via the
    configured ``metric_callback``. The callback defaults to a no-op and
    is replaced by the engine in later phases.

    Attributes:
        base_url: Base URL prepended to all request paths.
        headers: Mutable headers dict applied to every request. Setup hooks
            can modify this to add authentication tokens.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        metric_callback: Callable[[RequestMetric], None] | None = None,
        worker_id: int = 0,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the HTTP client.

        Args:
            base_url: Base URL prepended to all request paths.
            headers: Default headers applied to every request.
            metric_callback: Callback invoked with a ``RequestMetric``
                after each request. Defaults to a no-op.
            worker_id: Worker process identifier for metric tagging.
            timeout: Default request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.headers: dict[str, str] = dict(headers or {})
        self._metric_callback = metric_callback or _noop_callback
        self._worker_id = worker_id
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> HttpClient:
        """Open the underlying aiohttp session."""
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Close the underlying aiohttp session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get(
        self,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send a GET request.

        Args:
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.
        """
        return await self._request("GET", path, name=name, **kwargs)

    async def post(
        self,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send a POST request.

        Args:
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.
        """
        return await self._request("POST", path, name=name, **kwargs)

    async def put(
        self,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send a PUT request.

        Args:
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.
        """
        return await self._request("PUT", path, name=name, **kwargs)

    async def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send a PATCH request.

        Args:
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.
        """
        return await self._request("PATCH", path, name=name, **kwargs)

    async def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send a DELETE request.

        Args:
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.
        """
        return await self._request("DELETE", path, name=name, **kwargs)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        """Send an HTTP request with auto-timing and metric emission.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path appended to base_url.
            name: Logical name for metric grouping. Defaults to the path.
            **kwargs: Additional keyword arguments passed to aiohttp.

        Returns:
            The aiohttp response object.

        Raises:
            RuntimeError: If the client is used outside of an async context
                manager.
        """
        if self._session is None:
            msg = "HttpClient must be used as an async context manager"
            raise RuntimeError(msg)

        url = f"{self.base_url}{path}"
        metric_name = name or path
        merged_headers = {**self.headers}

        start = time.monotonic()
        status_code = 0
        content_length = 0
        error: str | None = None

        try:
            resp = await self._session.request(
                method,
                url,
                headers=merged_headers,
                **kwargs,  # type: ignore[arg-type]
            )
            status_code = resp.status
            content_length = int(resp.headers.get("Content-Length", 0))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            metric = RequestMetric(
                timestamp=start,
                name=metric_name,
                method=method,
                url=url,
                status_code=status_code,
                latency_ms=latency_ms,
                content_length=content_length,
                error=error,
                worker_id=self._worker_id,
            )
            self._metric_callback(metric)

        return resp
