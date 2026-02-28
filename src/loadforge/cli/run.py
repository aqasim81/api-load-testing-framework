"""``loadforge run`` — execute a load test scenario with live terminal output."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from loadforge._internal.errors import LoadForgeError
from loadforge.engine.runner import LoadTestRunner
from loadforge.patterns.constant import ConstantPattern
from loadforge.patterns.diurnal import DiurnalPattern
from loadforge.patterns.ramp import RampPattern
from loadforge.patterns.spike import SpikePattern
from loadforge.patterns.step import StepPattern

if TYPE_CHECKING:
    from loadforge.metrics.models import MetricSnapshot, TestResult
    from loadforge.patterns.base import LoadPattern

console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Pattern construction helpers
# ---------------------------------------------------------------------------


def _build_pattern(
    pattern_name: str,
    users: int,
    duration: float,
    ramp_to: int | None,
    step_size: int | None,
    step_duration: float | None,
) -> LoadPattern:
    """Construct a LoadPattern from CLI flags.

    Args:
        pattern_name: Pattern type name.
        users: Base / start user count.
        duration: Total test duration in seconds.
        ramp_to: Target users for ramp pattern.
        step_size: Users added per step.
        step_duration: Seconds per step.

    Returns:
        Configured LoadPattern instance.

    Raises:
        typer.BadParameter: If required flags for the chosen pattern are missing.
    """
    if pattern_name == "constant":
        return ConstantPattern(users=users)

    if pattern_name == "ramp":
        if ramp_to is None:
            msg = "--ramp-to is required when using --pattern ramp"
            raise typer.BadParameter(msg)
        return RampPattern(
            start_users=users,
            end_users=ramp_to,
            ramp_duration=duration,
        )

    if pattern_name == "step":
        if step_size is None:
            msg = "--step-size is required when using --pattern step"
            raise typer.BadParameter(msg)
        actual_step_dur = step_duration if step_duration is not None else 30.0
        steps = max(1, int(duration / actual_step_dur))
        return StepPattern(
            start_users=users,
            step_size=step_size,
            step_duration=actual_step_dur,
            steps=steps,
        )

    if pattern_name == "spike":
        spike_users = max(users * 5, users + 50)
        spike_dur = min(duration * 0.5, 60.0)
        return SpikePattern(
            base_users=users,
            spike_users=spike_users,
            spike_duration=spike_dur,
        )

    if pattern_name == "diurnal":
        min_users = max(1, users // 5)
        return DiurnalPattern(
            min_users=min_users,
            max_users=users,
            period=duration,
        )

    msg = f"Unknown pattern: {pattern_name}. Choose from: constant, ramp, step, spike, diurnal"
    raise typer.BadParameter(msg)


# ---------------------------------------------------------------------------
# Rich live display
# ---------------------------------------------------------------------------


def _make_live_table(snapshot: MetricSnapshot | None, elapsed: float) -> Table:
    """Build a Rich table summarising current test metrics.

    Args:
        snapshot: Latest metric snapshot, or None if no data yet.
        elapsed: Elapsed seconds so far.

    Returns:
        Formatted Rich Table.
    """
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    if snapshot is None:
        table.add_row("Elapsed", f"{elapsed:.0f}s")
        table.add_row("Status", "Starting...")
        return table

    table.add_row("Elapsed", f"{snapshot.elapsed_seconds:.0f}s")
    table.add_row("Active Users", str(snapshot.active_users))
    table.add_row("Requests/sec", f"{snapshot.requests_per_second:.1f}")
    table.add_row("Total Requests", str(snapshot.total_requests))
    table.add_row("p50 Latency", f"{snapshot.latency_p50:.1f}ms")
    table.add_row("p95 Latency", f"{snapshot.latency_p95:.1f}ms")
    table.add_row("p99 Latency", f"{snapshot.latency_p99:.1f}ms")
    table.add_row("Errors", str(snapshot.total_errors))
    table.add_row("Error Rate", f"{snapshot.error_rate * 100:.2f}%")

    return table


def _print_summary(result: TestResult) -> None:
    """Print a final summary table after the test completes.

    Args:
        result: Completed test result.
    """
    summary = result.final_summary
    table = Table(
        title="Test Complete",
        show_header=True,
        header_style="bold green",
        expand=True,
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Scenario", result.scenario_name)
    table.add_row("Pattern", result.pattern_description)
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    table.add_row("Snapshots", str(len(result.snapshots)))

    if summary:
        table.add_row("Total Requests", str(summary.total_requests))
        table.add_row("Avg Requests/sec", f"{summary.requests_per_second:.1f}")
        table.add_row("p50 Latency", f"{summary.latency_p50:.1f}ms")
        table.add_row("p95 Latency", f"{summary.latency_p95:.1f}ms")
        table.add_row("p99 Latency", f"{summary.latency_p99:.1f}ms")
        table.add_row("Total Errors", str(summary.total_errors))
        table.add_row("Error Rate", f"{summary.error_rate * 100:.2f}%")

        # Per-endpoint breakdown
        if summary.endpoints:
            console.print()
            ep_table = Table(
                title="Per-Endpoint Breakdown",
                show_header=True,
                header_style="bold cyan",
                expand=True,
            )
            ep_table.add_column("Endpoint")
            ep_table.add_column("Requests", justify="right")
            ep_table.add_column("RPS", justify="right")
            ep_table.add_column("p50", justify="right")
            ep_table.add_column("p95", justify="right")
            ep_table.add_column("p99", justify="right")
            ep_table.add_column("Errors", justify="right")
            ep_table.add_column("Error %", justify="right")

            for ep in summary.endpoints.values():
                ep_table.add_row(
                    ep.name,
                    str(ep.request_count),
                    f"{ep.requests_per_second:.1f}",
                    f"{ep.latency_p50:.1f}ms",
                    f"{ep.latency_p95:.1f}ms",
                    f"{ep.latency_p99:.1f}ms",
                    str(ep.error_count),
                    f"{ep.error_rate * 100:.2f}%",
                )
            console.print(ep_table)

    console.print(table)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def run_cmd(
    scenario_file: Path = typer.Argument(
        ...,
        help="Path to the scenario .py file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    users: int = typer.Option(
        10,
        "--users",
        "-u",
        help="Target concurrent virtual users.",
        min=1,
    ),
    duration: float = typer.Option(
        60.0,
        "--duration",
        "-d",
        help="Test duration in seconds.",
        min=1.0,
    ),
    pattern: str = typer.Option(
        "constant",
        "--pattern",
        "-p",
        help="Traffic pattern: constant, ramp, step, spike, or diurnal.",
    ),
    ramp_to: int | None = typer.Option(
        None,
        "--ramp-to",
        help="Ramp pattern: target user count at end of ramp.",
    ),
    step_size: int | None = typer.Option(
        None,
        "--step-size",
        help="Step pattern: users added at each step.",
    ),
    step_duration: float | None = typer.Option(
        None,
        "--step-duration",
        help="Step pattern: seconds between steps.",
    ),
    workers: int | None = typer.Option(
        None,
        "--workers",
        "-w",
        help="Number of worker processes (default: CPU count).",
    ),
    output: Path = typer.Option(
        Path("./results"),
        "--output",
        "-o",
        help="Output directory for reports.",
    ),
    fmt: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Report format: html, json, or csv.",
    ),
    no_report: bool = typer.Option(
        False,
        "--no-report",
        help="Skip report generation after the test.",
    ),
    fail_on_error_rate: float | None = typer.Option(
        None,
        "--fail-on-error-rate",
        help="Exit non-zero if error rate exceeds this threshold (e.g., 0.05).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) logging.",
    ),
    enable_dashboard: bool = typer.Option(
        False,
        "--dashboard",
        help="Start the live dashboard server (Phase 7).",
    ),
    dashboard_port: int = typer.Option(
        8089,
        "--dashboard-port",
        help="Port for the live dashboard.",
    ),
) -> None:
    """Execute a load test scenario with live terminal output."""
    # Build the traffic pattern from CLI flags
    load_pattern = _build_pattern(
        pattern_name=pattern,
        users=users,
        duration=duration,
        ramp_to=ramp_to,
        step_size=step_size,
        step_duration=step_duration,
    )

    log_level = logging.DEBUG if verbose else logging.INFO

    # Mutable holder so the on_snapshot callback can update the displayed data
    latest: list[MetricSnapshot | None] = [None]

    def _on_snapshot(snapshot: MetricSnapshot) -> None:
        latest[0] = snapshot

    console.print(
        Panel(
            f"[bold]Scenario:[/bold] {scenario_file.name}\n"
            f"[bold]Pattern:[/bold]  {load_pattern.describe()}\n"
            f"[bold]Users:[/bold]    {users}\n"
            f"[bold]Duration:[/bold] {duration}s",
            title="LoadForge",
            border_style="cyan",
        )
    )

    if enable_dashboard:
        console.print("[yellow]Live dashboard will be available in Phase 7.[/yellow]")

    try:
        test_runner = LoadTestRunner(
            scenario_path=scenario_file,
            pattern=load_pattern,
            duration_seconds=duration,
            num_workers=workers,
            on_snapshot=_on_snapshot,
            log_level=log_level,
        )
    except LoadForgeError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Run with live display
    try:
        with Live(
            _make_live_table(None, 0.0),
            console=console,
            refresh_per_second=2,
            transient=True,
        ) as live:
            original_cb = _on_snapshot

            def _live_snapshot(snapshot: MetricSnapshot) -> None:
                original_cb(snapshot)
                live.update(
                    _make_live_table(snapshot, snapshot.elapsed_seconds),
                )

            test_runner._on_snapshot = _live_snapshot
            result = test_runner.run()
    except LoadForgeError as exc:
        console.print(f"[red]Load test failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Print final summary
    _print_summary(result)

    # Check error rate threshold
    if (
        fail_on_error_rate is not None
        and result.final_summary is not None
        and result.final_summary.error_rate > fail_on_error_rate
    ):
        console.print(
            f"[red]FAIL:[/red] Error rate {result.final_summary.error_rate * 100:.2f}% "
            f"exceeds threshold {fail_on_error_rate * 100:.2f}%"
        )
        raise typer.Exit(code=1)

    console.print("[green]Load test completed successfully.[/green]")
