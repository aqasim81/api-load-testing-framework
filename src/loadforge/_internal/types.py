"""Shared type aliases for LoadForge."""

from __future__ import annotations

# HTTP headers dictionary.
Headers = dict[str, str]

# Think time range (min_seconds, max_seconds).
ThinkTime = tuple[float, float]
