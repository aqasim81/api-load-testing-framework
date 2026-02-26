"""Tests for traffic pattern generators."""

from __future__ import annotations

import pytest

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern
from loadforge.patterns.composite import CompositePattern
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.diurnal import DiurnalPattern
from loadforge.patterns.ramp import RampPattern
from loadforge.patterns.spike import SpikePattern
from loadforge.patterns.step import StepPattern

# =========================================================================
# ConstantPattern
# =========================================================================


class TestConstantPattern:
    """Tests for ConstantPattern."""

    def test_yields_constant_value(self) -> None:
        """Every tick should yield the same user count."""
        pattern = ConstantPattern(users=50)
        ticks = list(pattern.iter_concurrency(duration_seconds=5.0))
        for _, users in ticks:
            assert users == 50

    def test_tick_count(self) -> None:
        """Number of ticks matches expected count for duration and interval."""
        pattern = ConstantPattern(users=10)
        ticks = list(pattern.iter_concurrency(duration_seconds=5.0, tick_interval=1.0))
        # t=0, 1, 2, 3, 4, 5 -> 6 ticks
        assert len(ticks) == 6

    def test_elapsed_times(self) -> None:
        """Elapsed times should increment by tick_interval."""
        pattern = ConstantPattern(users=10)
        ticks = list(pattern.iter_concurrency(duration_seconds=3.0, tick_interval=1.0))
        elapsed_values = [t for t, _ in ticks]
        assert elapsed_values == pytest.approx([0.0, 1.0, 2.0, 3.0])

    def test_custom_tick_interval(self) -> None:
        """Custom tick_interval produces fewer/more ticks."""
        pattern = ConstantPattern(users=10)
        ticks = list(pattern.iter_concurrency(duration_seconds=4.0, tick_interval=2.0))
        elapsed_values = [t for t, _ in ticks]
        assert elapsed_values == pytest.approx([0.0, 2.0, 4.0])

    def test_describe(self) -> None:
        """describe() returns a meaningful string."""
        pattern = ConstantPattern(users=100)
        desc = pattern.describe()
        assert "100" in desc
        assert desc  # non-empty

    def test_is_load_pattern(self) -> None:
        """ConstantPattern is a LoadPattern."""
        pattern = ConstantPattern(users=1)
        assert isinstance(pattern, LoadPattern)

    def test_rejects_zero_users(self) -> None:
        """users < 1 raises ConfigError."""
        with pytest.raises(ConfigError, match="users"):
            ConstantPattern(users=0)

    def test_rejects_negative_users(self) -> None:
        """Negative users raises ConfigError."""
        with pytest.raises(ConfigError, match="users"):
            ConstantPattern(users=-5)

    def test_rejects_zero_duration(self) -> None:
        """duration_seconds <= 0 raises ConfigError."""
        pattern = ConstantPattern(users=10)
        with pytest.raises(ConfigError, match="duration_seconds"):
            list(pattern.iter_concurrency(duration_seconds=0.0))

    def test_rejects_zero_tick_interval(self) -> None:
        """tick_interval <= 0 raises ConfigError."""
        pattern = ConstantPattern(users=10)
        with pytest.raises(ConfigError, match="tick_interval"):
            list(pattern.iter_concurrency(duration_seconds=5.0, tick_interval=0.0))


# =========================================================================
# RampPattern
# =========================================================================


class TestRampPattern:
    """Tests for RampPattern."""

    def test_starts_at_start_users(self) -> None:
        """First tick should yield start_users."""
        pattern = RampPattern(start_users=10, end_users=100, ramp_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        assert ticks[0][1] == 10

    def test_ends_at_end_users(self) -> None:
        """Last tick within ramp should yield end_users."""
        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        assert ticks[-1][1] == 100

    def test_increases_linearly(self) -> None:
        """Values should increase monotonically for an upward ramp."""
        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        users_values = [u for _, u in ticks]
        for i in range(1, len(users_values)):
            assert users_values[i] >= users_values[i - 1]

    def test_decreasing_ramp(self) -> None:
        """Ramp from high to low should decrease monotonically."""
        pattern = RampPattern(start_users=100, end_users=0, ramp_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        users_values = [u for _, u in ticks]
        for i in range(1, len(users_values)):
            assert users_values[i] <= users_values[i - 1]

    def test_holds_after_ramp(self) -> None:
        """After ramp_duration, concurrency holds at end_users."""
        pattern = RampPattern(start_users=0, end_users=50, ramp_duration=5.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        # Ticks after t=5 should all be 50
        post_ramp = [(t, u) for t, u in ticks if t >= 5.0]
        for _, users in post_ramp:
            assert users == 50

    def test_midpoint_value(self) -> None:
        """At 50% of ramp_duration, concurrency should be ~50% of the way."""
        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        # t=5 should be ~50
        mid_tick = next(u for t, u in ticks if t == pytest.approx(5.0))
        assert mid_tick == 50

    def test_describe(self) -> None:
        """describe() returns a meaningful string."""
        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=60.0)
        desc = pattern.describe()
        assert "0" in desc
        assert "100" in desc

    def test_is_load_pattern(self) -> None:
        """RampPattern is a LoadPattern."""
        assert isinstance(
            RampPattern(start_users=0, end_users=10, ramp_duration=5.0),
            LoadPattern,
        )

    def test_rejects_negative_start(self) -> None:
        """Negative start_users raises ConfigError."""
        with pytest.raises(ConfigError, match="start_users"):
            RampPattern(start_users=-1, end_users=10, ramp_duration=5.0)

    def test_rejects_negative_end(self) -> None:
        """Negative end_users raises ConfigError."""
        with pytest.raises(ConfigError, match="end_users"):
            RampPattern(start_users=0, end_users=-1, ramp_duration=5.0)

    def test_rejects_zero_ramp_duration(self) -> None:
        """ramp_duration <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="ramp_duration"):
            RampPattern(start_users=0, end_users=10, ramp_duration=0.0)

    def test_rejects_equal_start_end(self) -> None:
        """start_users == end_users raises ConfigError."""
        with pytest.raises(ConfigError, match="start_users and end_users must differ"):
            RampPattern(start_users=50, end_users=50, ramp_duration=10.0)


# =========================================================================
# StepPattern
# =========================================================================


class TestStepPattern:
    """Tests for StepPattern."""

    def test_starts_at_start_users(self) -> None:
        """First tick yields start_users."""
        pattern = StepPattern(start_users=10, step_size=10, step_duration=5.0, steps=3)
        ticks = list(pattern.iter_concurrency(duration_seconds=20.0))
        assert ticks[0][1] == 10

    def test_staircase_shape(self) -> None:
        """Values increase in discrete steps at step boundaries."""
        pattern = StepPattern(start_users=10, step_size=10, step_duration=5.0, steps=3)
        ticks = list(pattern.iter_concurrency(duration_seconds=20.0))
        # t=0-4: 10, t=5-9: 20, t=10-14: 30, t=15+: 40
        values_by_range: dict[str, set[int]] = {
            "0-4": set(),
            "5-9": set(),
            "10-14": set(),
            "15+": set(),
        }
        for t, u in ticks:
            if t < 5:
                values_by_range["0-4"].add(u)
            elif t < 10:
                values_by_range["5-9"].add(u)
            elif t < 15:
                values_by_range["10-14"].add(u)
            else:
                values_by_range["15+"].add(u)
        assert values_by_range["0-4"] == {10}
        assert values_by_range["5-9"] == {20}
        assert values_by_range["10-14"] == {30}
        assert values_by_range["15+"] == {40}

    def test_holds_after_all_steps(self) -> None:
        """After all steps complete, concurrency holds at final level."""
        pattern = StepPattern(start_users=10, step_size=10, step_duration=5.0, steps=2)
        ticks = list(pattern.iter_concurrency(duration_seconds=20.0))
        # Final level = 10 + 10*2 = 30
        post_steps = [u for t, u in ticks if t >= 10.0]
        for users in post_steps:
            assert users == 30

    def test_final_level(self) -> None:
        """Final concurrency is start + step_size * steps."""
        pattern = StepPattern(start_users=5, step_size=15, step_duration=3.0, steps=4)
        ticks = list(pattern.iter_concurrency(duration_seconds=20.0))
        expected_final = 5 + 15 * 4  # 65
        assert ticks[-1][1] == expected_final

    def test_describe(self) -> None:
        """describe() returns a meaningful string."""
        pattern = StepPattern(start_users=10, step_size=5, step_duration=10.0, steps=3)
        desc = pattern.describe()
        assert "10" in desc
        assert "25" in desc  # final = 10 + 5*3

    def test_is_load_pattern(self) -> None:
        """StepPattern is a LoadPattern."""
        assert isinstance(
            StepPattern(start_users=1, step_size=1, step_duration=1.0, steps=1),
            LoadPattern,
        )

    def test_rejects_zero_start(self) -> None:
        """start_users <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="start_users"):
            StepPattern(start_users=0, step_size=10, step_duration=5.0, steps=3)

    def test_rejects_zero_step_size(self) -> None:
        """step_size <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="step_size"):
            StepPattern(start_users=10, step_size=0, step_duration=5.0, steps=3)

    def test_rejects_zero_step_duration(self) -> None:
        """step_duration <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="step_duration"):
            StepPattern(start_users=10, step_size=10, step_duration=0.0, steps=3)

    def test_rejects_zero_steps(self) -> None:
        """steps <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="steps"):
            StepPattern(start_users=10, step_size=10, step_duration=5.0, steps=0)


# =========================================================================
# SpikePattern
# =========================================================================


class TestSpikePattern:
    """Tests for SpikePattern."""

    def test_starts_at_spike_peak(self) -> None:
        """At t=0, concurrency should be at spike_users (peak)."""
        pattern = SpikePattern(base_users=100, spike_users=1000, spike_duration=30.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=60.0))
        assert ticks[0][1] == 1000

    def test_decays_toward_base(self) -> None:
        """Concurrency should decay from spike toward base over spike_duration."""
        pattern = SpikePattern(base_users=100, spike_users=1000, spike_duration=30.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=30.0))
        users_values = [u for _, u in ticks]
        # Should be monotonically decreasing (or equal)
        for i in range(1, len(users_values)):
            assert users_values[i] <= users_values[i - 1]

    def test_holds_base_after_spike(self) -> None:
        """After spike_duration, concurrency holds at base_users."""
        pattern = SpikePattern(base_users=100, spike_users=1000, spike_duration=10.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=20.0))
        post_spike = [u for t, u in ticks if t >= 10.0]
        for users in post_spike:
            assert users == 100

    def test_exponential_decay_shape(self) -> None:
        """Early decay should be steeper than late decay (exponential)."""
        pattern = SpikePattern(base_users=0, spike_users=1000, spike_duration=30.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=30.0))
        # Compare first-half drop vs second-half drop
        users_at_0 = ticks[0][1]
        users_at_15 = next(u for t, u in ticks if t == pytest.approx(15.0))
        users_at_29 = next(u for t, u in ticks if t == pytest.approx(29.0))
        first_half_drop = users_at_0 - users_at_15
        second_half_drop = users_at_15 - users_at_29
        assert first_half_drop > second_half_drop

    def test_describe(self) -> None:
        """describe() returns a meaningful string."""
        pattern = SpikePattern(base_users=50, spike_users=500, spike_duration=20.0)
        desc = pattern.describe()
        assert "50" in desc
        assert "500" in desc

    def test_is_load_pattern(self) -> None:
        """SpikePattern is a LoadPattern."""
        assert isinstance(
            SpikePattern(base_users=0, spike_users=10, spike_duration=5.0),
            LoadPattern,
        )

    def test_rejects_spike_lte_base(self) -> None:
        """spike_users <= base_users raises ConfigError."""
        with pytest.raises(ConfigError, match="spike_users"):
            SpikePattern(base_users=100, spike_users=100, spike_duration=10.0)

    def test_rejects_spike_below_base(self) -> None:
        """spike_users < base_users raises ConfigError."""
        with pytest.raises(ConfigError, match="spike_users"):
            SpikePattern(base_users=100, spike_users=50, spike_duration=10.0)

    def test_rejects_negative_base(self) -> None:
        """Negative base_users raises ConfigError."""
        with pytest.raises(ConfigError, match="base_users"):
            SpikePattern(base_users=-1, spike_users=10, spike_duration=5.0)

    def test_rejects_zero_spike_duration(self) -> None:
        """spike_duration <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="spike_duration"):
            SpikePattern(base_users=10, spike_users=100, spike_duration=0.0)


# =========================================================================
# DiurnalPattern
# =========================================================================


class TestDiurnalPattern:
    """Tests for DiurnalPattern."""

    def test_starts_at_min(self) -> None:
        """At t=0, concurrency should be at min_users (trough)."""
        pattern = DiurnalPattern(min_users=50, max_users=500, period=100.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=100.0))
        assert ticks[0][1] == 50

    def test_peaks_at_half_period(self) -> None:
        """At t=period/2, concurrency should be at max_users (peak)."""
        pattern = DiurnalPattern(min_users=50, max_users=500, period=100.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=100.0))
        peak_tick = next(u for t, u in ticks if t == pytest.approx(50.0))
        assert peak_tick == 500

    def test_returns_to_min_at_full_period(self) -> None:
        """At t=period, concurrency should return to min_users."""
        pattern = DiurnalPattern(min_users=50, max_users=500, period=100.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=100.0))
        assert ticks[-1][1] == 50

    def test_sine_wave_shape(self) -> None:
        """Values should increase in first half and decrease in second half."""
        pattern = DiurnalPattern(min_users=0, max_users=100, period=100.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=100.0))
        first_half = [u for t, u in ticks if 0 < t <= 50]
        second_half = [u for t, u in ticks if 50 < t <= 100]
        # First half: increasing
        for i in range(1, len(first_half)):
            assert first_half[i] >= first_half[i - 1]
        # Second half: decreasing
        for i in range(1, len(second_half)):
            assert second_half[i] <= second_half[i - 1]

    def test_quarter_period_value(self) -> None:
        """At t=period/4, concurrency should be midpoint (sin=0 -> 50%)."""
        pattern = DiurnalPattern(min_users=0, max_users=100, period=100.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=100.0))
        quarter_tick = next(u for t, u in ticks if t == pytest.approx(25.0))
        assert quarter_tick == 50

    def test_values_within_bounds(self) -> None:
        """All values should be between min_users and max_users."""
        pattern = DiurnalPattern(min_users=20, max_users=200, period=60.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=120.0))
        for _, users in ticks:
            assert 20 <= users <= 200

    def test_describe(self) -> None:
        """describe() returns a meaningful string."""
        pattern = DiurnalPattern(min_users=10, max_users=100, period=600.0)
        desc = pattern.describe()
        assert "10" in desc
        assert "100" in desc

    def test_is_load_pattern(self) -> None:
        """DiurnalPattern is a LoadPattern."""
        assert isinstance(
            DiurnalPattern(min_users=0, max_users=10, period=10.0),
            LoadPattern,
        )

    def test_rejects_negative_min(self) -> None:
        """Negative min_users raises ConfigError."""
        with pytest.raises(ConfigError, match="min_users"):
            DiurnalPattern(min_users=-1, max_users=10, period=10.0)

    def test_rejects_max_lte_min(self) -> None:
        """max_users <= min_users raises ConfigError."""
        with pytest.raises(ConfigError, match="max_users"):
            DiurnalPattern(min_users=50, max_users=50, period=10.0)

    def test_rejects_zero_period(self) -> None:
        """period <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="period"):
            DiurnalPattern(min_users=0, max_users=100, period=0.0)


# =========================================================================
# CompositePattern
# =========================================================================


class TestCompositePattern:
    """Tests for CompositePattern."""

    def test_chains_two_patterns(self) -> None:
        """Two constant patterns chained should produce correct values."""
        p1 = ConstantPattern(users=10)
        p2 = ConstantPattern(users=50)
        composite = CompositePattern(phases=[(p1, 3.0), (p2, 3.0)])
        ticks = list(composite.iter_concurrency(duration_seconds=6.0))
        # Phase 1 yields at t=0,1,2,3 (all 10). Phase 2 yields at t=3,4,5,6 (all 50).
        # At t=3.0 both phases emit a tick (boundary overlap).
        phase1_only = {u for t, u in ticks if t < 3.0}
        phase2_only = {u for t, u in ticks if t > 3.0}
        assert phase1_only == {10}
        assert phase2_only == {50}

    def test_elapsed_time_is_continuous(self) -> None:
        """Elapsed times should be continuous across phases."""
        p1 = ConstantPattern(users=10)
        p2 = ConstantPattern(users=20)
        composite = CompositePattern(phases=[(p1, 3.0), (p2, 3.0)])
        ticks = list(composite.iter_concurrency(duration_seconds=6.0))
        elapsed_values = [t for t, _ in ticks]
        # Should start at 0 and increase monotonically
        assert elapsed_values[0] == pytest.approx(0.0)
        for i in range(1, len(elapsed_values)):
            assert elapsed_values[i] >= elapsed_values[i - 1]

    def test_total_ticks_across_phases(self) -> None:
        """Total tick count should reflect all phases."""
        p1 = ConstantPattern(users=10)
        p2 = ConstantPattern(users=20)
        composite = CompositePattern(phases=[(p1, 2.0), (p2, 2.0)])
        ticks = list(composite.iter_concurrency(duration_seconds=4.0))
        # Phase 1: t=0, 1, 2 (3 ticks) + Phase 2: t=2, 3, 4 (3 ticks) = 6 ticks
        assert len(ticks) == 6

    def test_ramp_then_constant(self) -> None:
        """A ramp followed by constant should produce correct shape."""
        ramp = RampPattern(start_users=0, end_users=100, ramp_duration=5.0)
        hold = ConstantPattern(users=100)
        composite = CompositePattern(phases=[(ramp, 5.0), (hold, 5.0)])
        ticks = list(composite.iter_concurrency(duration_seconds=10.0))
        # First tick should be 0 (ramp start)
        assert ticks[0][1] == 0
        # After ramp (t>=5), all should be 100
        hold_values = [u for t, u in ticks if t >= 5.0]
        for users in hold_values:
            assert users == 100

    def test_single_phase(self) -> None:
        """A single-phase composite should behave like the inner pattern."""
        inner = ConstantPattern(users=42)
        composite = CompositePattern(phases=[(inner, 5.0)])
        ticks = list(composite.iter_concurrency(duration_seconds=5.0))
        for _, users in ticks:
            assert users == 42

    def test_describe(self) -> None:
        """describe() returns a meaningful multi-line string."""
        p1 = ConstantPattern(users=10)
        p2 = ConstantPattern(users=50)
        composite = CompositePattern(phases=[(p1, 5.0), (p2, 5.0)])
        desc = composite.describe()
        assert "2 phases" in desc
        assert "10.0s total" in desc

    def test_is_load_pattern(self) -> None:
        """CompositePattern is a LoadPattern."""
        assert isinstance(
            CompositePattern(phases=[(ConstantPattern(users=1), 1.0)]),
            LoadPattern,
        )

    def test_rejects_empty_phases(self) -> None:
        """Empty phases list raises ConfigError."""
        with pytest.raises(ConfigError, match="phases"):
            CompositePattern(phases=[])

    def test_rejects_zero_duration_in_phase(self) -> None:
        """A phase with duration <= 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="duration"):
            CompositePattern(phases=[(ConstantPattern(users=10), 0.0)])

    def test_rejects_negative_duration_in_phase(self) -> None:
        """A phase with negative duration raises ConfigError."""
        with pytest.raises(ConfigError, match="duration"):
            CompositePattern(phases=[(ConstantPattern(users=10), -5.0)])


# =========================================================================
# Cross-pattern tests
# =========================================================================


class TestPatternInterface:
    """Tests verifying all patterns conform to the LoadPattern interface."""

    @pytest.fixture(
        params=[
            ConstantPattern(users=10),
            RampPattern(start_users=0, end_users=100, ramp_duration=10.0),
            StepPattern(start_users=10, step_size=10, step_duration=5.0, steps=3),
            SpikePattern(base_users=10, spike_users=100, spike_duration=10.0),
            DiurnalPattern(min_users=10, max_users=100, period=60.0),
            CompositePattern(phases=[(ConstantPattern(users=10), 5.0)]),
        ],
    )
    def pattern(self, request: pytest.FixtureRequest) -> LoadPattern:
        """Parametrize over all pattern types."""
        result: LoadPattern = request.param
        return result

    def test_is_load_pattern_instance(self, pattern: LoadPattern) -> None:
        """All patterns are LoadPattern instances."""
        assert isinstance(pattern, LoadPattern)

    def test_describe_returns_non_empty_string(self, pattern: LoadPattern) -> None:
        """describe() returns a non-empty string."""
        desc = pattern.describe()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_iter_concurrency_yields_tuples(self, pattern: LoadPattern) -> None:
        """iter_concurrency() yields (float, int) tuples."""
        ticks = list(pattern.iter_concurrency(duration_seconds=5.0))
        assert len(ticks) > 0
        for elapsed, users in ticks:
            assert isinstance(elapsed, float)
            assert isinstance(users, int)

    def test_concurrency_is_non_negative(self, pattern: LoadPattern) -> None:
        """All concurrency values should be >= 0."""
        ticks = list(pattern.iter_concurrency(duration_seconds=10.0))
        for _, users in ticks:
            assert users >= 0

    def test_elapsed_starts_at_zero(self, pattern: LoadPattern) -> None:
        """First tick should have elapsed == 0.0."""
        ticks = list(pattern.iter_concurrency(duration_seconds=5.0))
        assert ticks[0][0] == pytest.approx(0.0)

    def test_elapsed_is_monotonic(self, pattern: LoadPattern) -> None:
        """Elapsed times should be monotonically non-decreasing."""
        ticks = list(pattern.iter_concurrency(duration_seconds=5.0))
        elapsed_values = [t for t, _ in ticks]
        for i in range(1, len(elapsed_values)):
            assert elapsed_values[i] >= elapsed_values[i - 1]
