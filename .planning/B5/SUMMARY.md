# B5 — Summary

## Status
Finished 2026-10-25 on branch `loop/B5`. Commit range `main..loop/B5`:
- `9127e3a` PLAN.md, already on the branch when I started
- `1139e84` classify subcommand
- `a15b429` README
- `8d91cd4` baseline

All four commits use the author `michaelt-45 <…@users.noreply.github.com>`. The three I made end with the Opus 5.5 trailer and nothing after it. Nothing was pushed or merged.

## Done
- **Step 1 (classify subcommand):** `classify <message>` with `--json` and `--explain`, which are mutually exclusive. `-` reads all of stdin as one message, decoded with `utf-8` and `replace`. `KIND_TEXT` has the 5 phrases and `explain()` builds the one-line text. An unknown kind falls back to `rule "<evidence>" matched`.
- **Step 1 (network guard):** `tests/sitecustomize.py` is two lines, so child processes block sockets. The backlog item `20261025-subprocess-netguard` is set to `status: done`.
- **Step 1 (tests):** `tests/test_classify_cli.py` has the 8 planned tests: label, json, explain, stdin, empty (3 parametrized cases), usage (3 parametrized cases), every kind in `KIND_TEXT`, and child network blocked.
- **Step 2 (README):** full rewrite following the outline. Every output block was pasted from a real `PYTHONPATH=src python3 -m commit_kind ...` run. The Limits section covers all three honesty points: synthetic data from this project's own templates; tuned on dev only but dev and test share templates, so the 1.0 score says little about real repositories; the B2 review found a dev-fitted first-word lookup would also have passed, with no number quoted. It links `.planning/B2/REVIEW.md`. The `.planning/` paragraph links the gated-build-loop repo and mentions no other project. The `## Eval` facts and the 2026-10-25 approval are kept.
- **Step 3 (baseline):** `eval --write-baseline --block B5`. The baseline diff changes only `written_for_block`. The config diff only appends `B5` to `finished_blocks`.
- **Step 4 (hygiene):** scanned `git log -p` for e-mail addresses, session links and local paths. The only matches were pytest decorator text, so the scan is clean.

## Deviations
- `ruff format` reformatted `cli.py` and the tests. That is the repo's own format step.
- The `cli.py` diff and the new tests are slightly over the plan's rough budget (see Checks). The README is within it.

## Checks
- **`./scripts/check.sh`:** 5 PASS and `check passed` after each step and on the final tree. pytest ran 128 tests, all passing.
- **Eval:** numbers unchanged from B4. The classifier scores 1.0000 on all four metrics, and the three controls fail every metric. `eval` exits 0.
- **By hand:**

| Command | Output | rc |
|---|---|---|
| `classify "fix: handle empty input"` | `fix` | 0 |
| `classify --json "fix: handle empty input"` | `{"evidence": "fix:", "label": "fix", "rule": "prefix.fix"}` | 0 |
| `classify --explain "add retry to the client"` | `feat because the verb phrase "add" matched (rule ambiguous.add)` | 0 |
| stdin `docs: reword the intro` + body | `docs` | 0 |
| `classify ""` | `classify: error: empty commit message` on stderr, stdout empty | 1 |
| `classify` | usage on stderr | 2 |
| `classify --json --explain x` | usage on stderr | 2 |

- **`git diff --numstat main...loop/B5`:**
  - `src/commit_kind/cli.py`: +45 -1
  - `tests/test_classify_cli.py`: +81
  - `tests/sitecustomize.py`: +3
  - `README.md`: +61 -26
  - `.planning/B5/PLAN.md`: +100 (the plan commit)
  - `.planning/backlog/20261025-subprocess-netguard.md`, `evals/baseline.json` and `evals/config.json`: one to two changed lines each
- **`wc -l README.md`:** 86.

## Files changed
- `src/commit_kind/cli.py`
- `tests/sitecustomize.py`
- `tests/test_classify_cli.py`
- `README.md`
- `evals/baseline.json`
- `evals/config.json`
- `.planning/backlog/20261025-subprocess-netguard.md`
- `.planning/B5/PLAN.md` (already on the branch, not edited by me)
