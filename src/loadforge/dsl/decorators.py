"""Decorators for defining load test scenarios."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loadforge._internal.errors import ScenarioError
from loadforge.dsl.scenario import (
    AsyncScenarioMethod,
    ScenarioDefinition,
    TaskDefinition,
    registry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Marker attribute names set on decorated methods.
_TASK_MARKER = "_loadforge_task"
_TASK_WEIGHT = "_loadforge_task_weight"
_TASK_NAME = "_loadforge_task_name"
_SETUP_MARKER = "_loadforge_setup"
_TEARDOWN_MARKER = "_loadforge_teardown"


def scenario(
    *,
    name: str,
    base_url: str,
    default_headers: dict[str, str] | None = None,
    think_time: tuple[float, float] = (0.5, 1.5),
) -> Callable[[type], ScenarioDefinition]:
    """Decorate a class as a LoadForge scenario.

    The decorator introspects the class for ``@task``, ``@setup``, and
    ``@teardown`` decorated methods, builds a ``ScenarioDefinition``, and
    registers it in the global scenario registry.

    Args:
        name: Human-readable name for this scenario.
        base_url: Base URL for all HTTP requests.
        default_headers: Default headers applied to every request.
        think_time: Random pause range (min, max) in seconds between tasks.

    Returns:
        A class decorator that transforms the class into a
        ScenarioDefinition.

    Raises:
        ScenarioError: If the class has no ``@task`` methods, or if
            ``@setup``/``@teardown`` methods are not coroutine functions.
    """

    def decorator(cls: type) -> ScenarioDefinition:
        tasks: list[TaskDefinition] = []
        setup_func: AsyncScenarioMethod | None = None
        teardown_func: AsyncScenarioMethod | None = None

        for attr_name in dir(cls):
            if attr_name.startswith("__"):
                continue

            attr = getattr(cls, attr_name, None)
            if attr is None or not callable(attr):
                continue

            if getattr(attr, _TASK_MARKER, False):
                if not asyncio.iscoroutinefunction(attr):
                    msg = f"Task method {cls.__name__}.{attr_name} must be an async function"
                    raise ScenarioError(msg)
                task_name: str = getattr(attr, _TASK_NAME, attr_name)
                task_weight: int = getattr(attr, _TASK_WEIGHT, 1)
                tasks.append(
                    TaskDefinition(
                        name=task_name,
                        func=attr,
                        weight=task_weight,
                    )
                )

            if getattr(attr, _SETUP_MARKER, False):
                if not asyncio.iscoroutinefunction(attr):
                    msg = f"Setup method {cls.__name__}.{attr_name} must be an async function"
                    raise ScenarioError(msg)
                if setup_func is not None:
                    msg = f"Scenario {cls.__name__} has multiple @setup methods"
                    raise ScenarioError(msg)
                setup_func = attr

            if getattr(attr, _TEARDOWN_MARKER, False):
                if not asyncio.iscoroutinefunction(attr):
                    msg = f"Teardown method {cls.__name__}.{attr_name} must be an async function"
                    raise ScenarioError(msg)
                if teardown_func is not None:
                    msg = f"Scenario {cls.__name__} has multiple @teardown methods"
                    raise ScenarioError(msg)
                teardown_func = attr

        if not tasks:
            msg = f"Scenario {cls.__name__} has no @task methods. At least one @task is required."
            raise ScenarioError(msg)

        definition = ScenarioDefinition(
            name=name,
            cls=cls,
            base_url=base_url,
            default_headers=default_headers or {},
            tasks=tasks,
            setup_func=setup_func,
            teardown_func=teardown_func,
            think_time=think_time,
        )

        registry.register(definition)
        return definition

    return decorator


def task(
    *,
    weight: int = 1,
    name: str | None = None,
) -> Callable[[AsyncScenarioMethod], AsyncScenarioMethod]:
    """Mark a method as a load test task.

    Tasks are selected with weighted-random distribution during test
    execution. A task with ``weight=5`` will be selected approximately
    5x as often as one with ``weight=1``.

    Args:
        weight: Relative selection weight. Must be >= 1.
        name: Optional logical name for grouping metrics. Defaults to
            the method name.

    Returns:
        A method decorator that tags the method with task metadata.

    Raises:
        ScenarioError: If weight is less than 1.
    """
    if weight < 1:
        msg = f"Task weight must be >= 1, got {weight}"
        raise ScenarioError(msg)

    def decorator(func: AsyncScenarioMethod) -> AsyncScenarioMethod:
        setattr(func, _TASK_MARKER, True)
        setattr(func, _TASK_WEIGHT, weight)
        setattr(func, _TASK_NAME, name or func.__name__)
        return func

    return decorator


def setup(func: AsyncScenarioMethod) -> AsyncScenarioMethod:
    """Mark a method as the scenario setup hook.

    Called once per virtual user before task execution begins.
    Typically used for authentication or data initialization.

    Args:
        func: The async method to use as setup.

    Returns:
        The original method, tagged with setup metadata.
    """
    setattr(func, _SETUP_MARKER, True)
    return func


def teardown(func: AsyncScenarioMethod) -> AsyncScenarioMethod:
    """Mark a method as the scenario teardown hook.

    Called once per virtual user during shutdown.
    Typically used for cleanup (logout, session close).

    Args:
        func: The async method to use as teardown.

    Returns:
        The original method, tagged with teardown metadata.
    """
    setattr(func, _TEARDOWN_MARKER, True)
    return func
