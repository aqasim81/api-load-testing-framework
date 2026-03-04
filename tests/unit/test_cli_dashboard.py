"""Unit tests for the ``loadforge dashboard`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from loadforge.cli.app import app

runner = CliRunner()


def test_dashboard_missing_result_json(tmp_path: Path) -> None:
    """Command exits with code 1 when result.json is missing."""
    result = runner.invoke(app, ["dashboard", str(tmp_path)])
    assert result.exit_code == 1
    assert "No result.json found" in result.output


def test_dashboard_empty_snapshots(tmp_path: Path) -> None:
    """Command exits with code 0 when result has no snapshots."""
    result_data = {
        "scenario_name": "test",
        "pattern_description": "constant(users=1)",
        "duration_seconds": 10.0,
        "start_time": 1000.0,
        "end_time": 1010.0,
        "snapshots": [],
        "final_summary": None,
    }
    json_path = tmp_path / "result.json"
    json_path.write_text(json.dumps(result_data))

    result = runner.invoke(app, ["dashboard", str(tmp_path)])
    assert result.exit_code == 0
    assert "No snapshots" in result.output
