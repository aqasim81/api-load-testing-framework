"""Unit tests for the public API surface of the ``loadforge`` package."""

from __future__ import annotations

import pytest

import loadforge
from loadforge._internal import errors


@pytest.mark.parametrize(
    "name",
    ["LoadForgeError", "ScenarioError", "ConfigError", "EngineError", "DashboardError"],
)
def test_error_exported_from_package(name: str) -> None:
    """Each exception is re-exported unchanged and derives from LoadForgeError."""
    exported = getattr(loadforge, name)
    assert name in loadforge.__all__
    assert exported is getattr(errors, name)
    assert issubclass(exported, loadforge.LoadForgeError)
