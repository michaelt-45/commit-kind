# B3 — Summary (trim)

## Status
Date 2026-10-25. Branch `loop/B3`. Commit range `bd12d6d..bf2548a`: one commit, "Trim the eval to the roadmap criteria and merge the B3 tests". The tree is clean. I did not push or merge. I did not create `evals/config.json` and did not wire `check.sh`. I did not touch `data/commits.jsonl`.

## Removed
- `require_classifier_from_block` / `classifier_required`.
- Dataset sha256 and `dataset_mismatch`.
- `--reason` and baseline `notes`.
- `thresholds_status`.
- `--show-errors` JSON output.
- `StrategyFactory` (the registry now holds plain callables).
- The AST stdlib-only test.
- The `Record`, `Config` and `Baseline` dataclasses (plain dicts now).
- Per-key config validation beyond: required keys present, thresholds exactly the four metrics and in [0,1], all three controls listed, classifier not a control and present in `REGISTRY`.
- Four test files, merged into one: `tests/test_strategies.py`, `tests/test_metrics.py`, `tests/test_eval_gate.py`, `tests/test_eval_cli.py`.

## Kept (CLI and exit-code contract)
- **CLI:** `eval [--config PATH] [--json] [--split {test,dev}] [--show-errors] [--write-baseline --block B<n>]`.
  - `--split dev` is informational: it prints a header, applies no gate and writes no baseline.
  - `--show-errors` works only with `--split dev` and plain text.
- **Exit codes:**
  - 0: pass.
  - 1: gate failed, or a baseline write was refused (nothing is written).
  - 2: usage error.
  - 3: missing or invalid config, dataset or baseline, or a bad strategy output. A missing dataset prints the generate command.
- **Metrics:** accuracy, macro_f1, min_recall and misleading_accuracy on the test split, with one `q()` rounding to 4 digits at storage, display and comparison. The 246/291 rounding test is kept.
- **Controls:** majority, keyword_spam and random, with the same semantics as before. `Strategy`, `StrategyContext`, `REGISTRY` and `CONTROL_NAMES` are kept.
- **Gate:**
  - A control reaching any threshold gives "too lenient: <metric>".
  - A classifier below threshold fails.
  - A classifier below its baseline entry fails.
  - A missing classifier baseline entry fails, except during `--write-baseline`.
- **Config and baseline:**
  - `evals/config.json` keys are `baseline`, `classifier`, `controls`, `dataset`, `finished_blocks`, `keyword_spam`, `random_seed` and `thresholds`.
  - `evals/baseline.json` is `{"strategies": ..., "written_for_block": ...}`, written atomically.
  - `--write-baseline` also adds the block to `finished_blocks`.
- The "Trim" note is appended to `.planning/B3/PLAN.md` (7 bullets).

## Checks
- `./scripts/check.sh`: ruff-check, ruff-format, mypy `--strict` (14 files) and pytest (51 passed) all PASS; "check passed".
- Line counts, before → after (`wc -l`):

| File | Before | After |
|---|---|---|
| `src/commit_kind/evaluate.py` | 830 | 261 |
| `src/commit_kind/strategies.py` | 84 | 61 |
| `src/commit_kind/labels.py` | 3 | 3 |
| `tests/_evalfixtures.py` | 151 | 62 |
| `tests/test_eval.py` (new) | n/a | 222 |
| `tests/test_eval_cli.py` | 616 | removed |
| `tests/test_strategies.py` | 103 | removed |
| `tests/test_metrics.py` | 110 | removed |
| `tests/test_eval_gate.py` | 94 | removed |

- B3 tests together: 1074 → 284 lines, within the 300 budget. `evaluate.py` is 261, about 10 over the ~250 target.
- **Tests proving each metric fails and passes:**
  - `test_gate_boundary_per_metric[<metric>]` checks all four metrics. A value exactly at threshold passes, threshold minus 0.0001 gives "below threshold: <metric>", and a control exactly at threshold gives "too lenient: <metric>".
  - `test_classifier_failing_each_metric[<metric>]` runs end to end on a data fixture and expects rc 1 with the named failure for each metric.
  - `test_controls_only_and_classifier_pass` is the passing twin: rc 0, and a perfect oracle classifier passes all four metrics.
- **Tests proving each failure kind:**
  - Too lenient: `test_friendly_fixture_makes_keyword_spam_too_lenient` (four failures naming keyword_spam), plus the boundary test.
  - Below threshold: the two tests above.
  - Below baseline: `test_below_baseline_fails`.
  - Missing classifier baseline entry: `test_gate_baseline_and_rounding_246_of_291`. Writing a baseline with no entry is allowed: `test_write_baseline`.
  - Rounding: `test_gate_baseline_and_rounding_246_of_291`.
  - Write refusal with nothing written: `test_write_baseline_refuses_and_writes_nothing`.
  - Exit 2: `test_usage_errors_exit_2` (5 cases).
  - Exit 3: `test_input_errors_exit_3` (bad baseline JSON, missing baseline, missing dataset with generate hint, missing config key, control as classifier, missing config) and `test_bad_strategy_output_exit_3`.
  - Dev informational: `test_dev_split_is_informational`.
  - Subprocess run: `test_module_entry_subprocess`.
  - Strategy semantics: the three strategy tests.
- All tests build their inputs on `tmp_path` and never read the live config, baseline or dataset.
- I did not run the CLI by hand against live data (there is none yet); the golden and error paths are covered by the in-process and subprocess tests above.

## Files changed
- `src/commit_kind/evaluate.py` (rewritten)
- `src/commit_kind/strategies.py` (slimmed)
- `tests/_evalfixtures.py` (rewritten)
- `tests/test_eval.py` (new)
- `tests/test_strategies.py`, `tests/test_metrics.py`, `tests/test_eval_gate.py`, `tests/test_eval_cli.py` (deleted)
- `.planning/B3/PLAN.md` (Trim note appended)
- `src/commit_kind/labels.py` and `src/commit_kind/cli.py` are unchanged.
