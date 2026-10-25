import re
from pathlib import Path

import commit_kind
import commit_kind.cli

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_version_format() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", commit_kind.__version__)


def test_pyproject_version_matches_package() -> None:
    match = re.search(r'^version = "([^"]+)"$', PYPROJECT, re.MULTILINE)
    assert match is not None
    assert match.group(1) == commit_kind.__version__


def test_no_runtime_dependencies() -> None:
    assert "\ndependencies = []\n" in PYPROJECT
    assert '\nrequires-python = ">=3.10"\n' in PYPROJECT


def test_dev_extra_lists_tools() -> None:
    match = re.search(r"^dev = \[(.*)\]$", PYPROJECT, re.MULTILINE)
    assert match is not None
    for tool in ("ruff", "mypy", "pytest"):
        assert tool in match.group(1)


def test_console_script_target_resolves() -> None:
    assert '\ncommit-kind = "commit_kind.cli:main"\n' in PYPROJECT
    assert callable(commit_kind.cli.main)
