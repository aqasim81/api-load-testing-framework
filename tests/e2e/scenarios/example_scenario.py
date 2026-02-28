"""Minimal scenario used by E2E CLI tests.

The base_url placeholder is replaced at runtime by the test fixture
that writes a temporary copy with the actual echo server address.
"""

from __future__ import annotations

from loadforge import HttpClient, scenario, task


@scenario(
    name="E2E Test Scenario",
    base_url="http://127.0.0.1:9999",
    think_time=(0.01, 0.02),
)
class E2ETestScenario:
    """Minimal scenario for end-to-end CLI testing."""

    @task(weight=1)
    async def get_echo(self, client: HttpClient) -> None:
        """Hit the echo endpoint."""
        await client.get("/echo/test", name="Echo Test")
