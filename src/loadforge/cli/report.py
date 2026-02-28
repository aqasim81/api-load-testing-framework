"""``loadforge report`` — regenerate reports from saved test data.

This is a placeholder for Phase 6 (Post-Run Reports). The command will
be fully implemented once the report generation module is built.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console(stderr=True)


def report_cmd(
    results_dir: Path = typer.Argument(
        ...,
        help="Directory containing saved test results.",
        exists=True,
        file_okay=False,
        readable=True,
    ),
    fmt: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Report format: html, json, or csv.",
    ),
) -> None:
    """Regenerate reports from previously saved test data."""
    console.print(
        f"[yellow]Report generation will be available in Phase 6.[/yellow]\n"
        f"  results_dir: {results_dir}\n"
        f"  format: {fmt}",
    )
    raise typer.Exit(code=0)
