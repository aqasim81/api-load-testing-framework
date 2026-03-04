"""Spike test — sudden traffic burst to stress-test your API.

Demonstrates the spike traffic pattern which simulates a sudden surge
of virtual users (e.g. a flash sale or viral event). Run with:

    loadforge run examples/spike_test.py --users 10 --duration 60 --pattern spike

The spike pattern starts at --users, bursts to ~5x that count, then
decays back to the base level over the remaining duration.
"""

from __future__ import annotations

from loadforge import HttpClient, scenario, task


@scenario(
    name="Spike Test",
    base_url="http://localhost:8080",
    think_time=(0.3, 1.0),
)
class SpikeTestScenario:
    """Simulate a flash-sale traffic spike."""

    @task(weight=3)
    async def browse_catalog(self, client: HttpClient) -> None:
        """GET /catalog — users browsing during the spike."""
        await client.get("/catalog", name="Browse Catalog")

    @task(weight=1)
    async def add_to_cart(self, client: HttpClient) -> None:
        """POST /cart — purchase attempts during the burst."""
        await client.post(
            "/cart",
            json={"item_id": 42, "quantity": 1},
            name="Add to Cart",
        )
