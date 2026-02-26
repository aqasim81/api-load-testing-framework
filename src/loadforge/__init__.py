"""LoadForge — Forge realistic load tests as Python code."""

from __future__ import annotations

from loadforge.dsl.decorators import scenario, setup, task, teardown
from loadforge.dsl.http_client import HttpClient, RequestMetric
from loadforge.patterns.base import LoadPattern
from loadforge.patterns.composite import CompositePattern
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.diurnal import DiurnalPattern
from loadforge.patterns.ramp import RampPattern
from loadforge.patterns.spike import SpikePattern
from loadforge.patterns.step import StepPattern

__version__ = "0.1.0"

__all__ = [
    "CompositePattern",
    "ConstantPattern",
    "DiurnalPattern",
    "HttpClient",
    "LoadPattern",
    "RampPattern",
    "RequestMetric",
    "SpikePattern",
    "StepPattern",
    "scenario",
    "setup",
    "task",
    "teardown",
]
