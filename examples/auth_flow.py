"""Authenticated API load test — login then make requests.

Demonstrates the @setup and @teardown hooks for per-user session
management. Run with:

    loadforge run examples/auth_flow.py --users 20 --duration 60
"""

from __future__ import annotations

import random

from loadforge import HttpClient, scenario, setup, task, teardown


@scenario(
    name="Auth Flow Load Test",
    base_url="http://localhost:8080",
    think_time=(0.5, 2.0),
)
class AuthFlowScenario:
    """Login, perform authenticated requests, then logout."""

    @setup
    async def on_start(self, client: HttpClient) -> None:
        """Log in and store the auth token for this virtual user."""
        resp = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "test-password-12345"},  # noqa: S106
            name="Login",
        )
        data = await resp.json()
        client.headers["Authorization"] = f"Bearer {data['token']}"

    @task(weight=5)
    async def list_items(self, client: HttpClient) -> None:
        """GET /items — most frequent operation."""
        await client.get("/items", name="List Items")

    @task(weight=2)
    async def get_item(self, client: HttpClient) -> None:
        """GET /items/:id — fetch a single item."""
        item_id = random.randint(1, 500)
        await client.get(f"/items/{item_id}", name="Get Item")

    @task(weight=1)
    async def create_item(self, client: HttpClient) -> None:
        """POST /items — create a new item."""
        await client.post(
            "/items",
            json={"name": f"Item-{random.randint(1, 10000)}"},
            name="Create Item",
        )

    @teardown
    async def on_stop(self, client: HttpClient) -> None:
        """Log out this virtual user."""
        await client.post("/auth/logout", name="Logout")
