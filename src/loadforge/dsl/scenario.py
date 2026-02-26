"""Scenario and task definition dataclasses and the global scenario registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AsyncScenarioMethod(Protocol):
    """Protocol for async scenario methods (tasks, setup, teardown).

    Matches unbound async methods with signature ``(self, client) -> None``.
    """

    @property
    def __name__(self) -> str:
        """Function name."""
        ...

    async def __call__(self, instance: object, client: object) -> None:
        """Call the method."""
        ...


@dataclass
class TaskDefinition:
    """Definition of a single task within a scenario.

    Attributes:
        name: Human-readable name for this task.
        func: The unbound async method implementing this task.
        weight: Relative weight for weighted-random task selection.
            Higher weight means this task is selected more often.
    """

    name: str
    func: AsyncScenarioMethod
    weight: int = 1


@dataclass
class ScenarioDefinition:
    """Complete definition of a load test scenario.

    Created by the ``@scenario`` class decorator. Contains all metadata
    needed to instantiate and execute a scenario.

    Attributes:
        name: Human-readable name for this scenario.
        cls: The original class that was decorated.
        base_url: Base URL for all HTTP requests in this scenario.
        default_headers: Default headers applied to every request.
        tasks: List of task definitions discovered from @task-decorated methods.
        setup_func: Optional coroutine called once per virtual user before
            tasks begin.
        teardown_func: Optional coroutine called once per virtual user on
            shutdown.
        think_time: Random pause range (min, max) in seconds between task
            executions.
    """

    name: str
    cls: type
    base_url: str
    default_headers: dict[str, str] = field(default_factory=dict)
    tasks: list[TaskDefinition] = field(default_factory=list)
    setup_func: AsyncScenarioMethod | None = None
    teardown_func: AsyncScenarioMethod | None = None
    think_time: tuple[float, float] = (0.5, 1.5)


class ScenarioRegistry:
    """Registry of all discovered scenario definitions.

    Scenarios are registered automatically by the ``@scenario`` decorator.
    The registry is a module-level singleton.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._scenarios: dict[str, ScenarioDefinition] = {}

    def register(self, definition: ScenarioDefinition) -> None:
        """Register a scenario definition.

        Args:
            definition: The scenario definition to register.

        Raises:
            ScenarioError: If a scenario with the same name is already
                registered.
        """
        from loadforge._internal.errors import ScenarioError

        if definition.name in self._scenarios:
            msg = f"Scenario {definition.name!r} is already registered"
            raise ScenarioError(msg)
        self._scenarios[definition.name] = definition

    def get(self, name: str) -> ScenarioDefinition | None:
        """Look up a scenario by name.

        Args:
            name: The scenario name to look up.

        Returns:
            The ScenarioDefinition if found, None otherwise.
        """
        return self._scenarios.get(name)

    def get_all(self) -> list[ScenarioDefinition]:
        """Return all registered scenarios.

        Returns:
            List of all registered ScenarioDefinition instances.
        """
        return list(self._scenarios.values())

    def clear(self) -> None:
        """Remove all registered scenarios. Primarily for testing."""
        self._scenarios.clear()

    def __len__(self) -> int:
        """Return the number of registered scenarios."""
        return len(self._scenarios)


# Global singleton registry.
registry = ScenarioRegistry()
