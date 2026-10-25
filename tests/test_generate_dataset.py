import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts" / "generate_dataset.py"
DATA = ROOT / "data" / "commits.jsonl"
CHECK_SH = ROOT / "scripts" / "check.sh"

ALLOWED_IMPORTS = {
    "argparse",
    "json",
    "os",
    "re",
    "sys",
    "random",
    "pathlib",
    "tempfile",
    "dataclasses",
    "typing",
    "collections",
    "itertools",
    "__future__",
}

EXPECTED_KEYWORDS = {
    "feat": [
        "feat",
        "feature",
        "add",
        "adds",
        "added",
        "new",
        "support",
        "implement",
        "introduce",
        "allow",
        "enable",
    ],
    "fix": [
        "fix",
        "fixes",
        "fixed",
        "bug",
        "bugfix",
        "crash",
        "error",
        "issue",
        "broken",
        "resolve",
        "typo",
        "regression",
    ],
    "docs": [
        "docs",
        "doc",
        "documentation",
        "readme",
        "comment",
        "comments",
        "docstring",
        "guide",
        "changelog",
        "example",
        "examples",
    ],
    "refactor": [
        "refactor",
        "refactoring",
        "rename",
        "renamed",
        "move",
        "moved",
        "extract",
        "simplify",
        "cleanup",
        "restructure",
    ],
    "test": [
        "test",
        "tests",
        "testing",
        "spec",
        "coverage",
        "fixture",
        "fixtures",
        "mock",
        "assert",
        "pytest",
    ],
    "chore": [
        "chore",
        "bump",
        "upgrade",
        "dependency",
        "dependencies",
        "deps",
        "ci",
        "build",
        "release",
        "version",
        "lint",
    ],
}


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_dataset", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_generator(
    *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def generate_bytes(out: Path, *args: str, env_extra: dict[str, str] | None = None) -> bytes:
    result = run_generator("--out", str(out), *args, env_extra=env_extra)
    assert result.returncode == 0, result.stderr
    return out.read_bytes()


def test_committed_dataset_matches_fresh_generation(tmp_path: Path) -> None:
    fresh = generate_bytes(tmp_path / "fresh.jsonl", "--seed", "20261025")
    assert fresh == DATA.read_bytes()


def test_byte_identical_across_runs_and_hash_seeds(tmp_path: Path) -> None:
    first = generate_bytes(tmp_path / "a.jsonl", env_extra={"PYTHONHASHSEED": "0"})
    second = generate_bytes(tmp_path / "b.jsonl", env_extra={"PYTHONHASHSEED": "1"})
    assert first == second


def test_different_seed_changes_output(tmp_path: Path) -> None:
    default = generate_bytes(tmp_path / "a.jsonl")
    other = generate_bytes(tmp_path / "b.jsonl", "--seed", "1")
    assert default != other


def test_default_seed_is_the_documented_one(tmp_path: Path) -> None:
    default = generate_bytes(tmp_path / "a.jsonl")
    assert default == DATA.read_bytes()


def test_success_message(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "dir" / "c.jsonl"
    result = run_generator("--out", str(out))
    assert result.returncode == 0
    assert result.stdout.startswith("wrote 360 records to ")
    assert out.exists()


def test_generator_is_stdlib_only() -> None:
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])
    assert imported
    assert imported <= ALLOWED_IMPORTS
    assert not imported & {"socket", "urllib", "http"}


def test_seed_not_an_int_is_usage_error(tmp_path: Path) -> None:
    out = tmp_path / "x.jsonl"
    result = run_generator("--seed", "abc", "--out", str(out))
    assert result.returncode == 2
    assert "usage" in result.stderr
    assert not out.exists()


def test_missing_out_is_usage_error() -> None:
    result = run_generator()
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_out_is_directory_is_error(tmp_path: Path) -> None:
    result = run_generator("--out", str(tmp_path))
    assert result.returncode == 1
    assert "is a directory" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_unwritable_out_is_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    result = run_generator("--out", str(blocker / "child.jsonl"))
    assert result.returncode == 1
    assert result.stderr.startswith("error:")


def test_keyword_contract() -> None:
    module = load_generator()
    keywords = cast("dict[str, tuple[str, ...]]", module.CONTROL_KEYWORDS)
    assert list(keywords) == list(EXPECTED_KEYWORDS)
    for label, words in EXPECTED_KEYWORDS.items():
        assert list(keywords[label]) == words
    flat = [word for words in keywords.values() for word in words]
    assert len(flat) == len(set(flat))


def test_module_constants() -> None:
    module = load_generator()
    assert cast("int", module.PER_LABEL) == 60
    assert cast("dict[str, int]", module.SLICE_COUNTS) == {
        "prefixed": 22,
        "plain": 18,
        "misleading": 20,
    }
    assert cast("tuple[str, ...]", module.LABELS) == tuple(EXPECTED_KEYWORDS)
    assert cast("tuple[str, ...]", module.SLICES) == ("prefixed", "plain", "misleading")
    heldout = cast("dict[str, list[dict[str, str]]]", module.HELDOUT)
    assert list(heldout) == list(EXPECTED_KEYWORDS)
    assert all(3 <= len(entries) <= 4 for entries in heldout.values())


def test_generate_and_serialise_agree_with_the_file() -> None:
    module = load_generator()
    records = cast("list[dict[str, str]]", module.generate(20261025))
    assert len(records) == 360
    assert cast("bytes", module.serialise(records)) == DATA.read_bytes()


def test_main_returns_codes(tmp_path: Path) -> None:
    module = load_generator()
    assert cast("int", module.main(["--out", str(tmp_path / "m.jsonl")])) == 0
    assert cast("int", module.main(["--out", str(tmp_path)])) == 1
    with pytest.raises(SystemExit) as info:
        module.main(["--seed", "abc", "--out", str(tmp_path / "n.jsonl")])
    assert info.value.code == 2


def test_check_sh_lints_scripts() -> None:
    lines = CHECK_SH.read_text(encoding="utf-8").splitlines()
    for prefix in ("run_step ruff-check", "run_step ruff-format", "run_step mypy"):
        matching = [line for line in lines if line.strip().startswith(prefix)]
        assert len(matching) == 1
        assert "src tests scripts" in matching[0]
