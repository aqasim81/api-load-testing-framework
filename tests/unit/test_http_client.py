"""Tests for the instrumented HTTP client and RequestMetric."""

from __future__ import annotations

import aiohttp
import pytest

from loadforge.dsl.http_client import HttpClient, RequestMetric


class TestRequestMetric:
    """Tests for the RequestMetric dataclass."""

    def test_fields(self):
        """RequestMetric has the expected fields."""
        metric = RequestMetric(
            timestamp=1000.0,
            name="Get Items",
            method="GET",
            url="http://localhost/items",
            status_code=200,
            latency_ms=42.5,
            content_length=1024,
        )
        assert metric.timestamp == 1000.0
        assert metric.name == "Get Items"
        assert metric.method == "GET"
        assert metric.url == "http://localhost/items"
        assert metric.status_code == 200
        assert metric.latency_ms == 42.5
        assert metric.content_length == 1024
        assert metric.error is None
        assert metric.worker_id == 0

    def test_error_field(self):
        """RequestMetric can capture an error message."""
        metric = RequestMetric(
            timestamp=1000.0,
            name="Fail",
            method="POST",
            url="http://localhost/fail",
            status_code=0,
            latency_ms=5.0,
            content_length=0,
            error="ConnectionError: refused",
        )
        assert metric.error == "ConnectionError: refused"

    def test_custom_worker_id(self):
        """RequestMetric can have a custom worker_id."""
        metric = RequestMetric(
            timestamp=1000.0,
            name="test",
            method="GET",
            url="http://localhost",
            status_code=200,
            latency_ms=10.0,
            content_length=0,
            worker_id=3,
        )
        assert metric.worker_id == 3


class TestHttpClient:
    """Tests for the HttpClient class."""

    async def test_get_request(self, echo_server: str):
        """HttpClient.get sends a GET request and emits a metric."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            resp = await client.get("/echo/hello", name="Echo")
            assert resp.status == 200

        assert len(metrics) == 1
        assert metrics[0].method == "GET"
        assert metrics[0].name == "Echo"
        assert metrics[0].status_code == 200
        assert metrics[0].latency_ms > 0

    async def test_post_request(self, echo_server: str):
        """HttpClient.post sends a POST request."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            resp = await client.post("/echo/data", name="Post Echo")
            assert resp.status == 200

        assert len(metrics) == 1
        assert metrics[0].method == "POST"
        assert metrics[0].name == "Post Echo"

    async def test_put_request(self, echo_server: str):
        """HttpClient.put sends a PUT request."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            resp = await client.put("/echo/update", name="Put Echo")
            assert resp.status == 200

        assert metrics[0].method == "PUT"

    async def test_patch_request(self, echo_server: str):
        """HttpClient.patch sends a PATCH request."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            resp = await client.patch("/echo/partial", name="Patch Echo")
            assert resp.status == 200

        assert metrics[0].method == "PATCH"

    async def test_delete_request(self, echo_server: str):
        """HttpClient.delete sends a DELETE request."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            resp = await client.delete("/echo/remove", name="Delete Echo")
            assert resp.status == 200

        assert metrics[0].method == "DELETE"

    async def test_default_name_is_path(self, echo_server: str):
        """When no name is given, the path is used as the metric name."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            await client.get("/echo/unnamed")

        assert metrics[0].name == "/echo/unnamed"

    async def test_default_headers_sent(self, echo_server: str):
        """Default headers are included in every request."""
        async with HttpClient(
            base_url=echo_server,
            headers={"X-Custom": "test-value"},
        ) as client:
            resp = await client.get("/echo/headers")
            data = await resp.json()

        assert data["headers"]["X-Custom"] == "test-value"

    async def test_mutable_headers(self, echo_server: str):
        """Headers can be mutated after construction (e.g., in setup)."""
        async with HttpClient(base_url=echo_server) as client:
            client.headers["Authorization"] = "Bearer token123"
            resp = await client.get("/echo/auth")
            data = await resp.json()

        assert data["headers"]["Authorization"] == "Bearer token123"

    async def test_metric_url_is_full(self, echo_server: str):
        """RequestMetric.url is the full URL (base + path)."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
        ) as client:
            await client.get("/echo/full-url")

        assert metrics[0].url == f"{echo_server}/echo/full-url"

    async def test_worker_id_in_metric(self, echo_server: str):
        """RequestMetric.worker_id matches the client's worker_id."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url=echo_server,
            metric_callback=metrics.append,
            worker_id=7,
        ) as client:
            await client.get("/echo/worker")

        assert metrics[0].worker_id == 7

    async def test_noop_callback_by_default(self, echo_server: str):
        """Default metric_callback is a no-op (no error raised)."""
        async with HttpClient(base_url=echo_server) as client:
            resp = await client.get("/echo/noop")
            assert resp.status == 200

    async def test_error_metric_on_connection_failure(self):
        """RequestMetric captures errors on connection failures."""
        metrics: list[RequestMetric] = []

        async with HttpClient(
            base_url="http://127.0.0.1:1",
            metric_callback=metrics.append,
            timeout=1.0,
        ) as client:
            with pytest.raises(aiohttp.ClientError):
                await client.get("/will-fail", name="Fail")

        assert len(metrics) == 1
        assert metrics[0].error is not None
        assert metrics[0].status_code == 0

    async def test_context_manager_required(self):
        """Using HttpClient outside async context manager raises RuntimeError."""
        client = HttpClient(base_url="http://localhost")
        with pytest.raises(RuntimeError, match="async context manager"):
            await client.get("/test")
