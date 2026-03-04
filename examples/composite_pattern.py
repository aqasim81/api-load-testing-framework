"""Composite pattern — multi-phase load profile.

Demonstrates how to simulate a multi-phase load test by chaining
separate runs with different traffic patterns. Run each phase:

    # Phase 1: Ramp up from 10 to 100 users over 60s
    loadforge run examples/composite_pattern.py \
        --users 10 --duration 60 --pattern ramp --ramp-to 100

    # Phase 2: Hold steady at 100 users for 5 minutes
    loadforge run examples/composite_pattern.py \
        --users 100 --duration 300

    # Phase 3: Spike to stress-test at peak
    loadforge run examples/composite_pattern.py \
        --users 100 --duration 60 --pattern spike

    # Phase 4: Ramp back down
    loadforge run examples/composite_pattern.py \
        --users 100 --duration 60 --pattern ramp --ramp-to 10

For programmatic composite patterns, use the ``CompositePattern`` class
directly with ``LoadTestRunner``.
"""

from __future__ import annotations

import random

from loadforge import HttpClient, scenario, task


@scenario(
    name="Composite Pattern Demo",
    base_url="http://localhost:8080",
    think_time=(0.3, 1.5),
)
class CompositePatternScenario:
    """E-commerce workload for multi-phase testing."""

    @task(weight=5)
    async def list_products(self, client: HttpClient) -> None:
        """GET /products — primary read traffic."""
        await client.get("/products", name="List Products")

    @task(weight=2)
    async def get_product(self, client: HttpClient) -> None:
        """GET /products/:id — single product lookup."""
        pid = random.randint(1, 500)
        await client.get(f"/products/{pid}", name="Get Product")

    @task(weight=1)
    async def search(self, client: HttpClient) -> None:
        """GET /search — search query."""
        query = random.choice(["laptop", "phone", "tablet", "headphones"])
        await client.get(f"/search?q={query}", name="Search")
