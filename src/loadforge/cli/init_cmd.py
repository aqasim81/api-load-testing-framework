"""``loadforge init`` — scaffold a new scenario file from a template."""

from __future__ import annotations

from pathlib import Path
from string import Template

import typer
from rich.console import Console

console = Console(stderr=True)

_SCENARIO_TEMPLATE = Template('''\
"""Load test scenario — $name.

Run with:
    loadforge run $filename --users 10 --duration 30
"""

from __future__ import annotations

from loadforge import HttpClient, scenario, task


@scenario(
    name="$name",
    base_url="http://localhost:8080",
    think_time=(0.5, 1.5),
)
class $class_name:
    """$name load test."""

    @task(weight=1)
    async def get_root(self, client: HttpClient) -> None:
        """GET the root endpoint."""
        await client.get("/", name="Root")
''')


def init_cmd(
    name: str = typer.Argument(
        "my_scenario",
        help="Name for the scenario (used as filename and class name).",
    ),
) -> None:
    """Scaffold a new scenario file in the current directory."""
    # Sanitise the name for use as a Python identifier
    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name).lower()
    if not safe_name or safe_name[0].isdigit():
        safe_name = "scenario_" + safe_name

    filename = f"{safe_name}.py"
    class_name = "".join(word.capitalize() for word in safe_name.split("_")) + "Scenario"
    display_name = name.replace("_", " ").replace("-", " ").title()

    target = Path.cwd() / filename
    if target.exists():
        console.print(f"[red]File already exists:[/red] {filename}")
        raise typer.Exit(code=1)

    content = _SCENARIO_TEMPLATE.substitute(
        name=display_name,
        filename=filename,
        class_name=class_name,
    )
    target.write_text(content)
    console.print(f"[green]Created scenario:[/green] {filename}")
