"""LoadForge — Forge realistic load tests as Python code."""

from __future__ import annotations

from loadforge._internal.errors import (
    ConfigError,
    DashboardError,
    EngineError,
    LoadForgeError,
    ScenarioError,
)
from loadforge.dsl.decorators import scenario, setup, task, teardown
from loadforge.dsl.http_client import HttpClient, RequestMetric
from loadforge.engine.runner import LoadTestRunner
from loadforge.engine.worker import run_worker
from loadforge.metrics.models import EndpointMetrics, MetricSnapshot, TestResult
from loadforge.patterns.base import LoadPattern
from loadforge.patterns.composite import CompositePattern
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.diurnal import DiurnalPattern
from loadforge.patterns.ramp import RampPattern
from loadforge.patterns.spike import SpikePattern
from loadforge.patterns.step import StepPattern
from loadforge.reports import ReportGenerator, export_csv, export_html, export_json

__version__ = "0.2.0"

__all__ = [
    "CompositePattern",
    "ConfigError",
    "ConstantPattern",
    "DashboardError",
    "DiurnalPattern",
    "EndpointMetrics",
    "EngineError",
    "HttpClient",
    "LoadForgeError",
    "LoadPattern",
    "LoadTestRunner",
    "MetricSnapshot",
    "RampPattern",
    "ReportGenerator",
    "RequestMetric",
    "ScenarioError",
    "SpikePattern",
    "StepPattern",
    "TestResult",
    "export_csv",
    "export_html",
    "export_json",
    "run_worker",
    "scenario",
    "setup",
    "task",
    "teardown",
]
