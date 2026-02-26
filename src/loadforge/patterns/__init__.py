"""Traffic pattern generators for LoadForge.

This package provides six composable traffic patterns that define how the
target concurrency (virtual user count) changes over time during a load test.

All patterns implement the :class:`LoadPattern` interface and yield
``(elapsed_seconds, target_concurrency)`` tuples via :meth:`iter_concurrency`.
"""

from __future__ import annotations

from loadforge.patterns.base import LoadPattern
from loadforge.patterns.composite import CompositePattern
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.diurnal import DiurnalPattern
from loadforge.patterns.ramp import RampPattern
from loadforge.patterns.spike import SpikePattern
from loadforge.patterns.step import StepPattern

__all__ = [
    "CompositePattern",
    "ConstantPattern",
    "DiurnalPattern",
    "LoadPattern",
    "RampPattern",
    "SpikePattern",
    "StepPattern",
]
