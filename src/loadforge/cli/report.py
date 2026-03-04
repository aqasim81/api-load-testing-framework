"""``loadforge report`` — regenerate reports from saved test data."""

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
    json_path = results_dir / "result.json"
    if not json_path.exists():
        console.print(f"[red]No result.json found in {results_dir}[/red]")
        raise typer.Exit(code=1)

    from loadforge._internal.errors import LoadForgeError
    from loadforge.reports.exporters import export_csv, export_html, load_result

    try:
        result = load_result(json_path)
    except LoadForgeError as exc:
        console.print(f"[red]Failed to load result: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if fmt == "html":
        report_path = results_dir / "report.html"
        export_html(result, report_path)
        console.print(f"[green]Report generated at {report_path}[/green]")
    elif fmt == "csv":
        csv_path = results_dir / "report.csv"
        export_csv(result, csv_path)
        console.print(f"[green]CSV exported to {csv_path}[/green]")
    elif fmt == "json":
        console.print(f"[dim]JSON already at {json_path}[/dim]")
    else:
        console.print(f"[red]Unknown format: {fmt}. Use html, json, or csv.[/red]")
        raise typer.Exit(code=1)
