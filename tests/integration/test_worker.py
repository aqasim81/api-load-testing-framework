"""Integration tests for the single-worker engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from loadforge.dsl.scenario import ScenarioDefinition, TaskDefinition
from loadforge.engine.session import SessionState
from loadforge.engine.session import TestSession as LoadTestSession
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.ramp import RampPattern

if TYPE_CHECKING:
    from loadforge.dsl.http_client import HttpClient


# ============================================================================
# Helper scenario builders — construct ScenarioDefinition directly to avoid
# polluting the global registry.
# ============================================================================


def _make_echo_scenario(base_url: str) -> ScenarioDefinition:
    """Create a simple scenario that hits the echo endpoint."""

    class _EchoScenario:
        pass

    async def _get_echo(self: object, client: HttpClient) -> None:
        await client.get("/echo/test", name="Echo Test")

    return ScenarioDefinition(
        name="Echo Test",
        cls=_EchoScenario,
        base_url=base_url,
        tasks=[TaskDefinition(name="Echo Test", func=_get_echo, weight=1)],  # type: ignore[arg-type]
        think_time=(0.01, 0.02),  # Fast think time for tests
    )


def _make_setup_teardown_scenario(base_url: str) -> ScenarioDefinition:
    """Create a scenario with setup and teardown."""

    class _AuthScenario:
        pass

    async def _setup(self: object, client: HttpClient) -> None:
        resp = await client.post("/auth/login", name="Login")
        data = await resp.json()
        client.headers["Authorization"] = f"Bearer {data['token']}"

    async def _get_echo(self: object, client: HttpClient) -> None:
        await client.get("/echo/test", name="Echo Test")

    async def _teardown(self: object, client: HttpClient) -> None:
        await client.post("/auth/logout", name="Logout")

    return ScenarioDefinition(
        name="Auth Test",
        cls=_AuthScenario,
        base_url=base_url,
        tasks=[TaskDefinition(name="Echo Test", func=_get_echo, weight=1)],  # type: ignore[arg-type]
        setup_func=_setup,  # type: ignore[arg-type]
        teardown_func=_teardown,  # type: ignore[arg-type]
        think_time=(0.01, 0.02),
    )


def _make_error_scenario(base_url: str) -> ScenarioDefinition:
    """Create a scenario that hits the error endpoint."""

    class _ErrorScenario:
        pass

    async def _get_error(self: object, client: HttpClient) -> None:
        await client.get("/error?status=500", name="Error Request")

    return ScenarioDefinition(
        name="Error Test",
        cls=_ErrorScenario,
        base_url=base_url,
        tasks=[TaskDefinition(name="Error Request", func=_get_error, weight=1)],  # type: ignore[arg-type]
        think_time=(0.01, 0.02),
    )


def _make_weighted_scenario(base_url: str) -> ScenarioDefinition:
    """Create a scenario with weighted tasks."""

    class _WeightedScenario:
        pass

    async def _heavy_task(self: object, client: HttpClient) -> None:
        await client.get("/echo/heavy", name="Heavy Task")

    async def _light_task(self: object, client: HttpClient) -> None:
        await client.get("/echo/light", name="Light Task")

    return ScenarioDefinition(
        name="Weighted Test",
        cls=_WeightedScenario,
        base_url=base_url,
        tasks=[
            TaskDefinition(name="Heavy Task", func=_heavy_task, weight=9),  # type: ignore[arg-type]
            TaskDefinition(name="Light Task", func=_light_task, weight=1),  # type: ignore[arg-type]
        ],
        think_time=(0.01, 0.02),
    )


# ============================================================================
# Tests
# ============================================================================


class TestWorkerIntegration:
    """Integration tests for TestSession against the echo server."""

    @pytest.mark.timeout(15)
    async def test_executes_scenario_against_echo_server(self, echo_server: str) -> None:
        """Run a simple scenario and verify metrics are collected."""
        scenario = _make_echo_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=2),
            duration_seconds=2.0,
            tick_interval=0.5,
        )
        result = await session.run()

        assert result.scenario_name == "Echo Test"
        assert result.duration_seconds >= 1.5
        assert len(result.snapshots) > 0
        assert result.final_summary is not None
        assert result.final_summary.total_requests > 0
        assert session.state == SessionState.COMPLETED

    @pytest.mark.timeout(15)
    async def test_scales_users_with_ramp_pattern(self, echo_server: str) -> None:
        """Verify that active users ramp up over time."""
        scenario = _make_echo_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=RampPattern(start_users=1, end_users=5, ramp_duration=3.0),
            duration_seconds=3.0,
            tick_interval=0.5,
        )
        result = await session.run()

        # Check that user count increased over time
        user_counts = [s.active_users for s in result.snapshots]
        assert max(user_counts) >= 3  # Should ramp up to at least 3

    @pytest.mark.timeout(15)
    async def test_executes_setup_and_teardown(self, echo_server: str) -> None:
        """Verify setup and teardown hooks are called."""
        scenario = _make_setup_teardown_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=1),
            duration_seconds=1.5,
            tick_interval=0.5,
        )
        result = await session.run()

        assert result.final_summary is not None
        endpoints = result.final_summary.endpoints
        # Login should appear in metrics (from setup)
        assert "Login" in endpoints
        # Main task should appear
        assert "Echo Test" in endpoints
        # Logout should appear in metrics (from teardown)
        assert "Logout" in endpoints

    @pytest.mark.timeout(15)
    async def test_handles_errors_gracefully(self, echo_server: str) -> None:
        """Verify errors are counted but don't crash the worker."""
        scenario = _make_error_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=2),
            duration_seconds=2.0,
            tick_interval=0.5,
        )
        result = await session.run()

        assert result.final_summary is not None
        # All requests should be errors (status 500)
        assert result.final_summary.total_errors > 0
        assert result.final_summary.error_rate > 0.5
        assert 500 in result.final_summary.errors_by_status
        assert session.state == SessionState.COMPLETED

    @pytest.mark.timeout(15)
    async def test_respects_rate_limit(self, echo_server: str) -> None:
        """Verify rate limiter constrains throughput."""
        scenario = _make_echo_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=5),
            duration_seconds=3.0,
            tick_interval=0.5,
            rate_limit=5.0,  # 5 RPS
        )
        result = await session.run()

        assert result.final_summary is not None
        # With 5 RPS for 3 seconds, should have roughly 15 requests
        # Allow generous tolerance due to burst capacity and timing
        assert result.final_summary.total_requests < 30

    @pytest.mark.timeout(15)
    async def test_stop_triggers_graceful_shutdown(self, echo_server: str) -> None:
        """Verify stop() causes the session to finish cleanly."""
        scenario = _make_echo_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=3),
            duration_seconds=10.0,  # Long duration — we'll stop early
            tick_interval=0.5,
        )

        async def _stop_after_delay() -> None:
            await asyncio.sleep(1.5)
            await session.stop()

        # Run session and stop concurrently
        import asyncio

        stop_task = asyncio.create_task(_stop_after_delay())
        result = await session.run()
        await stop_task

        assert session.state == SessionState.COMPLETED
        # Duration should be much less than 10s
        assert result.duration_seconds < 5.0
        assert result.final_summary is not None
        assert result.final_summary.total_requests > 0

    @pytest.mark.timeout(20)
    async def test_weighted_task_selection(self, echo_server: str) -> None:
        """Verify weighted-random selects heavy task more often."""
        scenario = _make_weighted_scenario(echo_server)
        session = LoadTestSession(
            scenario=scenario,
            pattern=ConstantPattern(users=2),
            duration_seconds=3.0,
            tick_interval=0.5,
        )
        result = await session.run()

        assert result.final_summary is not None
        endpoints = result.final_summary.endpoints
        assert "Heavy Task" in endpoints
        assert "Light Task" in endpoints

        heavy_count = endpoints["Heavy Task"].request_count
        light_count = endpoints["Light Task"].request_count
        total = heavy_count + light_count

        # Heavy task should get roughly 90% of requests
        # Use a generous threshold: at least 60%
        assert heavy_count / total > 0.6
