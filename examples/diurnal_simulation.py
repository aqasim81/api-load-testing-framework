"""Diurnal simulation — compressed 24-hour traffic cycle.

Demonstrates the diurnal pattern which generates a sine-wave of
virtual users that simulates day/night traffic variation. The full
cycle is compressed into the test duration. Run with:

    loadforge run examples/diurnal_simulation.py --users 200 --duration 300 --pattern diurnal

The --users flag sets the peak (daytime) user count; the trough is
automatically set to 1/5 of the peak.
"""

from __future__ import annotations

import random

from loadforge import HttpClient, scenario, task


@scenario(
    name="Diurnal Simulation",
    base_url="http://localhost:8080",
    think_time=(0.5, 2.0),
)
class DiurnalSimulationScenario:
    """Simulate day/night traffic to find performance cliffs."""

    @task(weight=5)
    async def read_feed(self, client: HttpClient) -> None:
        """GET /feed — most common daytime activity."""
        await client.get("/feed", name="Read Feed")

    @task(weight=2)
    async def view_profile(self, client: HttpClient) -> None:
        """GET /users/:id — view a random user profile."""
        user_id = random.randint(1, 1000)
        await client.get(f"/users/{user_id}", name="View Profile")

    @task(weight=1)
    async def post_update(self, client: HttpClient) -> None:
        """POST /posts — create content."""
        await client.post(
            "/posts",
            json={"body": "Hello from LoadForge!"},
            name="Post Update",
        )
