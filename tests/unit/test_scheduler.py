"""Tests for the concurrency scheduler."""

from __future__ import annotations

from loadforge.engine.scheduler import ScaleCommand, ScaleDirection, Scheduler
from loadforge.patterns.composite import CompositePattern
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.ramp import RampPattern


class TestScaleCommand:
    """Tests for the ScaleCommand dataclass."""

    def test_fields_are_set(self) -> None:
        cmd = ScaleCommand(
            elapsed_seconds=1.0,
            target_concurrency=10,
            direction=ScaleDirection.UP,
            delta=10,
        )
        assert cmd.elapsed_seconds == 1.0
        assert cmd.target_concurrency == 10
        assert cmd.direction == ScaleDirection.UP
        assert cmd.delta == 10

    def test_frozen_dataclass(self) -> None:
        cmd = ScaleCommand(
            elapsed_seconds=0.0,
            target_concurrency=5,
            direction=ScaleDirection.HOLD,
            delta=0,
        )
        try:
            cmd.delta = 99  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            msg = "ScaleCommand should be frozen"
            raise AssertionError(msg)


class TestScheduler:
    """Tests for the Scheduler class."""

    def test_constant_pattern_first_command_scales_up(self) -> None:
        scheduler = Scheduler(ConstantPattern(users=10), duration_seconds=5.0)
        commands = list(scheduler.iter_commands())
        assert commands[0].direction == ScaleDirection.UP
        assert commands[0].target_concurrency == 10
        assert commands[0].delta == 10

    def test_constant_pattern_subsequent_commands_hold(self) -> None:
        scheduler = Scheduler(ConstantPattern(users=10), duration_seconds=5.0)
        commands = list(scheduler.iter_commands())
        for cmd in commands[1:]:
            assert cmd.direction == ScaleDirection.HOLD
            assert cmd.delta == 0
            assert cmd.target_concurrency == 10

    def test_ramp_up_emits_up_commands(self) -> None:
        scheduler = Scheduler(
            RampPattern(start_users=0, end_users=100, ramp_duration=10.0),
            duration_seconds=10.0,
        )
        commands = list(scheduler.iter_commands())
        # First command should be HOLD (0->0) since ramp starts at 0
        # Subsequent commands should be UP as concurrency increases
        up_commands = [c for c in commands if c.direction == ScaleDirection.UP]
        assert len(up_commands) > 0

    def test_ramp_down_emits_down_commands(self) -> None:
        scheduler = Scheduler(
            RampPattern(start_users=100, end_users=0, ramp_duration=10.0),
            duration_seconds=10.0,
        )
        commands = list(scheduler.iter_commands())
        down_commands = [c for c in commands if c.direction == ScaleDirection.DOWN]
        assert len(down_commands) > 0

    def test_first_command_starts_from_zero(self) -> None:
        scheduler = Scheduler(ConstantPattern(users=50), duration_seconds=3.0)
        commands = list(scheduler.iter_commands())
        first = commands[0]
        assert first.elapsed_seconds == 0.0
        assert first.delta == 50
        assert first.direction == ScaleDirection.UP

    def test_delta_is_absolute_difference(self) -> None:
        scheduler = Scheduler(
            RampPattern(start_users=100, end_users=0, ramp_duration=10.0),
            duration_seconds=10.0,
        )
        commands = list(scheduler.iter_commands())
        for cmd in commands:
            assert cmd.delta >= 0

    def test_tick_interval_matches_pattern(self) -> None:
        scheduler = Scheduler(
            ConstantPattern(users=5),
            duration_seconds=5.0,
            tick_interval=1.0,
        )
        commands = list(scheduler.iter_commands())
        for i, cmd in enumerate(commands):
            assert abs(cmd.elapsed_seconds - i * 1.0) < 0.01

    def test_custom_tick_interval(self) -> None:
        scheduler = Scheduler(
            ConstantPattern(users=5),
            duration_seconds=4.0,
            tick_interval=2.0,
        )
        commands = list(scheduler.iter_commands())
        # Duration=4, tick=2 -> ticks at 0, 2, 4 -> 3 commands
        assert len(commands) == 3
        assert abs(commands[0].elapsed_seconds - 0.0) < 0.01
        assert abs(commands[1].elapsed_seconds - 2.0) < 0.01
        assert abs(commands[2].elapsed_seconds - 4.0) < 0.01

    def test_total_ticks_property(self) -> None:
        scheduler = Scheduler(
            ConstantPattern(users=10),
            duration_seconds=5.0,
            tick_interval=1.0,
        )
        assert scheduler.total_ticks == 6  # 0, 1, 2, 3, 4, 5

    def test_composite_pattern_produces_mixed_directions(self) -> None:
        pattern = CompositePattern(
            phases=[
                (RampPattern(start_users=0, end_users=50, ramp_duration=5.0), 5.0),
                (RampPattern(start_users=50, end_users=10, ramp_duration=5.0), 5.0),
            ]
        )
        scheduler = Scheduler(pattern, duration_seconds=10.0)
        commands = list(scheduler.iter_commands())
        directions = {cmd.direction for cmd in commands}
        assert ScaleDirection.UP in directions
        assert ScaleDirection.DOWN in directions

    def test_all_commands_have_valid_fields(self) -> None:
        scheduler = Scheduler(
            RampPattern(start_users=0, end_users=20, ramp_duration=5.0),
            duration_seconds=5.0,
        )
        for cmd in scheduler.iter_commands():
            assert cmd.elapsed_seconds >= 0.0
            assert cmd.target_concurrency >= 0
            assert cmd.delta >= 0
            assert isinstance(cmd.direction, ScaleDirection)
