# B3 — Plan

## 1. Goal and user-visible result

B3 adds the gated eval: `python -m commit_kind eval [--json]`. It scores strategies on the `test` split of `data/commits.jsonl` and applies four gated metrics, each rounded to 4 digits at storage and at comparison:
- accuracy
- macro-F1
- min per-class recall
- misleading-slice accuracy

It always runs three negative controls: `majority`, `keyword_spam` and `random`. The eval exits non-zero when:
- any control reaches any threshold: that metric is named "too lenient";
- the configured classifier is below threshold or below baseline;
- inputs are missing or invalid.

Until B4 there is no classifier. The eval then scores the controls only and exits 0 when every control fails every metric.

`./scripts/check.sh` runs the eval as its fifth step. `--write-baseline --block <B>` rewrites `evals/baseline.json` and marks the block in `finished_blocks`. `--split dev [--show-errors]` gives B4 an informational tuning view that never touches the test split.

Merge order (decided): **B2 merges first, then B3.**
- If the dataset is missing, the eval prints `eval: dataset not found: <path> (from <config>); generate it with: python3 scripts/generate_dataset.py --seed 20261025 --out data/commits.jsonl` to stderr and exits **3**. It fails closed.
- B3 builds steps 1–3 standalone. In that state `check.sh` is still green, because the eval is not yet wired.
- Step 4 starts only after B2 is on `main`: merge `main` into `loop/B3`, wire the eval, write the baseline. The branch tip is then the merged tree, and the full check is green on it.
- If B3 reaches step 4 first, it pauses and the orchestrator notes this in STATE.
- Rejected: merging B3 first with "skip the eval when there is no data". That is fail-open, a gate that can never fail. Also rejected: a bundled toy dataset as default, because the gate would then measure toy data and the baseline would need rewriting anyway.

## 2. Interfaces and file ownership (what other blocks may touch, what they must not)

| File | Owner | Later blocks may | Later blocks must not |
|---|---|---|---|
| `src/commit_kind/labels.py` | B3 | — | reorder or rename `LABELS` |
| `src/commit_kind/strategies.py` | B3 | **B4**: add one registry entry (`"rules"`) | change, remove or rename controls; let strategies see labels or test data |
| `src/commit_kind/evaluate.py` | B3 | fix bugs with tests | change rounding, `>=` semantics, test-split scoring or fail-closed behaviour |
| `src/commit_kind/cli.py` | B1 | **B3**: register `eval` (a few lines); **B5**: `classify` | — |
| `evals/config.json` | B3 | **B4**: set `"classifier": "rules"` in the same commit as its baseline write; orchestrator/human: thresholds after approval; `--block` appends to `finished_blocks` | drop a control; edit keyword lists to make a control fail; change thresholds without the human's approval |
| `evals/baseline.json` | B3 (written only by `--write-baseline`) | rewrite via the flag | edit by hand |
| `scripts/check.sh` | B1 | **B3**: only the commented line between `# >>> EVAL STEP (added in B3) >>>` and `# <<< EVAL STEP <<<` becomes `run_step eval "$PY" -m commit_kind eval` | keep the markers out (B1's `test_eval_marker_present_once` needs them); touch other lines (B2 owns the ruff/mypy target edit) |
| `tests/_evalfixtures.py`, `tests/test_strategies.py`, `tests/test_metrics.py`, `tests/test_eval_gate.py`, `tests/test_eval_cli.py`, `tests/test_eval_step.py` | B3 | add tests | read `data/commits.jsonl`, `evals/config.json` or `evals/baseline.json` |
| `README.md` | B1/B5 | **B3**: an `## Eval` section, added in step 4 after merging `main` | — |

**Edits in B1-owned files:** in `cli.py`, B3 keeps the review's `metavar="<command>"` and adds:
```python
p = sub.add_parser("eval", help="score strategies on the dataset")
evaluate.configure_parser(p)
...
if args.command == "eval":
    return evaluate.run_from_args(args)
```

**Plug-in interface for B4:**
```python
# commit_kind/labels.py
LABELS: tuple[str, ...] = ("feat", "fix", "docs", "refactor", "test", "chore")

# commit_kind/strategies.py
class Strategy(Protocol):
    def predict(self, message: str) -> str: ...  # must return one of LABELS

@dataclass(frozen=True)
class StrategyContext:
    dev_messages: tuple[str, ...]  # dev split only, never test
    dev_labels: tuple[str, ...]
    labels: tuple[str, ...]
    keywords: Mapping[str, tuple[str, ...]]  # from config
    seed: int

StrategyFactory = Callable[[StrategyContext], Strategy]
CONTROL_NAMES: tuple[str, ...] = ("majority", "keyword_spam", "random")
REGISTRY: dict[str, StrategyFactory] = {...}  # the three controls
```

- B4 adds `"rules": lambda ctx: _RuleStrategy()`, where `predict(m)` returns `classify(m).label`. Rules are not fitted at eval time.
- B4 sets `"classifier": "rules"` and runs `eval --write-baseline --block B4` in the same commit.
- `predict` sees only the message. Predictions run in file order.
- Any of the following is an input error (exit 3, naming the strategy and record id):
  - a prediction outside `LABELS`;
  - an exception in `predict`;
  - a classifier name that is a control or not in the registry.
- `run_eval(config, registry=REGISTRY)` takes the registry as a parameter, so tests inject scripted strategies.

**Controls:**
- `majority`: the most frequent dev label; ties go to the first in `LABELS` order.
- `keyword_spam`:
  - tokens are `re.findall(r"[a-z0-9]+", message.lower())`; hits count tokens equal to a label's list entries, with repetition;
  - it predicts the argmax; ties, including all-zero, go to the first in `LABELS` order;
  - the lists live in `evals/config.json` and equal B2's keyword contract verbatim.
- `random`: `random.Random(seed)`, then `LABELS[rng.randrange(6)]` per record in file order.

**`evals/config.json`:**
- Canonical format: `sort_keys`, indent 2, trailing newline.
- Unknown keys are exit 3, so a typo cannot silently drop a gate.
- Paths are relative to the config file's directory.
```json
{
  "baseline": "baseline.json",
  "classifier": null,
  "controls": ["keyword_spam", "majority", "random"],
  "dataset": "../data/commits.jsonl",
  "finished_blocks": ["B1", "B2"],
  "keyword_spam": {"chore": [...], "docs": [...], "feat": [...], "fix": [...], "refactor": [...], "test": [...]},
  "random_seed": 20261025,
  "require_classifier_from_block": "B4",
  "thresholds": {"accuracy": 0.85, "macro_f1": 0.85, "min_recall": 0.7, "misleading_accuracy": 0.7},
  "thresholds_status": "proposal, approval open"
}
```
- `controls` must contain all three names; otherwise exit 3, because hard rule 4 cannot be configured away.
- `thresholds` must contain exactly the four metrics, each in [0, 1].

**`finished_blocks` semantics:**
- It lists blocks merged under the eval gate (B1 and B2 pre-seeded, since they precede the eval).
- `--write-baseline --block <B>` appends `<B>` (pattern `^B\d+$`, idempotent) and rewrites the config canonically.
- Gate effect: if `require_classifier_from_block` is in `finished_blocks` and `classifier` is null, the failure is `classifier_required` (exit 1). This stops a later block from silently dropping the classifier and passing on controls only.

**`evals/baseline.json`:** written only by `--write-baseline`, canonical, every value already rounded:
```json
{
  "dataset": {"records": 360, "sha256": "<file sha256>"},
  "notes": [{"block": "B3", "reason": "initial baseline, controls only"}],
  "split": "test",
  "strategies": {"keyword_spam": {...4 metrics}, "majority": {...}, "random": {...}},
  "written_for_block": "B3"
}
```

**Baseline rewrite on merge (the orchestrator rewrites no numbers by hand):**
1. A block's final build step (from B3 on) runs on its branch after `git merge main`: `python -m commit_kind eval --write-baseline --block B<n> [--reason "<text>"]`, commits `evals/`, then runs `./scripts/check.sh`.
2. The orchestrator merges `--no-ff`.
3. If `main` moved in the meantime, the orchestrator merges `main` into the branch again and re-runs `check.sh`. If that is not green, the block goes back to a build agent.

**`--write-baseline`:**
- Refuses (exit 1, nothing written) on `too_lenient`, `below_threshold`, `classifier_required` or any input error.
- `below_baseline` and `dataset_mismatch` need `--reason`, which is appended to `notes`. That is "worse only with a stated reason".
- A missing baseline file is allowed (first write).
- `--write-baseline` together with `--split dev` is usage error 2.

**CLI:** `commit-kind eval [--config PATH] [--json] [--split {test,dev}] [--show-errors] [--write-baseline] [--block B<n>] [--reason TEXT]`.
- `--config` defaults to `evals/config.json`, relative to the working directory; `check.sh` runs from the repo root.
- `--show-errors` only with `--split dev`; with test it is usage error 2, so the tool never lists test records.
- `--block` and `--reason` only with `--write-baseline`.
- Exit codes:
  - 0: gate passed (or a dev run completed);
  - 1: gate failed (any failure, or a refused baseline write);
  - 2: usage error (argparse);
  - 3: input error, meaning a missing or invalid config, dataset or baseline, a schema violation, a test split without some label or without misleading rows, or a bad strategy.
- Errors go to stderr.
- **Dev runs** print the table with the header `informational: dev split, not gated`, compare nothing and write nothing.

**Metrics** (on the test split only; every value is passed through `q(x) = round(x, 4)` before storage, display and every comparison; thresholds and baseline values are passed through `q` on load):
- `accuracy` = correct / n.
- `macro_f1` = mean over all six `LABELS` of F1. P = TP/(TP+FP), or 0 with no predictions; R = TP/support; F1 = 2PR/(P+R), or 0 when P+R = 0.
- `min_recall` = the minimum over the six labels of TP/support. A label with zero test support is exit 3.
- `misleading_accuracy` = accuracy over test rows with `slice == "misleading"`. Zero such rows is exit 3, because a metric that cannot be computed must not silently pass.
- Pass means `q(value) >= q(threshold)`.

**Gate** (all checks run and every failure is listed; nothing stops at the first failure):

| kind | condition |
|---|---|
| `too_lenient` | any control with `q(m) >= q(t_m)`; the message is `metric <m> too lenient: control <c> reaches <v> >= <t>` |
| `below_threshold` | classifier `q(m) < q(t_m)` |
| `below_baseline` | classifier `q(m) < q(baseline[classifier][m])` |
| `missing_baseline` | classifier configured but no baseline entry for it; fail-closed |
| `dataset_mismatch` | baseline `sha256` ≠ the current dataset file's sha256 |
| `classifier_required` | see `finished_blocks` above |

A missing `evals/baseline.json` is exit 3 (`run --write-baseline`), except during `--write-baseline`.

**Output:**
- Table on stdout. Rows: `threshold`, each control, then the classifier (or `classifier: none configured (controls only)`). Columns: strategy, role, then the four metrics as `0.1667 fail` / `0.9012 pass`. A legend says controls must fail every metric and the classifier must pass every one.
- Then `eval passed`, or `eval failed:` followed by one line per failure.
- `--json` prints one canonical object instead: `{"split", "dataset": {"path", "sha256", "records", "evaluated"}, "thresholds", "thresholds_status", "classifier", "strategies": {name: {"role", "metrics", "pass": {metric: bool}}}, "failures": [{"kind", "strategy", "metric", "value", "limit", "message"}], "ok"}`.

The modules use the standard library only: `json`, `hashlib`, `re`, `random`, `argparse`, `dataclasses`, `pathlib`, `typing`. No network.

## 3. Steps
| # | Step | Files | Check | Model | Size |
|---|---|---|---|---|---|
| 1 | `LABELS`; `Strategy` protocol, `StrategyContext`, the three controls, `REGISTRY`, `CONTROL_NAMES`; tests | `src/commit_kind/labels.py`, `src/commit_kind/strategies.py`, `tests/test_strategies.py` | `python3 -m pytest -q tests/test_strategies.py`; `./scripts/check.sh` green | sonnet | S |
| 2 | `evaluate.py` core: typed loading and validation of config, dataset and baseline (exit 3 on anything invalid, with file and line); metrics plus `q`; `gate()` as a pure function returning a list of `Failure`; table and JSON rendering; baseline/config writers (canonical, atomic `os.replace`); fixture helpers; tests | `src/commit_kind/evaluate.py`, `tests/_evalfixtures.py`, `tests/test_metrics.py`, `tests/test_eval_gate.py` | those tests green; `mypy --strict src tests` clean; `./scripts/check.sh` green | sonnet | M |
| 3 | `eval` subcommand: `configure_parser`, `run_from_args`, every flag and exit code, `--split dev`/`--show-errors`, `--write-baseline`/`--block`/`--reason`; `cli.py` registration; end-to-end tests against `tmp_path` fixture configs (in-process `main([...])` plus one subprocess `python -m commit_kind eval --config <tmp>` with `PYTHONPATH=src`, `timeout=30`) | `src/commit_kind/evaluate.py`, `src/commit_kind/cli.py`, `tests/test_eval_cli.py` | tests green; `./scripts/check.sh` green (eval not wired yet) | sonnet | M |
| 4 | **Starts only when B2 is on `main`.** `git merge main` into `loop/B3` (expect a clean merge of `check.sh`; on a conflict keep both sides' lines and report it). Create `evals/config.json`. Wire the EVAL line. Add `tests/test_eval_step.py`. Run `python -m commit_kind eval` and confirm the section 2 control numbers: if any control passes, **stop and report**, never tune thresholds or lists. Run `eval --write-baseline --block B3 --reason "initial baseline, controls only"`. Add the README `## Eval` section (at most 10 lines: command, exit codes, thresholds are a proposal, `--split dev` for tuning) | `evals/config.json`, `evals/baseline.json`, `scripts/check.sh` (1 line), `tests/test_eval_step.py`, `README.md` | `./scripts/check.sh` shows 5 PASS lines, `check passed`, rc 0 | sonnet | S |
| 5 | Final verification: the manual negative controls and hygiene in section 5; summary between markers | none (fixes only) | all section 5 items pass | haiku | S |

Parallel groups and order:
- Steps 1 → 2 → 3 run in `loop/B3`, in parallel with B2.
- Step 4 waits for B2's merge, then 4 → 5.
- One agent at a time on this branch.
- `check.sh` after every step.

## 4. Tests (name — what it proves; include error paths and one negative control per metric)

All tests build configs, datasets and baselines in `tmp_path` via `tests/_evalfixtures.py`, for example:
- `make_records(spec)`;
- `write_case(tmp_path, records, thresholds=PROPOSAL, classifier=None, baseline=None, finished=("B1", "B2"))`;
- `scripted(predictions: dict[str, str])`, a strategy keyed by message;
- `oracle(records)`.

No test reads `data/commits.jsonl`, `evals/config.json` or `evals/baseline.json`. The default-config test uses `monkeypatch.chdir(tmp_path)`. A standard fixture has 60 test records (10 per label: 4 prefixed, 3 plain, 3 misleading) plus 60 dev records.

**`tests/test_strategies.py`:**
- `test_majority_uses_dev_only`: dev is mostly `docs` and test mostly `fix`; majority predicts `docs`. A spy factory proves `StrategyContext` has no test rows.
- `test_majority_tie_breaks_by_label_order`: balanced dev gives `feat`.
- `test_keyword_spam_counts_tokens_with_repetition`: "fix the fix docs" gives `fix`; exact tokens, so "fixture" is not a `fix` hit.
- `test_keyword_spam_ties_and_zero_hits`: a tie goes to the first in `LABELS` order; zero hits gives `feat`.
- `test_random_is_seeded`: same seed, same sequence; different seed, different; all values in `LABELS`.
- `test_registry_contains_all_controls`.

**`tests/test_metrics.py`:**
- `test_perfect_predictions`: all four metrics are 1.0.
- `test_hand_computed_confusion`: a 12-row case with accuracy, macro-F1 and per-label recall computed by hand.
- `test_f1_zero_when_label_never_predicted`.
- `test_scores_test_split_only`: the scripted strategy is wrong on every dev row and right on every test row, so accuracy is 1.0.
- `test_rounding_246_of_291`: 291 test rows, 246 correct:
  - stored accuracy is `0.8454`;
  - a baseline containing `0.8454` gives **no** `below_baseline`;
  - the test also asserts `246 / 291 < 0.8454`, which shows unrounded comparison would have flagged a false regression.
- `test_values_rounded_in_json_and_baseline`: every number in `--json` output and in a written baseline has at most 4 decimals and equals `q(value)`.

**`tests/test_eval_gate.py`** (pure `gate()` with given metric dicts; one failing and one passing case per metric and per kind). The isolated per-metric fixture sets every value exactly at its threshold except one:

| metric | failing fixture | expected failure | passing twin |
|---|---|---|---|
| accuracy | classifier accuracy = threshold − 0.0001, others = threshold | exactly one `below_threshold accuracy` | all at threshold, so no failure (boundary inclusive) |
| macro_f1 | same pattern | one `below_threshold macro_f1` | same |
| min_recall | same pattern | one `below_threshold min_recall` | same |
| misleading_accuracy | same pattern | one `below_threshold misleading_accuracy` | same |
| each metric, controls | one control at exactly the threshold, the rest at threshold − 0.0001 | one `too_lenient <metric>` naming the control | control at threshold − 0.0001, so none |

Further gate tests:
- `test_below_baseline` (0.9000 vs 0.9500 fails; equal passes);
- `test_missing_baseline_entry_fails_closed`;
- `test_dataset_mismatch`;
- `test_classifier_required_after_block` (fails with B4 in `finished_blocks` and a null classifier; passes when B4 is absent);
- `test_all_failures_reported`: three simultaneous failures are all listed.

**`tests/test_eval_cli.py`** (end to end on fixture files, real metric computation):
- `test_controls_only_passes` (the pre-B4 state): with a classifier-free config on the standard fixture, rc is 0, the output says `controls only` and `eval passed`.
- Data-level failing fixture per metric. Each runs `scripted` as the classifier with thresholds at the proposal, asserts rc 1 and the named failure; the passing twin uses `oracle` and gives rc 0:
  - `fx_accuracy_low`: 10 wrong spread over 5 labels on prefixed and plain rows gives accuracy 0.8333, so `below_threshold accuracy`; macro-F1 may fail too, and the test asserts accuracy is present.
  - `fx_macro_f1_low`: 6 `feat` rows predicted as `chore` and 4 `docs` rows as `chore` gives macro-F1 below 0.85, so `below_threshold macro_f1`.
  - `fx_min_recall_low`: 4 of 10 `chore` rows (prefixed) predicted as `fix` give recall 0.6 → `below_threshold min_recall` only (accuracy 0.9333, misleading 1.0).
  - `fx_misleading_low`: 6 of 18 misleading rows wrong, one per label, give 0.6667, so `below_threshold misleading_accuracy` only (accuracy 0.90, recall 0.90).
- `fx_keyword_friendly` (controls too lenient): every message contains only its own label's keyword. keyword_spam scores 1.0, so there are four `too_lenient` failures naming keyword_spam, and rc 1.
- `fx_lenient_thresholds`: all thresholds are 0.10. Majority's accuracy and misleading accuracy (both 0.1667) are reported as too lenient; rc 1.
- `test_missing_dataset_exit_3` (error path): stderr contains `dataset not found` and `generate_dataset.py`.
- `test_missing_config_exit_3`, `test_invalid_json_exit_3`, `test_unknown_config_key_exit_3`, `test_missing_control_in_config_exit_3`, `test_schema_violation_exit_3_names_line`, `test_no_misleading_rows_exit_3`, `test_label_without_support_exit_3`.
- `test_invalid_prediction_exit_3` and `test_predict_raises_exit_3`, each naming the strategy and record id.
- `test_show_errors_requires_dev` (rc 2); `test_write_baseline_with_dev_is_usage_error` (rc 2).
- `test_dev_split_is_informational`: the dev run prints the `informational` header and gives rc 0 even when the controls would fail the gate.
- `test_write_baseline_first_time_and_block`: writes the canonical baseline; `--block B3` appends to `finished_blocks` idempotently.
- `test_write_baseline_refuses_on_failure`: with a `too_lenient` case, rc 1 and both files are unchanged.
- `test_write_baseline_regression_needs_reason`: refused without `--reason`; with it, the reason is appended to `notes`.
- `test_json_output_shape`: the keys above, canonical, with `ok` false exactly when rc is 1.
- `test_module_entry_eval_subprocess`: `python -m commit_kind eval --config <tmp>` gives rc 0.
- `test_eval_modules_stdlib_only`: an AST import check of `evaluate.py` and `strategies.py`; no `socket`, `urllib` or `http`.

**`tests/test_eval_step.py`** (static, no live data):
- `test_eval_step_wired_between_markers`: exactly one uncommented line `run_step eval "$PY" -m commit_kind eval` sits between the two markers, after `run_step pytest` and before `finish`.
- `test_tests_do_not_read_live_eval_files`: no `tests/test_eval*.py`, `tests/test_metrics.py` or `tests/test_strategies.py` contains `data/commits.jsonl`, `evals/config.json` or `evals/baseline.json`.

## 5. Acceptance criteria (checkable by a machine or in five clicks)

Criteria 1–5 and 7 run on `loop/B3` after step 4, when it contains `main` with B2.

1. `./scripts/check.sh; echo $?` shows `PASS ruff-check`, `PASS ruff-format`, `PASS mypy`, `PASS pytest`, `PASS eval`, `check passed`, `0`.
2. `PYTHONPATH=src python3 -m commit_kind eval` prints the table with `classifier: none configured (controls only)` and `eval passed`, rc 0. Expected values:
   - majority: 0.1667 / 0.0476 / 0.0000 / 0.1667;
   - keyword_spam: accuracy ≤ 0.6667, macro-F1 ≤ 0.8000, min recall ≤ 0.6667, misleading 0.0000;
   - random: all well below thresholds.
3. `PYTHONPATH=src python3 -m commit_kind eval --json | python3 -m json.tool` succeeds; `"ok": true`; every value has ≤ 4 decimals.
4. Too-lenient negative control (manual, not committed): `cp evals/config.json evals/_tmp_lenient.json`, set all thresholds to 0.10 in the copy, then `PYTHONPATH=src python3 -m commit_kind eval --config evals/_tmp_lenient.json; echo $?`. Expected: `metric accuracy too lenient: control majority …`, the same for `misleading_accuracy`, and `1`. Then `rm evals/_tmp_lenient.json`.
5. Missing-data negative control (manual): `mv data/commits.jsonl data/_tmp.jsonl; PYTHONPATH=src python3 -m commit_kind eval; echo $?` prints `dataset not found … generate_dataset.py` on stderr and `3`; `./scripts/check.sh` shows `FAIL eval` and rc 1. Then `mv data/_tmp.jsonl data/commits.jsonl`.
6. Usage and error paths:
   - `… eval --show-errors; echo $?` prints `2`.
   - `… eval --config nope.json; echo $?` prints `3`.
   - `… eval --split dev --show-errors` lists dev records only (every id it prints has split `dev` in the data) and rc 0.
7. `evals/baseline.json`:
   - `written_for_block` is `B3`; `notes` has one entry;
   - its `sha256` equals `shasum -a 256 data/commits.jsonl`;
   - `evals/config.json` `finished_blocks` is `["B1", "B2", "B3"]` and `thresholds_status` is `proposal, approval open`.
8. `git diff main -- scripts/check.sh` (after the merge of `main`) changes exactly one line, between the EVAL markers; both markers are still present.
9. Each hygiene scan prints nothing:
   - `git grep -nE '/(Users|home|private|tmp)/'`
   - `git grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' -- . ':!CLAUDE.md' ':!.planning'`
10. `git log --format='%an <%ae>%n%B' main..loop/B3`: the author is the identity from CLAUDE.md hard rule 6, every message ends with the required `Co-Authored-By` line, and there are no session links.
11. `git diff main...loop/B3 --stat` touches only the files in section 2, plus `.planning/B3/`.

## 6. Eval metrics (name, direction, target as "proposal, approval open", what makes it fail)

| Metric | Direction | Threshold (proposal, approval open) | Fixture that makes it fail | Controls on real data (by B2's construction) |
|---|---|---|---|---|
| `accuracy` | higher is better, pass if `>=` | 0.85 | gate: threshold − 0.0001; data: `fx_accuracy_low` (0.8333) | majority 0.1667, keyword_spam ≤ 0.6667, random ≈ 0.17 |
| `macro_f1` | higher, `>=` | 0.85 | gate: threshold − 0.0001; data: `fx_macro_f1_low` | majority 0.0476, keyword_spam ≤ 0.80, random ≈ 0.17 |
| `min_recall` | higher, `>=` | 0.70 | gate: threshold − 0.0001; data: `fx_min_recall_low` (0.60) | majority 0.0, keyword_spam ≤ 0.6667, random small |
| `misleading_accuracy` | higher, `>=` | 0.70 | gate: threshold − 0.0001; data: `fx_misleading_low` (0.6667) | majority 0.1667, keyword_spam 0.0, random ≈ 0.17 |

How each failure kind is proven to fire:
- `too_lenient`: the gate boundary test, plus `fx_keyword_friendly` and `fx_lenient_thresholds`.
- `below_baseline`: the gate test plus the 246/291 rounding test.
- `missing_baseline`, `dataset_mismatch`, `classifier_required`: gate tests.

Lowest safe thresholds on this data: accuracy > 0.6667, macro-F1 > 0.80, min recall > 0.6667, misleading accuracy above random's measured value. Below these, keyword_spam or random may pass, and the eval reports "too lenient", as designed.

## 7. Risks and rollback

**Risks:**
- **Merge dependency on B2.** B3 cannot finish without B2. Accepted: a gate without data measures nothing. If B2 is reworked after B3's step 4, merge `main` again and re-run `--write-baseline` (the dataset sha changes, so `--reason`).
- **Rounding.** One `q()` used at storage, display and comparison, plus the 246/291 test (pitfall).
- **Tests coupled to live state.** Fixtures only, plus the static test forbidding live paths (pitfall).
- **Fail-open paths.** All are closed:
  - a missing dataset, config or baseline is exit 3;
  - a missing classifier baseline entry is a failure;
  - unknown config keys are exit 3;
  - removing a control from the config is exit 3;
  - `classifier_required` blocks dropping the classifier after B4.
- **The test split leaking into B4 tuning.** Strategies only see messages; `fit`-style data is dev only; `--show-errors` is dev only. The B4 rule test against held-out tokens (from B2) is a hand-off item for B4's plan.
- **Keyword lists in config drift from B2's contract.** The eval on real data is authoritative; drift can only make a control pass, and the eval then fails closed.
- **mypy strict with argparse.** `configure_parser(p: argparse.ArgumentParser)` avoids private `_SubParsersAction` types in B3's signatures. JSON is parsed into typed dataclasses with explicit validation; no `Any` leaks out.
- **Helper module import.** `tests/_evalfixtures.py` relies on the same test-dir import pattern as B1's `tests/_netguard.py` (review fix). If that pattern breaks, inline the helpers into each test file.
- **Thresholds not approved.** Proposal only. B4 must meet whatever is approved; changing them later means editing the config with the human's approval quoted in the gate.

**Rollback:**
- Work is on `loop/B3`; revert per step.
- After merge, `git revert -m 1 <merge>` on `main`. `check.sh` then returns to four steps and B2's data stays valid. Never `--force`.

## 8. Open questions (recommendation first; mark which block a missing answer blocks)

- **Approve the thresholds** accuracy ≥ 0.85, macro-F1 ≥ 0.85, min recall ≥ 0.70, misleading accuracy ≥ 0.70. Recommendation: approve. Blocks B4's merge, not B3.
- **`require_classifier_from_block = "B4"`.** Recommendation: yes; blocks nothing.
- **Merge order B2 → B3**, with B3 pausing before step 4 if needed. Recommendation: yes, decided here; listed under "Decisions I made".

Decisions I made:
- Eval exit codes 0/1/2/3.
- Config paths are relative to the config file.
- The `keyword_spam` tie and zero-hit rule is "first in `LABELS` order".
- The dataset sha is stored in the baseline and a mismatch is a failure.
- `--split dev` and `--show-errors` are added for honest B4 tuning.
- `LABELS` lives in its own module, so B4 does not import eval code.
- B3 adds its README section only after merging `main`.

## Trim (owner decision: demo-sized B3; this section overrides the sections above)

- Removed: `require_classifier_from_block` / `classifier_required`, dataset sha256 and `dataset_mismatch`, `--reason` and baseline `notes`, `thresholds_status`, `--show-errors` JSON output, `StrategyFactory`, the AST stdlib test, per-key config validation beyond: required keys, thresholds in [0,1], all three controls listed, classifier not a control and in the registry.
- Config keys: `baseline`, `classifier`, `controls`, `dataset`, `finished_blocks`, `keyword_spam`, `random_seed`, `thresholds` (plain JSON, canonical on write). Baseline: `{"strategies": {name: 4 metrics}, "written_for_block": "B<n>"}`.
- Gate failures (strings): `too lenient: <metric> ...`, `classifier <n> below threshold: <metric> ...`, `classifier <n> below baseline: <metric> ...`, `classifier <n> has no baseline entry` (skipped during `--write-baseline`). `tests/test_eval_step.py` in step 4 only needs the wiring check.
- CLI: `eval [--config PATH] [--json] [--split {test,dev}] [--show-errors] [--write-baseline --block B<n>]`. `--show-errors` only with `--split dev`, text only. `--split dev` is informational: no gate, no baseline.
- Exit codes: 0 pass; 1 gate failed or baseline write refused (nothing written); 2 usage; 3 missing or invalid config, dataset (prints the generate command) or baseline, bad strategy output.
- B4 registers its classifier with one `REGISTRY["rules"] = lambda ctx: ...` entry (plain callable) and sets `"classifier": "rules"`.
- Tests: `tests/_evalfixtures.py` and `tests/test_eval.py` replace the five earlier B3 test files.
