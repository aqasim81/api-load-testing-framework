"""``loadforge dashboard`` — replay saved test results in the live dashboard."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console

from loadforge._internal.errors import LoadForgeError

console = Console(stderr=True)


def dashboard_cmd(
    results_dir: Path = typer.Argument(
        ...,
        help="Directory containing saved test results (with result.json).",
        exists=True,
        file_okay=False,
        readable=True,
    ),
    port: int = typer.Option(
        8089,
        "--port",
        "-p",
        help="Port for the dashboard server.",
    ),
) -> None:
    """Replay saved test results in the live dashboard.

    Loads snapshots from a result.json file and replays them through
    the dashboard at 1-second intervals.  Press Ctrl+C to stop.

    Raises:
        typer.Exit: With code 1 on error.
    """
    from loadforge.dashboard.broadcaster import SnapshotBroadcaster
    from loadforge.dashboard.server import DashboardServer, create_app
    from loadforge.reports.exporters import load_result

    json_path = results_dir / "result.json"
    if not json_path.exists():
        console.print(f"[red]No result.json found in {results_dir}[/red]")
        raise typer.Exit(code=1)

    try:
        result = load_result(json_path)
    except LoadForgeError as exc:
        console.print(f"[red]Failed to load results:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not result.snapshots:
        console.print("[yellow]No snapshots in result — nothing to replay.[/yellow]")
        raise typer.Exit(code=0)

    broadcaster = SnapshotBroadcaster()
    app = create_app(broadcaster)
    server = DashboardServer(app, broadcaster, port)

    try:
        server.start()
    except LoadForgeError as exc:
        console.print(f"[red]Dashboard failed to start:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    count = len(result.snapshots)
    name = result.scenario_name
    console.print(
        f"[green]Dashboard running at http://localhost:{port}[/green]\n"
        f"Replaying {count} snapshots from [bold]{name}[/bold]...\n"
        f"Press [bold]Ctrl+C[/bold] to stop."
    )

    try:
        for snapshot in result.snapshots:
            broadcaster.on_snapshot(snapshot)
            time.sleep(1.0)

        # After replay, keep server open until interrupted
        console.print(
            "[dim]Replay complete. Dashboard still running \u2014 press Ctrl+C to exit.[/dim]"
        )
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down dashboard...[/dim]")
    finally:
        server.stop()
