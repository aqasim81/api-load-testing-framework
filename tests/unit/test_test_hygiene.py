"""Static checks on the test suite itself: no hardcoded ports (invariant 5)."""

from __future__ import annotations

import ast
import itertools
import re
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parents[1]
_HOST_WITH_PORT = re.compile(r"(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]):\d+")
_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", ""})  # noqa: S104
_MAX_PORT = 65535


def _int_port(node: ast.expr) -> int | None:
    """Return the value of a non-zero int literal that could be a port."""
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
        and 0 < node.value <= _MAX_PORT
    ):
        return node.value
    return None


def _sequence_ports(items: list[ast.expr]) -> list[tuple[int, str]]:
    """Find ports right after a host string, or after a ``--*port`` CLI flag."""
    found: list[tuple[int, str]] = []
    for prev, cur in itertools.pairwise(items):
        if not (isinstance(prev, ast.Constant) and isinstance(prev.value, str)):
            continue
        port = _int_port(cur)
        if prev.value in _HOSTS and port is not None:
            found.append((cur.lineno, f"({prev.value!r}, {port})"))
        elif (
            prev.value.startswith("--")
            and prev.value.endswith("port")
            and isinstance(cur, ast.Constant)
            and isinstance(cur.value, str)
            and cur.value.isdigit()
            and cur.value != "0"
        ):
            found.append((cur.lineno, f"{prev.value} {cur.value}"))
    return found


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Return ids of string constants that are docstrings."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def find_hardcoded_ports(source: str, filename: str) -> list[str]:
    """Return one message per hardcoded port found in a test module's source.

    Args:
        source: Python source code.
        filename: Name used in the messages.

    Returns:
        Messages of the form ``"<file>:<line>: <reason>"``.
    """
    tree = ast.parse(source, filename=filename)
    docstrings = _docstring_nodes(tree)
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "port":
            port = _int_port(node.value)
            if port is not None:
                problems.append(f"{filename}:{node.value.lineno}: port={port}")
        elif isinstance(node, ast.Tuple | ast.List):
            for lineno, what in _sequence_ports(node.elts):
                problems.append(f"{filename}:{lineno}: {what}")
        elif isinstance(node, ast.Call):
            for lineno, what in _sequence_ports(node.args):
                problems.append(f"{filename}:{lineno}: {what}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and _HOST_WITH_PORT.search(node.value)
        ):
            problems.append(f"{filename}:{node.lineno}: hardcoded address {node.value!r}")
    return problems


class TestFindHardcodedPorts:
    """The detector flags literal ports and ignores computed ones."""

    @pytest.mark.parametrize(
        "source",
        [
            "start(port=8080)",
            'url = "http://127.0.0.1:9999/x"',
            'url = "ws://localhost:8089/ws"',
            'url = "http://[::1]:5000"',
            'url = "http://0.0.0.0:8000"',
            's.connect(("127.0.0.1", 8080))',
            'web.TCPSite(runner, "127.0.0.1", 8080)',
            'args = ["run", "--dashboard-port", "8089"]',
        ],
    )
    def test_flags_literal_port(self, source: str) -> None:
        assert find_hardcoded_ports(source, "t.py")

    @pytest.mark.parametrize(
        "source",
        [
            "start(port=_get_free_port())",
            'url = f"http://127.0.0.1:{port}"',
            'base_url = "http://localhost"',
            "start(port=0)",
            's.bind(("127.0.0.1", 0))',
            'args = ["--dashboard-port", str(_get_free_port())]',
            'args = ["--users", "2"]',
            'def f():\n    """Returns e.g. http://127.0.0.1:54321."""',
        ],
    )
    def test_ignores_computed_port_and_docstrings(self, source: str) -> None:
        assert find_hardcoded_ports(source, "t.py") == []


def test_tests_have_no_hardcoded_ports() -> None:
    """Every test module gets its ports from _get_free_port()."""
    problems: list[str] = []
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        rel = path.relative_to(_TESTS_DIR).as_posix()
        if rel == "unit/test_test_hygiene.py":
            continue  # this module's own detector cases contain literal ports
        problems.extend(find_hardcoded_ports(path.read_text(encoding="utf-8"), rel))
    assert problems == [], "Use _get_free_port() instead:\n" + "\n".join(problems)
