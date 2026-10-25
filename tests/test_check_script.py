import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check.sh"
EVAL_START = "# >>> EVAL STEP (added in B3) >>>"
EVAL_END = "# <<< EVAL STEP <<<"


def run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_selftest_fail_propagates() -> None:
    result = run_script("--selftest-fail")
    assert result.returncode == 1
    assert "FAIL injected-failure" in result.stdout
    assert "PASS before-failure" in result.stdout
    assert "PASS after-failure" in result.stdout
    assert "check failed: injected-failure" in result.stdout


def test_selftest_pass_exits_zero() -> None:
    result = run_script("--selftest-pass")
    assert result.returncode == 0
    assert "check passed" in result.stdout


def test_unknown_argument_is_usage_error() -> None:
    result = run_script("--bogus")
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_recursive_real_run_is_refused() -> None:
    env = {**os.environ, "COMMIT_KIND_CHECK_RUNNING": "1"}
    result = run_script(env=env)
    assert result.returncode == 3
    assert "refusing recursive" in result.stderr


def test_real_steps_use_run_step() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    for fragment in (
        "ruff check src tests",
        "ruff format --check src tests",
        "mypy --strict src tests",
        "pytest",
    ):
        assert any(line.startswith("run_step") and fragment in line for line in lines), fragment
    assert "|| true" not in text
    assert "set -e" not in text


def test_eval_marker_present_once() -> None:
    lines = [line.strip() for line in SCRIPT.read_text(encoding="utf-8").splitlines()]
    assert lines.count(EVAL_START) == 1
    assert lines.count(EVAL_END) == 1
    pytest_at = next(i for i, line in enumerate(lines) if line.startswith("run_step pytest"))
    finish_at = max(i for i, line in enumerate(lines) if line == "finish")
    assert pytest_at < lines.index(EVAL_START) < lines.index(EVAL_END) < finish_at


def test_check_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK)


def test_check_script_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stderr
