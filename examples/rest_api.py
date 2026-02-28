"""Multi-endpoint REST API load test.

Demonstrates weighted tasks hitting multiple endpoints. Run with:

    loadforge run examples/rest_api.py --users 50 --duration 60

Or with a ramp pattern:

    loadforge run examples/rest_api.py --users 10 --duration 120 --pattern ramp --ramp-to 200
"""

from __future__ import annotations

import random

from loadforge import HttpClient, scenario, task


@scenario(
    name="REST API Load Test",
    base_url="http://localhost:8080",
    think_time=(0.5, 1.5),
)
class RestApiScenario:
    """Hit multiple endpoints with realistic traffic distribution."""

    @task(weight=5)
    async def list_items(self, client: HttpClient) -> None:
        """GET /items — most common operation."""
        await client.get("/items", name="List Items")

    @task(weight=3)
    async def get_item(self, client: HttpClient) -> None:
        """GET /items/:id — second most common."""
        item_id = random.randint(1, 1000)
        await client.get(f"/items/{item_id}", name="Get Item")

    @task(weight=1)
    async def create_item(self, client: HttpClient) -> None:
        """POST /items — least common."""
        await client.post(
            "/items",
            json={"name": f"Item-{random.randint(1, 10000)}"},
            name="Create Item",
        )
