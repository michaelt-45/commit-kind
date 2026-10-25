# B1 — Plan

## 1. Goal and user-visible result

B1 builds the gate before any feature is written. When B1 is done, a fresh clone gives you:

- `./scripts/check.sh` runs four steps: `ruff check`, `ruff format --check`, `mypy --strict` (on `src/` and `tests/`) and `pytest`.
  - It prints one PASS/FAIL line per step and a final summary.
  - It exits 0 only if every step passed.
  - It has a clearly marked spot where B3 adds `python -m commit_kind eval`.
- `PYTHONPATH=src python3 -m commit_kind --version` prints `commit-kind 0.1.0`.
- `pyproject.toml` declares Python >= 3.10, no runtime dependencies, a `dev` optional extra with the tool versions, and the console script `commit-kind`.
- During tests, opening a socket raises. A test proves it.
- A test proves that a failing step makes `check.sh` exit non-zero, without `check.sh` calling itself through pytest.
- `.gitignore`, `LICENSE` (MIT, "michaelt-45") and a minimal `README.md` exist.

Environment facts, checked on the build machine:
- Python 3.10.13 (pyenv shims `python3` / `python`), with ruff 0.15.12, mypy 2.1.0 and pytest 9.0.2 installed globally.
- `/usr/bin/env bash` resolves to **bash 3.2.57**.
- Python 3.10 has **no `tomllib`**.
- `shellcheck` is **not installed**.
- No `uv`. No network. No `pip install` of anything, and no `pip install -e`.

## 2. Interfaces and file ownership (what other blocks may touch, what they must not)

Files created by B1:

| File | Owner | Later blocks may | Later blocks must not |
|---|---|---|---|
| `pyproject.toml` | B1 | add `[tool.*]` settings; add modules to packaging | add runtime `dependencies`; lower `requires-python`; drop the `dev` extra; change `pythonpath = ["src"]` |
| `scripts/check.sh` | B1 | **B3**: replace the marked EVAL block with one `run_step eval ...` line. **B2**: add `scripts` to the ruff and mypy targets once `scripts/*.py` exists | remove or reorder the four core steps; add `\|\| true`; switch to fail-fast; remove the self-test modes or the recursion guard |
| `src/commit_kind/__init__.py` | B1 | re-export the public API (B3 `evaluate`, B4 `classify`) | change how `__version__` is defined (one string literal) |
| `src/commit_kind/__main__.py` | B1 | — | add logic (it only calls `cli.main`) |
| `src/commit_kind/cli.py` | B1 | **B3**: register the `eval` subcommand. **B5**: register `classify` | change the signature `main(argv: Sequence[str] \| None = None) -> int`; change the `--version` output format |
| `src/commit_kind/py.typed` | B1 | — | delete |
| `tests/conftest.py` | B1 | add fixtures | weaken, remove or make opt-in the autouse network guard |
| `tests/test_network_guard.py`, `tests/test_check_script.py`, `tests/test_package.py`, `tests/test_cli.py` | B1 | add tests | delete or loosen the existing assertions |
| `.gitignore`, `LICENSE` | B1 | append ignore patterns | change the license or the copyright holder |
| `README.md` | B1 (minimal) | **B5** rewrites it fully | — |

Interfaces fixed by B1:
- **CLI:**
  - `main(argv)` uses `argparse`, with `prog="commit-kind"`, and creates `add_subparsers(dest="command")` now with no subcommands yet.
  - `--version` prints `commit-kind <__version__>` to stdout and exits 0.
  - No arguments prints usage to stderr and returns 2. An unknown option makes argparse exit with 2.
  - These exit codes match B5's contract: 2 means usage error.
- **check.sh exit codes:**
  - 0: all steps passed.
  - 1: at least one step failed.
  - 2: usage error (unknown argument).
  - 3: refused because of a recursive real-mode run.
- **Network guard:** `tests/conftest.py` defines `NetworkBlockedError(RuntimeError)`. It is a `RuntimeError` on purpose, not an `OSError`, so code that catches `OSError` (urllib, retry loops) cannot swallow it.

## 3. Steps
| # | Step | Files | Check | Model | Size |
|---|---|---|---|---|---|
| 1 | Package skeleton and config: `pyproject.toml`, the package files and `.gitignore` (full specs below) | `pyproject.toml`, `src/commit_kind/__init__.py`, `__main__.py`, `cli.py`, `py.typed`, `.gitignore` | `PYTHONPATH=src python3 -m commit_kind --version` prints `commit-kind 0.1.0`; `python3 -m ruff check src && python3 -m ruff format --check src && python3 -m mypy --strict src` exit 0 | sonnet | S |
| 2 | Network guard and package/CLI tests: autouse fixture in `tests/conftest.py` plus the tests in section 4 (groups A–C) | `tests/conftest.py`, `tests/test_network_guard.py`, `tests/test_package.py`, `tests/test_cli.py` | `python3 -m pytest -q` green; `python3 -m mypy --strict src tests` and ruff on `tests` exit 0 | sonnet | M |
| 3 | `scripts/check.sh` with a step runner, self-test modes, recursion guard and EVAL marker, plus its tests (section 4, group D) | `scripts/check.sh` (mode 100755), `tests/test_check_script.py` | `./scripts/check.sh` exits 0; `./scripts/check.sh --selftest-fail` exits 1; `./scripts/check.sh --selftest-pass` exits 0; `./scripts/check.sh --bogus` exits 2 | sonnet | M |
| 4 | LICENSE and README | `LICENSE`, `README.md` | `grep -q "MIT License" LICENSE && grep -q "michaelt-45" LICENSE`; README names `./scripts/check.sh`; `./scripts/check.sh` green | haiku | S |
| 5 | Final verification and hygiene: the full check, manual runs, injected-violation proof and hygiene scans (section 5), then summary between the markers | none (fixes only if something fails) | all items in section 5 pass | haiku | S |

**Step 1, file specs:**

- **`pyproject.toml`:**
  - `[build-system]`: setuptools >= 61, `setuptools.build_meta`. It is never run at check time.
  - `[project]`:
    - `name="commit-kind"`, `version="0.1.0"` (a static string literal).
    - `description`, `readme`, `license = {text = "MIT"}`, `requires-python=">=3.10"`.
    - `dependencies = []`.
    - `[project.optional-dependencies] dev = ["ruff>=0.15", "mypy>=2.1", "pytest>=9.0"]`.
    - `[project.scripts] commit-kind = "commit_kind.cli:main"`.
  - `[tool.setuptools.packages.find] where = ["src"]` and package-data for `py.typed`.
  - `[tool.ruff]`: `target-version = "py310"`, `line-length = 100`, `src = ["src", "tests"]`. Lint select: `["E", "F", "W", "I", "B", "UP", "SIM", "RUF"]`.
  - `[tool.mypy]`: `python_version = "3.10"`, `strict = true`, `mypy_path = "src"`.
  - `[tool.pytest.ini_options]`: `pythonpath = ["src"]`, `testpaths = ["tests"]`, `addopts = "-ra --strict-markers"`, `xfail_strict = true`.
- **`__init__.py`:** contains only the docstring and `__version__ = "0.1.0"`.
- **`__main__.py`:** `raise SystemExit(main())`.
- **`cli.py`:** as fixed in section 2.
- **`.gitignore`:** `__pycache__/`, `*.py[cod]`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.venv/`, `venv/`, `build/`, `dist/`, `*.egg-info/`, `.env`, `.coverage`, `htmlcov/`, `.DS_Store`.

**Step 2, conftest spec:** an autouse fixture uses `monkeypatch` to replace `socket.socket` and `socket.create_connection` with a guard. The guard is typed `(*args: object, **kwargs: object) -> NoReturn` and raises `NetworkBlockedError("network access is blocked in tests")`. pytest restores the originals after each test.

**Step 3, check.sh spec:**
- Header and environment:
  - `#!/usr/bin/env bash`, then `set -uo pipefail` (no `-e`, because steps are collected).
  - `cd` to the repo root via `$(dirname "$0")/..`.
  - `export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"`.
  - `PY="${PYTHON:-python3}"`.
- **bash 3.2 compatible:**
  - No arrays under `set -u` (an empty `"${a[@]}"` is an unbound-variable error in 3.2).
  - No `mapfile`, no associative arrays, no `${var,,}`.
  - Failed step names are collected in a space-separated string.
- `run_step NAME CMD...`:
  - prints `==> NAME`;
  - runs `if "$@"; then echo "PASS NAME"; else echo "FAIL NAME (exit $?)"; FAILED="$FAILED NAME"; fi`.
- `finish`: prints `check passed` and exits 0, or prints `check failed:$FAILED` and exits 1.
- Real mode (no arguments):
  - If `COMMIT_KIND_CHECK_RUNNING` is already set, print `refusing recursive check.sh run` to stderr and exit 3. Otherwise export it as 1.
  - `run_step ruff-check "$PY" -m ruff check src tests`
  - `run_step ruff-format "$PY" -m ruff format --check src tests`
  - `run_step mypy "$PY" -m mypy --strict src tests`
  - `run_step pytest "$PY" -m pytest -q`
  - then the EVAL block, verbatim:
    ```
    # >>> EVAL STEP (added in B3) >>>
    # run_step eval "$PY" -m commit_kind eval
    # <<< EVAL STEP <<<
    ```
  - then `finish`.
- `--selftest-pass` runs `run_step selftest-ok true` twice, then `finish`.
- `--selftest-fail` runs `run_step before-failure true`, `run_step injected-failure false`, `run_step after-failure true`, then `finish`.
- Self-test modes use the same `run_step`/`finish` code. They do not check or set the recursion variable, and they never start Python.
- Any other argument prints a usage line to stderr and exits 2.
- Commit the file with the executable bit (`chmod +x` before `git add`; verify with `git ls-files -s`).

**Step 4, contents:**
- **LICENSE:** standard MIT text, `Copyright (c) 2026 michaelt-45`.
- **README.md:** at most about 25 lines:
  - what commit-kind is (one paragraph, with the label set);
  - status: milestone 1 in progress, CLI not usable yet beyond `--version`;
  - requirements: Python >= 3.10, ruff/mypy/pytest from the `dev` extra;
  - how to run the gate: `./scripts/check.sh` (set `PYTHON=` to choose the interpreter);
  - `PYTHONPATH=src python3 -m commit_kind --version`;
  - license line.
- No absolute paths, no other projects.

Parallel groups and order: everything is serial in one worktree (`loop/B1`), run by one build agent per step or one sonnet agent for steps 1–3. Order: 1 → 2 → 3 → 4 → 5. Each step ends with a small thematic commit. After step 3, run `./scripts/check.sh` after every step.

## 4. Tests (name — what it proves; include error paths and one negative control per metric)

**A. `tests/test_network_guard.py`** (none of these tests requests the fixture, which proves it is autouse):
- `test_socket_constructor_raises`: `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` raises `NetworkBlockedError`.
- `test_create_connection_raises`: `socket.create_connection(("127.0.0.1", 9), timeout=0.1)` raises `NetworkBlockedError`. No real connect is attempted.
- `test_urllib_cannot_reach_network`: `urllib.request.urlopen("http://127.0.0.1:9", timeout=0.1)` raises `NetworkBlockedError`, not a wrapped `URLError`. This error path proves the guard is not swallowed by `OSError` handling.
- `test_guard_error_message`: the error text contains "network access is blocked".

**B. `tests/test_package.py`:**
- `test_version_format`: `commit_kind.__version__` matches `^\d+\.\d+\.\d+$`.
- `test_pyproject_version_matches_package`: the `version = "..."` string in `pyproject.toml` (read with a regex, since there is no `tomllib` on 3.10) equals `__version__`.
- `test_no_runtime_dependencies`: `pyproject.toml` contains `dependencies = []` and `requires-python = ">=3.10"`.
- `test_dev_extra_lists_tools`: the `dev` extra mentions ruff, mypy and pytest.
- `test_console_script_target_resolves`: `pyproject.toml` contains `commit-kind = "commit_kind.cli:main"`, and importing `commit_kind.cli` gives a callable `main`.

**C. `tests/test_cli.py`:**
- `test_version_in_process`: `main(["--version"])` raises `SystemExit(0)`; stdout is exactly `commit-kind 0.1.0\n`.
- `test_module_entry_version`: a subprocess runs `[sys.executable, "-m", "commit_kind", "--version"]` with `cwd` = repo root, `env` with `PYTHONPATH=src` and `timeout=30`. It must give rc 0 and the same stdout. This proves `__main__.py` is wired up.
- `test_no_arguments_is_usage_error` (error path): `main([])` returns 2; stderr contains `usage:`.
- `test_unknown_option_is_usage_error` (error path): `main(["--nope"])` raises `SystemExit(2)`; stderr contains `usage:`.

**D. `tests/test_check_script.py`** (every subprocess call has `timeout=30` and runs from the repo root):
- `test_selftest_fail_propagates` (the gate's negative control): `scripts/check.sh --selftest-fail` must give:
  - rc == 1;
  - stdout contains `FAIL injected-failure`, `PASS before-failure`, `PASS after-failure` and `check failed: injected-failure`.

  This proves a failing step makes the exit code non-zero and that later steps still run.
- `test_selftest_pass_exits_zero` (positive control): `--selftest-pass` gives rc == 0 and `check passed`.
- `test_unknown_argument_is_usage_error` (error path): `--bogus` gives rc == 2, and stderr contains `usage`.
- `test_recursive_real_run_is_refused` (error path): running with no argument and `COMMIT_KIND_CHECK_RUNNING=1` in the env gives rc == 3 within the timeout. This proves a real run nested inside pytest-inside-check.sh is refused, not repeated.
- `test_real_steps_use_run_step`: a static read of the script. For each of `ruff check src tests`, `ruff format --check src tests`, `mypy --strict src tests` and `pytest`, a line exists that starts with `run_step`. The script contains neither `|| true` nor `set -e`.
- `test_eval_marker_present_once`: the lines `# >>> EVAL STEP (added in B3) >>>` and `# <<< EVAL STEP <<<` each appear exactly once, in that order, after the pytest step and before `finish`.
- `test_check_script_is_executable`: `os.access(path, os.X_OK)` holds.
- `test_check_script_bash_syntax`: `bash -n scripts/check.sh` gives rc 0. This stands in for the missing shellcheck.

Negative control per metric: B1 has no eval metrics. The negative control for the gate itself is `test_selftest_fail_propagates`, and the manual injected-ruff-violation check in section 5.

## 5. Acceptance criteria (checkable by a machine or in five clicks)

All commands run from the repo root on branch `loop/B1`.

1. `./scripts/check.sh; echo $?` prints the four steps as PASS, then `check passed`, then `0`.
2. `./scripts/check.sh --selftest-fail; echo $?` shows `FAIL injected-failure`, then `1`.
3. Injected real failure (manual, not committed):
   - `printf 'import os\n' > src/commit_kind/_tmp_bad.py && ./scripts/check.sh; echo $?` shows `FAIL ruff-check`, `FAIL mypy` (or at least `FAIL ruff-check`) and a non-zero exit.
   - Then `rm src/commit_kind/_tmp_bad.py`; `./scripts/check.sh` is green again.
4. `grep -n "EVAL STEP (added in B3)" scripts/check.sh` returns exactly one line.
5. `PYTHONPATH=src python3 -m commit_kind --version` prints `commit-kind 0.1.0`, exit 0.
   - `PYTHONPATH=src python3 -m commit_kind; echo $?` prints usage on stderr, then `2`.
6. `pyproject.toml` contains:
   - `requires-python = ">=3.10"`
   - `dependencies = []`
   - a `dev` extra with ruff, mypy and pytest
   - `commit-kind = "commit_kind.cli:main"`
7. `python3 -m pytest -q tests/test_network_guard.py` passes: the socket guard is active and proven.
8. `git ls-files -s scripts/check.sh` starts with `100755`.
9. `LICENSE` contains `MIT License` and `Copyright (c) 2026 michaelt-45`. `README.md` exists and mentions `./scripts/check.sh`. `.gitignore` covers the caches.
10. Hygiene scans. Each must print nothing:
    - `git grep -nE '/(Users|home|private|tmp)/'` (the README must not use `/tmp` in examples);
    - `git grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' -- . ':!.planning'`, which checks e-mail addresses in product files. Allowed exceptions: the noreply address in commit trailers is not in files. The LICENSE has no e-mail address.
11. `git log --format='%an <%ae>%n%b' main..loop/B1`:
    - author is `michaelt-45 <202262075+michaelt-45@users.noreply.github.com>`;
    - every message ends with the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` line;
    - no session links.
12. `git diff main...loop/B1 --stat` touches no files outside those in section 2, plus `.planning/B1/`.

## 6. Eval metrics (name, direction, target as "proposal, approval open", what makes it fail)

None in B1. The eval harness, its metrics, thresholds, baselines and negative controls arrive in B3. B1 only provides the marked insertion point in `check.sh` (criterion 4). The gate's own correctness is proven by the self-test negative and positive controls (section 4, group D).

## 7. Risks and rollback

**Risks:**
- **bash 3.2 on macOS.** `/usr/bin/env bash` is 3.2.57 here, and arrays under `set -u` break when empty.
  - Mitigation: string accumulator only, no bash-4 features, and `bash -n` in the tests.
  - The reviewer runs check.sh with that same bash.
- **Wrong interpreter.** `python3` could resolve to an interpreter without the tools.
  - Mitigation: every tool is called as `"$PY" -m <tool>`, with `PY=${PYTHON:-python3}`, so all steps use one interpreter. This is documented in the README.
- **Recursion** (check.sh → pytest → test → check.sh → pytest ...).
  - Mitigation: tests only ever call self-test modes, and those never start Python.
  - The real mode refuses with exit 3 when `COMMIT_KIND_CHECK_RUNNING` is set, and a test covers that.
- **Self-test proves the runner, not the real step list.** Mitigations:
  - the static test that each real step is a `run_step` line and no `|| true` / `set -e`;
  - manual criterion 3, with an injected real ruff violation.
- **Network guard gaps.**
  - It patches `socket.socket` and `socket.create_connection` in-process only. Code using `_socket` directly, or child processes started by tests, are not covered.
  - In B1 the only subprocesses run `python -m commit_kind --version` and `check.sh` self-test modes; neither touches the network.
  - Patching `socket.socket` also breaks `socket.socketpair`/asyncio in tests. That is acceptable: the project uses neither.
  - Backlog entry: a subprocess-level guard (for example a `sitecustomize` on `PYTHONPATH` for tests) before B5's subprocess end-to-end tests.
- **mypy strict on tests.**
  - pytest ships type information, but fixtures (`monkeypatch: pytest.MonkeyPatch`, `capsys: pytest.CaptureFixture[str]`) must be annotated.
  - Tests have no `__init__.py`; module names stay unique (`test_cli`, `test_package`, ...) so mypy sees no duplicates.
- **Tool version drift** (ruff rule changes, a newer mypy). Lower bounds are listed in the `dev` extra; versions are not pinned, since nothing is installed at check time. If ruff 0.15 lacks a selected rule family, drop that family. Do not add ignores per file.
- **Regex-based pyproject tests are brittle** (no `tomllib` on 3.10). Keep the pyproject formatting canonical (one key per line, double quotes). The tests match those exact lines.

**Rollback:**
- All work lives on `loop/B1`; nothing reaches `main` before the gate.
- If a step goes wrong, revert that step's commit on the branch.
- After the merge, `git revert -m 1 <merge-commit>` on `main` (never `--force`).
- No data, no external state and no installs, so nothing else needs undoing.

## 8. Open questions (recommendation first; mark which block a missing answer blocks)

None that block. Decisions the build agent applies and the gate lists under "Decisions I made":
- The check runs all steps and gives a summary, instead of stopping at the first failure. Recommended because it reports everything at once; the exit code is the same either way.
- The failing-step proof uses `--selftest-fail` / `--selftest-pass` modes in `check.sh` itself, plus a recursion guard (exit 3). This avoids a second helper file and any nested pytest run.
- Version: `0.1.0`, as a static string in both `pyproject.toml` and `__init__.py`, kept in sync by a test.
- CLI with no arguments: usage on stderr and exit 2, matching B5's "2 = usage error".
- ruff line length is 100.
- `NetworkBlockedError` subclasses `RuntimeError`, not `OSError`.
- LICENSE year: 2026.
