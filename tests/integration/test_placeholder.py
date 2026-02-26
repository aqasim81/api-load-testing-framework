"""Placeholder to verify integration test infrastructure works."""

from __future__ import annotations

import aiohttp


async def test_echo_server_responds(echo_server: str) -> None:
    async with aiohttp.ClientSession() as session, session.get(f"{echo_server}/health") as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
