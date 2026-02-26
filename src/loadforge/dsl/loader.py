"""Dynamic scenario file loading via importlib."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from loadforge._internal.errors import ScenarioError
from loadforge.dsl.scenario import ScenarioDefinition


def load_scenario(file_path: str | Path) -> ScenarioDefinition:
    """Load a scenario from a Python file.

    Dynamically imports the file using ``importlib`` and scans the module
    globals for ``ScenarioDefinition`` instances (created by the ``@scenario``
    decorator).

    Args:
        file_path: Path to the Python scenario file.

    Returns:
        The first ``ScenarioDefinition`` found in the module.

    Raises:
        ScenarioError: If the file does not exist, cannot be imported,
            or contains no ``@scenario``-decorated class.
    """
    path = Path(file_path)

    if not path.exists():
        msg = f"Scenario file not found: {path}"
        raise ScenarioError(msg)

    if path.suffix != ".py":
        msg = f"Scenario file must be a .py file, got: {path}"
        raise ScenarioError(msg)

    module_name = f"loadforge_scenario_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"Could not create module spec for: {path}"
        raise ScenarioError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        msg = f"Failed to import scenario file {path}: {exc}"
        raise ScenarioError(msg) from exc

    # Scan module globals for ScenarioDefinition instances.
    definitions: list[ScenarioDefinition] = [
        obj for obj in vars(module).values() if isinstance(obj, ScenarioDefinition)
    ]

    if not definitions:
        sys.modules.pop(module_name, None)
        msg = (
            f"No @scenario-decorated class found in {path}. "
            f"Ensure at least one class is decorated with @scenario."
        )
        raise ScenarioError(msg)

    return definitions[0]
