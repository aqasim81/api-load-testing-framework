"""``loadforge dashboard`` — launch the live dashboard server.

This is a placeholder for Phase 7 (Live React Dashboard). The command will
be fully implemented once the dashboard module is built.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console(stderr=True)


def dashboard_cmd(
    results_dir: Path = typer.Argument(
        ...,
        help="Directory containing saved test results.",
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
    """Launch the live dashboard for saved test results."""
    console.print(
        f"[yellow]Live dashboard will be available in Phase 7.[/yellow]\n"
        f"  results_dir: {results_dir}\n"
        f"  port: {port}",
    )
    raise typer.Exit(code=0)
