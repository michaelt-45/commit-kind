# B3 — Summary (step 4)

## Status
Date 2026-10-25. Branch `loop/B3`. Commit range `4810cc7..1acf513`: merge `c6f91ff` plus 4 commits (`d220fe6`, `f6f4eac`, `400001e`, `1acf513`). The tree is clean. Nothing was pushed or merged to main.

## Done
- Merged `main` into `loop/B3` (B2 dataset, generator, `.planning/B2`). The merge was clean and the message ends with the required trailer.
- `evals/config.json`:
  - `dataset` is `../data/commits.jsonl` and `baseline` is `baseline.json`.
  - Thresholds are accuracy 0.85, macro_f1 0.85, min_recall 0.70, misleading_accuracy 0.70.
  - `keyword_spam` was copied from `CONTROL_KEYWORDS` in `scripts/generate_dataset.py`.
  - The three controls are listed, `random_seed` is 20261025, and `classifier` is null.
- `scripts/check.sh`: only the commented line between the EVAL markers became `run_step eval "$PY" -m commit_kind eval`.
- Two tests in `tests/test_check_script.py`:
  - `test_eval_step_is_wired_between_markers`.
  - `test_generator_keywords_match_eval_config`: static read of the live config against the generator's `CONTROL_KEYWORDS`.
- `eval --write-baseline --block B3` wrote `evals/baseline.json`, and `evals/config.json` now has `finished_blocks: ["B3"]`.
- README `## Eval` section, 6 lines. It covers the command, the controls, exit codes, thresholds as a proposal awaiting owner approval, and `--split dev --show-errors`.

## Deviations
- The `evals/config.json` commit (`d220fe6`) already contains `finished_blocks: ["B3"]`, because I wrote the baseline before committing. The baseline commit (`400001e`) therefore holds only `evals/baseline.json`.
- `eval` exits 3 while no baseline exists, even with no classifier configured. I could not run a plain `eval` before the baseline write, so the control numbers below come from the `--write-baseline` run. That run applies the same gate and exits 0.
- No control passed any metric, so I did not stop.

## Checks
- `./scripts/check.sh`: PASS ruff-check, ruff-format, mypy, pytest, eval (5 PASS), then `check passed`, rc 0.
- Eval table (test split; every control fails all four metrics):

| strategy | accuracy | macro_f1 | min_recall | misleading_accuracy |
|---|---|---|---|---|
| threshold | 0.8500 | 0.8500 | 0.7000 | 0.7000 |
| majority | 0.1667 fail | 0.0476 fail | 0.0000 fail | 0.1667 fail |
| keyword_spam | 0.5389 fail | 0.5454 fail | 0.4000 fail | 0.0000 fail |
| random | 0.1667 fail | 0.1671 fail | 0.1333 fail | 0.1333 fail |

- Baseline: `{"strategies": {majority, keyword_spam, random: the four metrics above}, "written_for_block": "B3"}`.
- By hand:
  - `python -m commit_kind eval` (golden path) exits with rc 0.
  - `python -m commit_kind eval --config does-not-exist.json` prints "config not found" and exits with rc 3.

## Files changed
- `evals/config.json` (new)
- `evals/baseline.json` (new)
- `scripts/check.sh`
- `tests/test_check_script.py`
- `README.md`
- B2 files came in through the merge: `data/commits.jsonl`, `scripts/generate_dataset.py`, `tests/test_dataset.py`, `.planning/B2/*`.
