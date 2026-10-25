import os
import subprocess
import sys
from pathlib import Path

import pytest

from commit_kind.cli import main

ROOT = Path(__file__).resolve().parent.parent


def test_version_in_process(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out == "commit-kind 0.1.0\n"


def test_module_entry_version() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "commit_kind", "--version"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == "commit-kind 0.1.0\n"


def test_no_arguments_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_unknown_option_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--nope"])
    assert excinfo.value.code == 2
    assert "usage:" in capsys.readouterr().err
