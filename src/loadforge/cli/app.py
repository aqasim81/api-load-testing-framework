"""Main Typer application — entry point for the ``loadforge`` CLI."""

from __future__ import annotations

import typer

from loadforge import __version__
from loadforge.cli.dashboard import dashboard_cmd
from loadforge.cli.init_cmd import init_cmd
from loadforge.cli.report import report_cmd
from loadforge.cli.run import run_cmd

app = typer.Typer(
    name="loadforge",
    help="Forge realistic load tests as Python code.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("run", help="Run a load test scenario.")(run_cmd)
app.command("init", help="Scaffold a new scenario file.")(init_cmd)
app.command("report", help="Regenerate reports from saved data.")(report_cmd)
app.command("dashboard", help="Launch the live dashboard for saved results.")(dashboard_cmd)


def _version_callback(value: bool) -> None:
    """Print version and exit.

    Args:
        value: True if --version was passed.
    """
    if value:
        typer.echo(f"loadforge {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """LoadForge — forge realistic load tests as Python code."""
