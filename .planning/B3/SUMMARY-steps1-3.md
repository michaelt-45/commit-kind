# B3 — Summary (steps 1–3)

## Status
- Date 2026-10-25. Branch `loop/B3`. Commits `015a8af` through `ecb2253`, on top of `8f2b680` (Plan block B3); four commits, all with the required trailer.
- Steps 1, 2 and 3 are done. Step 4 is not started: no `evals/config.json`, no check.sh wiring, no README section, no `data/commits.jsonl` read.
- Commits:
  - `015a8af` LABELS, strategy interface, controls.
  - `37b13b6` eval core.
  - `28487cb` eval subcommand.
  - `ecb2253` end-to-end tests.

## Done
- Step 1:
  - `labels.py` holds `LABELS`.
  - `strategies.py` holds `Strategy`, `StrategyContext`, `StrategyFactory`, `CONTROL_NAMES` and `REGISTRY` with the three controls.
  - Control rules match the plan: majority uses dev only, with ties going to LABELS order; keyword_spam uses `[a-z0-9]+` tokens with repetition and ties/zero hits going to `feat`; random uses `Random(seed)` and `randrange(6)`.
- Step 2 (`evaluate.py` core):
  - Typed loaders for config, dataset and baseline raise `InputError` (exit 3). Errors name the file, and the dataset loader names the line.
  - Config rejects unknown keys, missing controls and thresholds outside [0,1].
  - `q()`, `compute_metrics` and the pure `gate()` implement all six failure kinds.
  - `run_eval(config, registry=REGISTRY, split)` scores the controls and the classifier, and treats a bad prediction or an exception in predict as exit 3 naming the strategy and record id.
  - Table and canonical JSON rendering.
  - Atomic baseline and config writers (`os.replace`).
  - `tests/_evalfixtures.py` holds the fixture helpers.
- Step 3:
  - `configure_parser`, `run_from_args`, and `eval` registered in `cli.py` (the `metavar` stays).
  - Flags `--config --json --split --show-errors --write-baseline --block --reason`, with exit codes 0/1/2/3.
  - Dev view prints the `informational: dev split, not gated` header, compares nothing, writes nothing and loads no baseline.
  - Baseline writing is refused (rc 1, nothing written) on `too_lenient`, `below_threshold` or `classifier_required`. `below_baseline` and `dataset_mismatch` need `--reason`, which is appended to `notes`.

## Deviations from the plan
- The keyword contract and dataset schema are not both "repeated in the plan and ROADMAP". The ROADMAP has the schema; the keyword lists live only in B2's plan, which is not in this tree. This did not block steps 1–3: tests use fixture keyword lists (`KEYWORDS` in `tests/_evalfixtures.py`). Step 4 must copy the lists verbatim from B2.
- `--write-baseline` requires `--block` (usage error 2 otherwise). The plan only shows it together with `--block`.
- During `--write-baseline`, a `missing_baseline` failure is not counted, so a first entry for a new classifier can be written (needed for B4). A completely missing baseline file is also allowed there, as the plan says.
- `--show-errors` also works with `--json` and adds an `errors` key. It lists the classifier's errors if one is configured, otherwise the controls' errors. This is a small extra.
- Usage errors in `run_from_args` return 2 after printing `commit-kind eval: error: ...`, not through argparse. An invalid `--split` value still exits 2 through argparse.
- Loaders also reject duplicate dataset ids, an empty dataset, and a dataset with no dev rows. All are exit 3.
- Not done: a test that a written baseline equals a hand-written file. Canonical format is checked instead.

## Checks
- `./scripts/check.sh` after every step: final run is ruff-check PASS, ruff-format PASS, mypy --strict PASS (17 files), pytest PASS (95 passed), `check passed`, rc 0.
- Manual: `eval --config nope.json` gives rc 3; `eval --show-errors` gives rc 2; a fixture config without a baseline gives rc 3 and names the path. The golden path (rc 0 with a table) runs in the tests only, on `tmp_path` fixtures.
- Hygiene: `git grep` for local paths and for e-mail addresses (outside CLAUDE.md and .planning) prints nothing. The repo tree is clean.
- Proof per failure kind, with the test that fires it:
  - `too_lenient` (all four metrics): `test_eval_gate.py::test_too_lenient_per_metric[...]` (a control exactly at the threshold fires; at threshold − 0.0001 it does not). End to end: `test_fx_keyword_friendly_makes_keyword_spam_too_lenient` and `test_fx_lenient_thresholds` (majority).
  - `below_threshold`:
    - gate level: `test_below_threshold_per_metric[accuracy|macro_f1|min_recall|misleading_accuracy]`, each with a passing twin at the boundary.
    - data level: `test_fx_accuracy_low` (0.8333), `test_fx_macro_f1_low`, `test_fx_min_recall_low` (0.6; only min_recall fires), `test_fx_misleading_low` (0.6667; only misleading fires), with `test_oracle_passes_every_metric` as the twin.
  - `below_baseline`: `test_below_baseline` (0.90 vs 0.95 fires, equal passes); `test_rounding_246_of_291` (stored 0.8454, no false regression, and `246/291 < 0.8454` asserted); `test_write_baseline_regression_needs_reason`.
  - `missing_baseline`: `test_missing_baseline_entry_fails_closed`.
  - `dataset_mismatch`: `test_dataset_mismatch`.
  - `classifier_required`: `test_classifier_required_after_block` and `test_classifier_required_end_to_end`.
  - Also covered:
    - exit 3 cases: missing dataset, config and baseline; invalid JSON; unknown config key; missing control; threshold out of range; schema violation naming `commits.jsonl:3`; no misleading rows; label without support; invalid prediction; predict raising; bad classifier name.
    - exit 2 cases: `--show-errors` without dev, `--write-baseline` with dev, and bad flag combinations.
    - other behaviour: dev view, rounding of JSON and baseline values, first baseline write with idempotent `finished_blocks`, write refusals, a subprocess `python -m commit_kind eval`, and a stdlib-only AST check.

## Backlog
- Add a `--write-baseline` dry run (print what would change).
- `tests/test_eval_step.py` and the live-file ban test belong to step 4 as planned.
- `evaluate.py` is about 830 lines; split loading/gate/rendering/CLI into modules after B5 if wanted.
- Consider `--only <strategy>` for `--show-errors` once B4 has more than one classifier.

## Open / risks
- Step 4 waits for B2 on `main`. The `keyword_spam` lists in `evals/config.json` must equal B2's contract verbatim, and the real-data control numbers in section 2 of the plan are still unverified.
- Thresholds in fixtures are the proposal values only. Nothing is approved.
- Tests that need a classifier monkeypatch `REGISTRY` in place (`monkeypatch.setitem`). `test_registry_is_untouched_by_tests` guards against leaks.

## Files changed
- `src/commit_kind/labels.py` (new)
- `src/commit_kind/strategies.py` (new)
- `src/commit_kind/evaluate.py` (new)
- `src/commit_kind/cli.py` (eval registration, 8 lines)
- `tests/_evalfixtures.py` (new)
- `tests/test_strategies.py` (new)
- `tests/test_metrics.py` (new)
- `tests/test_eval_gate.py` (new)
- `tests/test_eval_cli.py` (new)
