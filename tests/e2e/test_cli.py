"""End-to-end tests for the LoadForge CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from loadforge import __version__
from loadforge.cli.app import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_scenario(tmp_path: Path, sync_echo_server: str) -> Path:
    """Create a temporary scenario file pointing at the sync echo server."""
    code = f'''\
from __future__ import annotations

from loadforge import scenario, task, HttpClient


@scenario(
    name="CLI Test Scenario",
    base_url="{sync_echo_server}",
    think_time=(0.01, 0.02),
)
class CLITestScenario:

    @task(weight=1)
    async def get_echo(self, client: HttpClient) -> None:
        await client.get("/echo/test", name="Echo Test")
'''
    path = tmp_path / "cli_scenario.py"
    path.write_text(code)
    return path


@pytest.fixture
def error_scenario(tmp_path: Path, sync_echo_server: str) -> Path:
    """Scenario that hits the error endpoint to trigger a high error rate."""
    code = f'''\
from __future__ import annotations

from loadforge import scenario, task, HttpClient


@scenario(
    name="Error Scenario",
    base_url="{sync_echo_server}",
    think_time=(0.01, 0.02),
)
class ErrorScenario:

    @task(weight=1)
    async def get_error(self, client: HttpClient) -> None:
        await client.get("/error?status=500", name="Error Endpoint")
'''
    path = tmp_path / "error_scenario.py"
    path.write_text(code)
    return path


# ---------------------------------------------------------------------------
# Tests: version and help
# ---------------------------------------------------------------------------


def test_version_flag():
    """--version prints version and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_short_flag():
    """-V also prints version."""
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_output():
    """--help shows usage information."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "loadforge" in result.output.lower()


def test_run_help():
    """loadforge run --help shows run options."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--users" in result.output
    assert "--duration" in result.output
    assert "--pattern" in result.output


# ---------------------------------------------------------------------------
# Tests: loadforge init
# ---------------------------------------------------------------------------


def test_init_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """loadforge init creates a scenario file in cwd."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_test"])
    assert result.exit_code == 0
    generated = tmp_path / "my_test.py"
    assert generated.exists()
    content = generated.read_text()
    assert "class MyTestScenario" in content
    assert "@scenario" in content
    assert "@task" in content


def test_init_default_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """loadforge init with no name uses 'my_scenario'."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / "my_scenario.py").exists()


def test_init_rejects_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """loadforge init refuses to overwrite an existing file."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing.py").write_text("# placeholder")
    result = runner.invoke(app, ["init", "existing"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Tests: loadforge run (basic)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_run_basic(cli_scenario: Path):
    """loadforge run executes a scenario and exits 0."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--users",
            "2",
            "--duration",
            "3",
            "--workers",
            "1",
            "--no-report",
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.output}"
    assert "Test Complete" in result.output or "completed successfully" in result.output


@pytest.mark.slow
def test_run_ramp_pattern(cli_scenario: Path):
    """loadforge run with --pattern ramp works."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--users",
            "1",
            "--duration",
            "3",
            "--pattern",
            "ramp",
            "--ramp-to",
            "4",
            "--workers",
            "1",
            "--no-report",
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.output}"


@pytest.mark.slow
def test_run_step_pattern(cli_scenario: Path):
    """loadforge run with --pattern step works."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--users",
            "1",
            "--duration",
            "4",
            "--pattern",
            "step",
            "--step-size",
            "2",
            "--step-duration",
            "2",
            "--workers",
            "1",
            "--no-report",
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.output}"


def test_run_ramp_requires_ramp_to(cli_scenario: Path):
    """--pattern ramp without --ramp-to gives an error."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--pattern",
            "ramp",
            "--no-report",
        ],
    )
    assert result.exit_code != 0


def test_run_step_requires_step_size(cli_scenario: Path):
    """--pattern step without --step-size gives an error."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--pattern",
            "step",
            "--no-report",
        ],
    )
    assert result.exit_code != 0


def test_run_nonexistent_scenario(tmp_path: Path):
    """loadforge run with a nonexistent file exits non-zero."""
    fake_path = str(tmp_path / "does_not_exist.py")
    result = runner.invoke(
        app,
        ["run", fake_path, "--no-report"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: --fail-on-error-rate
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_fail_on_error_rate_triggers(error_scenario: Path):
    """--fail-on-error-rate exits 1 when threshold exceeded."""
    result = runner.invoke(
        app,
        [
            "run",
            str(error_scenario),
            "--users",
            "2",
            "--duration",
            "3",
            "--workers",
            "1",
            "--fail-on-error-rate",
            "0.01",
            "--no-report",
        ],
    )
    assert result.exit_code == 1


@pytest.mark.slow
def test_fail_on_error_rate_passes(cli_scenario: Path):
    """--fail-on-error-rate exits 0 when error rate is below threshold."""
    result = runner.invoke(
        app,
        [
            "run",
            str(cli_scenario),
            "--users",
            "2",
            "--duration",
            "3",
            "--workers",
            "1",
            "--fail-on-error-rate",
            "0.99",
            "--no-report",
        ],
    )
    assert result.exit_code == 0, f"stderr: {result.output}"


# ---------------------------------------------------------------------------
# Tests: placeholder commands
# ---------------------------------------------------------------------------


def test_report_placeholder(tmp_path: Path):
    """loadforge report prints Phase 6 message."""
    result = runner.invoke(app, ["report", str(tmp_path)])
    assert result.exit_code == 0
    assert "Phase 6" in result.output


def test_dashboard_placeholder(tmp_path: Path):
    """loadforge dashboard prints Phase 7 message."""
    result = runner.invoke(app, ["dashboard", str(tmp_path)])
    assert result.exit_code == 0
    assert "Phase 7" in result.output
