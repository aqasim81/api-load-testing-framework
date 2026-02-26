"""Tests for the scenario registry, dataclasses, and scenario loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from loadforge._internal.errors import ScenarioError
from loadforge.dsl.decorators import scenario, task
from loadforge.dsl.loader import load_scenario
from loadforge.dsl.scenario import (
    ScenarioDefinition,
    ScenarioRegistry,
    TaskDefinition,
    registry,
)


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the global scenario registry before each test."""
    registry.clear()
    yield
    registry.clear()


# =========================================================================
# ScenarioRegistry
# =========================================================================


class TestScenarioRegistry:
    """Tests for the ScenarioRegistry class."""

    def test_register_and_get(self):
        """Registered scenarios can be retrieved by name."""
        reg = ScenarioRegistry()

        @scenario(name="Lookup", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        reg.register(MyScenario)
        assert reg.get("Lookup") is MyScenario

    def test_get_nonexistent_returns_none(self):
        """Looking up a non-registered name returns None."""
        reg = ScenarioRegistry()
        assert reg.get("nonexistent") is None

    def test_get_all(self):
        """get_all returns all registered scenarios."""
        reg = ScenarioRegistry()

        @scenario(name="First", base_url="http://localhost")
        class FirstScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        @scenario(name="Second", base_url="http://localhost")
        class SecondScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        reg.register(FirstScenario)
        reg.register(SecondScenario)
        all_scenarios = reg.get_all()
        assert len(all_scenarios) == 2

    def test_duplicate_name_raises_error(self):
        """Registering two scenarios with the same name raises ScenarioError."""
        reg = ScenarioRegistry()

        @scenario(name="Dup", base_url="http://localhost")
        class First:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        reg.register(First)

        @scenario(name="Dup2", base_url="http://localhost")
        class Second:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        # Manually rename to create a duplicate
        second = Second
        object.__setattr__(second, "name", "Dup")

        with pytest.raises(ScenarioError, match="already registered"):
            reg.register(second)

    def test_clear(self):
        """clear() empties the registry."""
        reg = ScenarioRegistry()

        @scenario(name="Clearable", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        reg.register(MyScenario)
        assert len(reg) == 1
        reg.clear()
        assert len(reg) == 0

    def test_len(self):
        """__len__ returns the count of registered scenarios."""
        reg = ScenarioRegistry()
        assert len(reg) == 0

        @scenario(name="Countable", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        reg.register(MyScenario)
        assert len(reg) == 1


# =========================================================================
# Dataclass integrity
# =========================================================================


class TestDataclasses:
    """Tests for TaskDefinition and ScenarioDefinition dataclasses."""

    def test_task_definition_fields(self):
        """TaskDefinition has the expected fields."""

        async def dummy(self: object, client: object) -> None:
            pass

        td = TaskDefinition(name="test", func=dummy, weight=3)
        assert td.name == "test"
        assert td.func is dummy
        assert td.weight == 3

    def test_task_definition_default_weight(self):
        """TaskDefinition default weight is 1."""

        async def dummy(self: object, client: object) -> None:
            pass

        td = TaskDefinition(name="test", func=dummy)
        assert td.weight == 1

    def test_scenario_definition_defaults(self):
        """ScenarioDefinition has correct defaults."""

        class Dummy:
            pass

        sd = ScenarioDefinition(name="test", cls=Dummy, base_url="http://localhost")
        assert sd.default_headers == {}
        assert sd.tasks == []
        assert sd.setup_func is None
        assert sd.teardown_func is None
        assert sd.think_time == (0.5, 1.5)


# =========================================================================
# Scenario Loader
# =========================================================================


class TestLoader:
    """Tests for the load_scenario function."""

    def test_load_scenario_from_file(self, tmp_path: Path):
        """load_scenario loads a valid scenario file."""
        code = """\
from __future__ import annotations

from loadforge import scenario, task


@scenario(name="Loaded", base_url="http://localhost")
class LoadedScenario:
    @task(weight=1)
    async def do_work(self, client: object) -> None:
        pass
"""
        path = tmp_path / "valid_scenario.py"
        path.write_text(code)

        result = load_scenario(path)
        assert isinstance(result, ScenarioDefinition)
        assert result.name == "Loaded"
        assert result.base_url == "http://localhost"

    def test_load_scenario_nonexistent_file(self, tmp_path: Path):
        """load_scenario raises ScenarioError for missing files."""
        path = tmp_path / "does_not_exist.py"
        with pytest.raises(ScenarioError, match="not found"):
            load_scenario(path)

    def test_load_scenario_not_python_file(self, tmp_path: Path):
        """load_scenario raises ScenarioError for non-.py files."""
        path = tmp_path / "scenario.txt"
        path.write_text("not python")
        with pytest.raises(ScenarioError, match=r"must be a \.py file"):
            load_scenario(path)

    def test_load_scenario_no_scenario_in_file(self, tmp_path: Path):
        """load_scenario raises ScenarioError if no @scenario found."""
        code = """\
from __future__ import annotations

x = 42
"""
        path = tmp_path / "empty_scenario.py"
        path.write_text(code)
        with pytest.raises(ScenarioError, match="No @scenario-decorated class"):
            load_scenario(path)

    def test_load_scenario_import_error(self, tmp_path: Path):
        """load_scenario raises ScenarioError on import failures."""
        code = """\
from __future__ import annotations

import nonexistent_module_12345  # noqa: F401
"""
        path = tmp_path / "broken_scenario.py"
        path.write_text(code)
        with pytest.raises(ScenarioError, match="Failed to import"):
            load_scenario(path)

    def test_load_scenario_with_conftest_fixture(self, sample_scenario_path: Path):
        """load_scenario works with the conftest sample_scenario_path fixture."""
        result = load_scenario(sample_scenario_path)
        assert isinstance(result, ScenarioDefinition)
        assert result.name == "Test Scenario"
