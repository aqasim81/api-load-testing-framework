"""Basic GET scenario — the simplest possible LoadForge scenario.

This example demonstrates the core DSL: a single endpoint hit with
constant traffic. Run it with:

    loadforge run examples/basic_get.py --users 10 --duration 30
"""

from __future__ import annotations

from loadforge import HttpClient, scenario, task


@scenario(
    name="Basic GET",
    base_url="http://localhost:8080",
)
class BasicGetScenario:
    """Hit a single endpoint repeatedly."""

    @task(weight=1)
    async def get_root(self, client: HttpClient) -> None:
        """GET the root endpoint."""
        await client.get("/", name="Root")
