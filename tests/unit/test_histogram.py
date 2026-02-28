"""Tests for HdrHistogramWrapper."""

from __future__ import annotations

from loadforge.metrics.histogram import HdrHistogramWrapper


class TestHdrHistogramWrapper:
    def test_record_and_get_percentile(self):
        h = HdrHistogramWrapper()
        # Record 100 values from 1.0 to 100.0 ms
        for i in range(1, 101):
            h.record_latency_ms(float(i))

        # p50 should be around 50ms
        p50 = h.get_percentile(50.0)
        assert 49.0 <= p50 <= 51.0

        # p99 should be around 99ms
        p99 = h.get_percentile(99.0)
        assert 98.0 <= p99 <= 101.0

    def test_empty_histogram_returns_zeros(self):
        h = HdrHistogramWrapper()
        assert h.get_percentile(50.0) == 0.0
        assert h.get_percentile(99.0) == 0.0
        assert h.get_min() == 0.0
        assert h.get_max() == 0.0
        assert h.get_mean() == 0.0
        assert h.get_total_count() == 0

    def test_record_latency_ms_converts_correctly(self):
        h = HdrHistogramWrapper()
        h.record_latency_ms(10.0)  # 10ms = 10000us
        # The only recorded value, so all percentiles should be ~10ms
        assert 9.5 <= h.get_percentile(50.0) <= 10.5

    def test_min_max_mean(self):
        h = HdrHistogramWrapper()
        h.record_latency_ms(5.0)
        h.record_latency_ms(15.0)
        h.record_latency_ms(25.0)

        assert 4.5 <= h.get_min() <= 5.5
        assert 24.5 <= h.get_max() <= 25.5
        # Mean should be around 15ms
        mean = h.get_mean()
        assert 14.0 <= mean <= 16.0

    def test_total_count(self):
        h = HdrHistogramWrapper()
        assert h.get_total_count() == 0
        h.record_latency_ms(10.0)
        assert h.get_total_count() == 1
        h.record_latency_ms(20.0)
        assert h.get_total_count() == 2

    def test_reset_clears_histogram(self):
        h = HdrHistogramWrapper()
        h.record_latency_ms(10.0)
        h.record_latency_ms(20.0)
        assert h.get_total_count() == 2

        h.reset()
        assert h.get_total_count() == 0
        assert h.get_percentile(50.0) == 0.0
        assert h.get_min() == 0.0
        assert h.get_max() == 0.0

    def test_add_merges_histograms(self):
        h1 = HdrHistogramWrapper()
        h2 = HdrHistogramWrapper()

        # h1 has low values
        for i in range(1, 51):
            h1.record_latency_ms(float(i))

        # h2 has high values
        for i in range(51, 101):
            h2.record_latency_ms(float(i))

        h1.add(h2)
        assert h1.get_total_count() == 100

        # After merge, p50 should be around 50ms
        p50 = h1.get_percentile(50.0)
        assert 49.0 <= p50 <= 51.0

        # Min should be from h1, max from h2
        assert h1.get_min() <= 1.5
        assert h1.get_max() >= 99.0

    def test_clamps_extreme_values(self):
        h = HdrHistogramWrapper()
        # Very small value (below 1us = 0.001ms) gets clamped to 1us
        h.record_latency_ms(0.0001)
        assert h.get_total_count() == 1
        assert h.get_min() > 0.0

        # Very large value (above 60s) gets clamped to 60s
        # HDR histogram quantization at 3 significant digits can add
        # up to ~0.1% error at the boundary
        h.record_latency_ms(100_000.0)
        assert h.get_total_count() == 2
        assert h.get_max() <= 60_100.0

    def test_record_returns_true_on_success(self):
        h = HdrHistogramWrapper()
        assert h.record_latency_ms(10.0) is True

    def test_multiple_percentiles(self):
        h = HdrHistogramWrapper()
        for i in range(1, 1001):
            h.record_latency_ms(float(i))

        p50 = h.get_percentile(50.0)
        p75 = h.get_percentile(75.0)
        p90 = h.get_percentile(90.0)
        p95 = h.get_percentile(95.0)
        p99 = h.get_percentile(99.0)
        p999 = h.get_percentile(99.9)

        # Percentiles should be in ascending order
        assert p50 < p75 < p90 < p95 < p99 < p999

        # Rough accuracy checks
        assert 490.0 <= p50 <= 510.0
        assert 740.0 <= p75 <= 760.0
        assert 890.0 <= p90 <= 910.0
