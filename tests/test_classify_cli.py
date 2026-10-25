import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from commit_kind.classifier import classify
from commit_kind.cli import KIND_TEXT
from commit_kind.rules import RULES

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(["src", "tests"])}
    cmd = [sys.executable, "-m", "commit_kind", *args]
    return subprocess.run(
        cmd, cwd=ROOT, env=env, input=stdin, capture_output=True, text=True, timeout=30
    )


def test_label() -> None:
    r = run("classify", "fix: handle empty input")
    assert (r.stdout, r.returncode, r.stderr) == ("fix\n", 0, "")


def test_json() -> None:
    msg = "fix: handle empty input"
    out = json.loads(run("classify", "--json", msg).stdout)
    assert out == asdict(classify(msg))
    assert set(out) == {"label", "rule", "evidence"}


def test_explain() -> None:
    lines = run("classify", "--explain", "fix: handle empty input").stdout.splitlines()
    assert len(lines) == 1
    assert "prefix.fix" in lines[0] and '"fix:"' in lines[0]


def test_stdin_is_one_message() -> None:
    r = run("classify", "-", stdin="docs: reword the intro\n\nBody.\n")
    assert r.stdout == "docs\n"


@pytest.mark.parametrize(("args", "stdin"), [(("",), ""), (("   ",), ""), (("-",), "")])
def test_empty_exit_1(args: tuple[str, ...], stdin: str) -> None:
    r = run("classify", *args, stdin=stdin)
    assert (r.returncode, r.stdout) == (1, "")
    assert "empty" in r.stderr


@pytest.mark.parametrize("args", [(), ("--json", "--explain", "x"), ("--bogus", "x")])
def test_usage_exit_2(args: tuple[str, ...]) -> None:
    r = run("classify", *args)
    assert (r.returncode, r.stdout) == (2, "")
    assert "usage:" in r.stderr


def test_explain_knows_every_kind() -> None:
    assert {r.kind for r in RULES} <= set(KIND_TEXT)


def test_child_network_blocked() -> None:
    code = "import socket; socket.create_connection(('127.0.0.1', 9))"
    r = (
        run("-c", code)
        if False
        else subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": "tests"},
            capture_output=True,
            text=True,
            timeout=30,
        )
    )
    assert r.returncode != 0
    assert "network access is blocked" in r.stderr
