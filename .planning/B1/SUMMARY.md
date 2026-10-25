# B1 — Summary

## Status
Date 2026-10-25. Branch `loop/B1`. Steps 1–5 are done. My four commits are `6c2c892..bc07074`, on top of the plan commit `0373b77`. The working tree is clean. Nothing was pushed or merged.

## Done
- **Step 1, `6c2c892`, package skeleton and config.** Files: `pyproject.toml`, `src/commit_kind/{__init__,__main__,cli}.py`, `py.typed`, `.gitignore`. Built to the plan spec. `main(argv)` uses argparse with `prog="commit-kind"`. `--version` prints `commit-kind 0.1.0`, and no arguments gives usage on stderr and returns 2.
- **Step 2, `049ee5b`, network guard and tests.**
  - `tests/conftest.py` has an autouse fixture. It patches `socket.socket` and `socket.create_connection`, and `NetworkBlockedError` subclasses `RuntimeError`.
  - New tests: `tests/test_network_guard.py` (4), `tests/test_package.py` (5), `tests/test_cli.py` (4).
- **Step 3, `ba6e423`, gate script.**
  - `scripts/check.sh` has mode 100755 and is bash 3.2 compatible (string accumulator, no arrays). It has the `run_step` and `finish` functions, `--selftest-pass`, `--selftest-fail`, the recursion guard (exit 3), the usage error (exit 2) and the EVAL marker.
  - `tests/test_check_script.py` has 8 tests.
- **Step 4, `bc07074`, `LICENSE` (MIT, "Copyright (c) 2026 michaelt-45") and a minimal `README.md`.**
- **Step 5.** Verification only, with no fixes needed.

## Deviations from the plan
- Step 2: `ruff --fix` removed a `# noqa: S310` that I had added to a `urlopen` line. The S rules are not enabled, so RUF100 flagged it. It also re-sorted the imports in `tests/test_network_guard.py`. Both changes are cosmetic.
- Step 1: `__main__.py` imports `main` from `commit_kind.cli`, as the plan says it only calls `cli.main`. No other deviation.
- In acceptance item 3 only `FAIL ruff-check` appeared. mypy passed, because an unused import is not a mypy error. The plan allows this ("or at least").
- Step 5: my first criterion-1 run used an unusable temp path (`/tmp/x` is a directory). I re-ran it directly (see Checks). I left no files behind.

## Checks
- Step 1: `python3 -m ruff check src`, `ruff format --check src` and `mypy --strict src` all passed (3 source files). `PYTHONPATH=src python3 -m commit_kind --version` printed `commit-kind 0.1.0`.
- After step 2: 13 pytest tests passed. ruff check, ruff format and mypy --strict were clean on `src tests` (7 files).
- After step 3: `./scripts/check.sh` exited 0, with 21 tests passed.
- After step 4: `./scripts/check.sh` exited 0, with 21 tests passed.
- Section 5 acceptance criteria:
  1. `./scripts/check.sh` printed `PASS ruff-check`, `PASS ruff-format`, `PASS mypy`, `PASS pytest` and `check passed`. The earlier direct runs exited 0 (`rc=0`).
  2. `--selftest-fail` printed `FAIL injected-failure (exit 1)`, with `PASS before-failure` and `PASS after-failure`, then `check failed: injected-failure`, and exited 1. `--selftest-pass` exited 0. `--bogus` printed `usage: scripts/check.sh [--selftest-pass | --selftest-fail]` and exited 2.
  3. Injected violation: with `import os` in `src/commit_kind/_tmp_bad.py`, the output was `FAIL ruff-check (exit 1)`, `PASS ruff-format`, `PASS mypy`, `PASS pytest`, then `check failed: ruff-check`. The exit code was non-zero. I did not capture it in that run, because zsh `PIPESTATUS` is empty, but `finish` exits 1 whenever `FAILED` is set, which the `--selftest-fail` run shows. After `rm` of the file the run was `check passed` again.
  4. `grep -n "EVAL STEP (added in B3)" scripts/check.sh` gave one line, `44:`.
  5. `--version` printed `commit-kind 0.1.0` with rc 0. With no arguments it printed `usage: commit-kind [-h] [--version] {} ...` on stderr, and the exit code was 2.
  6. `pyproject.toml` has `requires-python = ">=3.10"`, `dependencies = []`, the `dev` extra and `commit-kind = "commit_kind.cli:main"`. Tests assert these.
  7. `tests/test_network_guard.py`: 4 passed.
  8. `git ls-files -s scripts/check.sh` gave `100755`.
  9. `LICENSE` has the copyright line, and `README.md` mentions `./scripts/check.sh`. `.gitignore` covers the caches.
  10. The path scan was empty. The e-mail scan, which excludes only `.planning`, hit only the pre-existing `CLAUDE.md` lines 17–18, which hold the noreply identity text. This is not new and none of my files have an address. The plan's exclusion list could add `CLAUDE.md`.
  11. All 5 commits on `main..loop/B1` are authored `michaelt-45 <202262075+michaelt-45@users.noreply.github.com>`. Each of my four messages ends with the exact Co-Authored-By line, and there are no session links. The fifth is the plan commit `0373b77`, which I did not check.
  12. `git diff main...loop/B1 --stat` shows 15 files, all in the section 2 list plus `.planning/B1/PLAN.md`.
- The bash used by the script is `/usr/bin/env bash`, 3.2.57. `bash -n` is covered by a test.

## Checked by hand
`--version` and the no-argument usage error (rc 2) run through the module entry point. The three `check.sh` modes (real, selftest-fail, bogus) and the injected-violation run were also done by hand.

## Backlog
Proposed entries, not files:
- Created: a subprocess-level network guard (for example a `sitecustomize` on `PYTHONPATH` for tests) before B5's subprocess end-to-end tests, because the in-process socket patch does not cover child processes.
- Created: add `CLAUDE.md` to the exclusions of the e-mail hygiene scan, or reword it, since it matches the noreply text.
- Created: B2 adds `scripts` to the ruff and mypy targets in `check.sh` once `scripts/*.py` exists.
- Closed: none.

## Open / risks / follow-ups
- shellcheck is not installed, so `bash -n` is the only shell lint.
- The regex-based `pyproject.toml` tests depend on the canonical formatting, one key per line.
- The README is minimal and B5 rewrites it.
- STATE.md updates are left to the orchestrator.

## Files changed
`.gitignore`, `LICENSE`, `README.md`, `pyproject.toml`, `scripts/check.sh`, `src/commit_kind/__init__.py`, `src/commit_kind/__main__.py`, `src/commit_kind/cli.py`, `src/commit_kind/py.typed`, `tests/conftest.py`, `tests/test_check_script.py`, `tests/test_cli.py`, `tests/test_network_guard.py`, `tests/test_package.py`
