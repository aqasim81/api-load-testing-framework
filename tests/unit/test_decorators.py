"""Tests for the @scenario, @task, @setup, and @teardown decorators."""

from __future__ import annotations

import pytest

from loadforge._internal.errors import ScenarioError
from loadforge.dsl.decorators import scenario, setup, task, teardown
from loadforge.dsl.scenario import ScenarioDefinition, registry


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the global scenario registry before each test."""
    registry.clear()
    yield
    registry.clear()


# =========================================================================
# @scenario decorator
# =========================================================================


class TestScenarioDecorator:
    """Tests for the @scenario class decorator."""

    def test_creates_scenario_definition(self):
        """@scenario transforms a class into a ScenarioDefinition."""

        @scenario(name="Test", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert isinstance(MyScenario, ScenarioDefinition)

    def test_sets_name_and_base_url(self):
        """ScenarioDefinition has correct name and base_url."""

        @scenario(name="My Test", base_url="http://example.com")
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert MyScenario.name == "My Test"
        assert MyScenario.base_url == "http://example.com"

    def test_preserves_original_class(self):
        """ScenarioDefinition.cls is the original class."""

        class _Original:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        result = scenario(name="Test", base_url="http://localhost")(_Original)
        assert result.cls is _Original

    def test_default_headers(self):
        """Custom default_headers are stored."""

        @scenario(
            name="Test",
            base_url="http://localhost",
            default_headers={"Authorization": "Bearer token"},
        )
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert MyScenario.default_headers == {"Authorization": "Bearer token"}

    def test_default_headers_empty_when_not_specified(self):
        """Default headers is an empty dict when not specified."""

        @scenario(name="Test", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert MyScenario.default_headers == {}

    def test_custom_think_time(self):
        """Custom think_time is stored."""

        @scenario(name="Test", base_url="http://localhost", think_time=(1.0, 3.0))
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert MyScenario.think_time == (1.0, 3.0)

    def test_default_think_time(self):
        """Default think_time is (0.5, 1.5)."""

        @scenario(name="Test", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert MyScenario.think_time == (0.5, 1.5)

    def test_registers_in_global_registry(self):
        """@scenario registers the definition in the global registry."""

        @scenario(name="Registered", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        assert registry.get("Registered") is MyScenario
        assert len(registry) == 1

    def test_no_tasks_raises_error(self):
        """@scenario with no @task methods raises ScenarioError."""
        with pytest.raises(ScenarioError, match="no @task methods"):

            @scenario(name="Empty", base_url="http://localhost")
            class EmptyScenario:
                async def not_a_task(self, client: object) -> None:
                    pass

    def test_sync_task_raises_error(self):
        """A sync method decorated with @task raises ScenarioError."""
        with pytest.raises(ScenarioError, match="must be an async function"):

            @scenario(name="Sync", base_url="http://localhost")
            class SyncScenario:
                @task(weight=1)
                def not_async(self, client: object) -> None:  # type: ignore[type-var]
                    pass

    def test_duplicate_scenario_name_raises_error(self):
        """Registering two scenarios with the same name raises ScenarioError."""

        @scenario(name="Duplicate", base_url="http://localhost")
        class First:
            @task(weight=1)
            async def do_something(self, client: object) -> None:
                pass

        with pytest.raises(ScenarioError, match="already registered"):

            @scenario(name="Duplicate", base_url="http://localhost")
            class Second:
                @task(weight=1)
                async def do_something(self, client: object) -> None:
                    pass


# =========================================================================
# @task decorator
# =========================================================================


class TestTaskDecorator:
    """Tests for the @task method decorator."""

    def test_collects_tasks(self):
        """@task methods are collected into ScenarioDefinition.tasks."""

        @scenario(name="Tasks", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def task_a(self, client: object) -> None:
                pass

            @task(weight=2)
            async def task_b(self, client: object) -> None:
                pass

        assert len(MyScenario.tasks) == 2

    def test_task_weight(self):
        """@task(weight=N) stores the correct weight."""

        @scenario(name="Weighted", base_url="http://localhost")
        class MyScenario:
            @task(weight=5)
            async def heavy_task(self, client: object) -> None:
                pass

        assert MyScenario.tasks[0].weight == 5

    def test_task_default_weight(self):
        """Default weight is 1."""

        @scenario(name="Default", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def some_task(self, client: object) -> None:
                pass

        assert MyScenario.tasks[0].weight == 1

    def test_task_custom_name(self):
        """@task(name='Custom') overrides the method name."""

        @scenario(name="Named", base_url="http://localhost")
        class MyScenario:
            @task(weight=1, name="Custom Name")
            async def some_task(self, client: object) -> None:
                pass

        assert MyScenario.tasks[0].name == "Custom Name"

    def test_task_default_name_is_method_name(self):
        """Default task name is the method name."""

        @scenario(name="MethodName", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def get_items(self, client: object) -> None:
                pass

        assert MyScenario.tasks[0].name == "get_items"

    def test_task_stores_function_reference(self):
        """TaskDefinition.func is the original unbound method."""

        @scenario(name="FuncRef", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        # func should be callable
        assert callable(MyScenario.tasks[0].func)

    def test_task_weight_zero_raises_error(self):
        """@task(weight=0) raises ScenarioError."""
        with pytest.raises(ScenarioError, match="weight must be >= 1"):
            task(weight=0)

    def test_task_weight_negative_raises_error(self):
        """@task(weight=-1) raises ScenarioError."""
        with pytest.raises(ScenarioError, match="weight must be >= 1"):
            task(weight=-1)


# =========================================================================
# @setup decorator
# =========================================================================


class TestSetupDecorator:
    """Tests for the @setup method decorator."""

    def test_registers_setup_func(self):
        """@setup registers the method as setup_func."""

        @scenario(name="WithSetup", base_url="http://localhost")
        class MyScenario:
            @setup
            async def on_start(self, client: object) -> None:
                pass

            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        assert MyScenario.setup_func is not None

    def test_no_setup_is_none(self):
        """setup_func is None when no @setup method exists."""

        @scenario(name="NoSetup", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        assert MyScenario.setup_func is None

    def test_sync_setup_raises_error(self):
        """A sync @setup method raises ScenarioError."""
        with pytest.raises(ScenarioError, match="must be an async function"):

            @scenario(name="SyncSetup", base_url="http://localhost")
            class MyScenario:
                @setup
                def on_start(self, client: object) -> None:  # type: ignore[type-var]
                    pass

                @task(weight=1)
                async def do_work(self, client: object) -> None:
                    pass

    def test_multiple_setup_raises_error(self):
        """Multiple @setup methods raise ScenarioError."""
        with pytest.raises(ScenarioError, match="multiple @setup"):

            @scenario(name="MultiSetup", base_url="http://localhost")
            class MyScenario:
                @setup
                async def on_start_1(self, client: object) -> None:
                    pass

                @setup
                async def on_start_2(self, client: object) -> None:
                    pass

                @task(weight=1)
                async def do_work(self, client: object) -> None:
                    pass


# =========================================================================
# @teardown decorator
# =========================================================================


class TestTeardownDecorator:
    """Tests for the @teardown method decorator."""

    def test_registers_teardown_func(self):
        """@teardown registers the method as teardown_func."""

        @scenario(name="WithTeardown", base_url="http://localhost")
        class MyScenario:
            @teardown
            async def on_stop(self, client: object) -> None:
                pass

            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        assert MyScenario.teardown_func is not None

    def test_no_teardown_is_none(self):
        """teardown_func is None when no @teardown method exists."""

        @scenario(name="NoTeardown", base_url="http://localhost")
        class MyScenario:
            @task(weight=1)
            async def do_work(self, client: object) -> None:
                pass

        assert MyScenario.teardown_func is None

    def test_sync_teardown_raises_error(self):
        """A sync @teardown method raises ScenarioError."""
        with pytest.raises(ScenarioError, match="must be an async function"):

            @scenario(name="SyncTeardown", base_url="http://localhost")
            class MyScenario:
                @teardown
                def on_stop(self, client: object) -> None:  # type: ignore[type-var]
                    pass

                @task(weight=1)
                async def do_work(self, client: object) -> None:
                    pass

    def test_multiple_teardown_raises_error(self):
        """Multiple @teardown methods raise ScenarioError."""
        with pytest.raises(ScenarioError, match="multiple @teardown"):

            @scenario(name="MultiTeardown", base_url="http://localhost")
            class MyScenario:
                @teardown
                async def on_stop_1(self, client: object) -> None:
                    pass

                @teardown
                async def on_stop_2(self, client: object) -> None:
                    pass

                @task(weight=1)
                async def do_work(self, client: object) -> None:
                    pass


# =========================================================================
# Full scenario with setup + teardown + multiple tasks
# =========================================================================


class TestFullScenario:
    """Tests for a complete scenario with all decorator types."""

    def test_full_scenario(self):
        """A scenario with setup, teardown, and multiple tasks."""

        @scenario(
            name="Full",
            base_url="http://localhost",
            default_headers={"X-Test": "true"},
            think_time=(0.1, 0.5),
        )
        class FullScenario:
            @setup
            async def on_start(self, client: object) -> None:
                pass

            @task(weight=5, name="List Items")
            async def list_items(self, client: object) -> None:
                pass

            @task(weight=3, name="Get Item")
            async def get_item(self, client: object) -> None:
                pass

            @task(weight=1)
            async def create_item(self, client: object) -> None:
                pass

            @teardown
            async def on_stop(self, client: object) -> None:
                pass

        assert isinstance(FullScenario, ScenarioDefinition)
        assert FullScenario.name == "Full"
        assert FullScenario.base_url == "http://localhost"
        assert FullScenario.default_headers == {"X-Test": "true"}
        assert FullScenario.think_time == (0.1, 0.5)
        assert len(FullScenario.tasks) == 3
        assert FullScenario.setup_func is not None
        assert FullScenario.teardown_func is not None

        # Verify task names and weights
        task_map = {t.name: t.weight for t in FullScenario.tasks}
        assert task_map["List Items"] == 5
        assert task_map["Get Item"] == 3
        assert task_map["create_item"] == 1
