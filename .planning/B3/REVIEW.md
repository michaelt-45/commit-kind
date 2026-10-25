# B3 — Review gate
Status: 2026-10-25, branch `loop/B3`, 15 commits (`8f2b680..771f3ca`, including the merge of main `c6f91ff`). Not merged, not pushed. The worktree was clean after the review. The probes ran on temp copies of the config and baseline outside the repo, and those copies have been deleted. **Verdict: merge-ready yes.** There are no blockers and nothing at "should" level. Four small "could" items are listed below, and none of them is needed for a demo.

## In one paragraph: what works now that did not before
`python -m commit_kind eval [--json]` scores the test split on four metrics: accuracy, macro-F1, min recall and misleading-slice accuracy. Values are rounded to 4 digits through a single `q()`. It runs the three negative controls (majority, keyword_spam, random), which are fitted on dev only. It fails with rc 1 in three cases: a control reaches any threshold ("too lenient: <metric>"), the classifier is below a threshold, or the classifier is below its baseline. It fails closed with rc 3 when the config, dataset or baseline is missing or invalid. `check.sh` now runs it as its fifth step. `evals/config.json` and `evals/baseline.json` exist, and `finished_blocks` is `["B3"]`. Until B4 the classifier slot is `null`, so only the controls are scored, and the eval exits 0 because all of them fail.

## Proof
- `./scripts/check.sh`: ruff-check, ruff-format, mypy --strict (16 files), pytest (61 passed) and eval all PASS. Output ends with `check passed`, rc 0.
- `eval --json`: `ok: true`, `failures: []`. Every control fails all four metrics (thresholds 0.85 / 0.85 / 0.70 / 0.70):

| strategy | accuracy | macro_f1 | min_recall | misleading_acc |
|---|---|---|---|---|
| majority | 0.1667 | 0.0476 | 0.0000 | 0.1667 |
| keyword_spam | 0.5389 | 0.5454 | 0.4000 | 0.0000 |
| random | 0.1667 | 0.1671 | 0.1333 | 0.1333 |

  These match `evals/baseline.json` and SUMMARY-step4. Before B3 there was no eval, so there is nothing to compare against.
- Manual gate probes, all on the real data:
  - (a) Accuracy threshold lowered to 0.5: rc 1, `too lenient: accuracy (control keyword_spam reaches 0.5389 >= 0.5)`.
  - (b) `"classifier": "keyword_spam"`: rc 3 ("not a known non-control strategy").
  - (b) In-process oracle with 29 of 180 predictions wrong: rc 1, `classifier oracle below threshold: accuracy 0.8389 < 0.85`.
  - (b) Oracle with no baseline entry: rc 1, `has no baseline entry`.
  - (c) Oracle with 1 prediction wrong against a perfect baseline: rc 1, `below baseline` on all four metrics.
  - (d) The raw accuracy is 151/180 = 0.83889, stored as 0.8389. Re-running against that stored baseline gives rc 0. A baseline of 0.8390 gives rc 1. So the comparison happens at stored precision, as the 246/291 test also shows (`test_gate_baseline_and_rounding_246_of_291`).
  - (e) Missing baseline: rc 3. Missing dataset: rc 3 and the generate command is printed. Missing config: rc 3.
  - (f) `--write-baseline --block B9` on the lenient config: rc 1, both files are byte-identical afterwards, and no `.tmp` file is left behind.
- By hand (DoD 4): the golden path gives rc 0. `--config does-not-exist.json` gives rc 3. `--block` without `--write-baseline` gives rc 2. `--split dev --show-errors` prints "informational" and exits 0.
- Correctness review:
  - Macro-F1 averages over all 6 labels. A class that is never predicted gets precision 0 and F1 0, with no division by zero. A class with no support raises InputError (rc 3). Hand-checked against `test_metrics_hand_computed`.
  - min_recall is the minimum per-class recall.
  - Dev is never gated: the `--split dev` path returns 0 before any baseline or gate check.
  - `StrategyContext` carries dev messages and labels only. Majority uses dev counts, and ties go to the first label in label order.
  - keyword_spam tokenises with `[a-z0-9]+` on lowercased text and counts repeated hits, the same as `hits()` in `scripts/generate_dataset.py`. Ties and zero hits go to the first label. The keyword lists equal `CONTROL_KEYWORDS`, enforced by `test_generator_keywords_match_eval_config`.
  - Because of the generator's "misleading" invariant (another class always has strictly more hits), keyword_spam's 0.0 on the misleading slice is by construction.
  - random uses a fresh `random.Random(seed)` per run, so results are deterministic.
  - Writes go to a temp file and then `os.replace`.
  - Exit codes are 0, 1, 2 and 3, as in the Trim note.
- Tests: all eval tests build their inputs on `tmp_path`. The only test that reads live files is the keyword contract test, which is allowed. Each of the four metrics has a fixture where it fails end to end (`test_classifier_failing_each_metric`) and a passing twin (`test_gate_boundary_per_metric`, `test_controls_only_and_classifier_pass`).
- Summary claims checked: the commit list, the eval numbers, "config not found" with rc 3, the README lines and `evaluate.py` at 261 lines all match.

## Findings
**Blockers:** none.
**Should:** none.
**Could:**
1. `src/commit_kind/evaluate.py:66,126`: a config with a wrong type, for example `"controls": 5` or a non-dict `keyword_spam`, ends in a traceback with rc 1 instead of rc 3. It is still non-zero and never a silent pass, and the Trim note deliberately limits validation. No action needed.
2. `src/commit_kind/evaluate.py:258-259`: the baseline and the config are written as two separate atomic writes, so a crash between them would leave the two files out of step. `--write-baseline --json` also appends a text line after the JSON. Both are harmless for a demo.
3. `src/commit_kind/evaluate.py:130`: the `controls` config key is checked but never used, because scoring always runs `CONTROL_NAMES`. It is decorative and could be dropped later.
4. Scope: `--split dev` and `--show-errors` go beyond the roadmap's B3 criteria. The owner kept them in the Trim note as the B4 tuning aid, so this is noted only, with no action. `tests/test_eval.py:219` uses a relative `PYTHONPATH=src`, so it only works when pytest runs from the repo root, which is how `check.sh` runs it.

## Hard rules: result per rule
1. Secrets: none in the diff or the log. ✓
2. Personal data and paths: `git grep` finds no `/Users/`, `/home/`, `/var/folders` or e-mail addresses in B3's diff. The older `~/.cache/...` mentions in STATE and HANDOFF were already accepted in B2. Nothing mentions another project. ✓
3. Network: the conftest socket guard is unchanged and the eval tests do no I/O beyond `tmp_path`. ✓
4. Negative controls: all three fail every gated metric, the "too lenient" exit is proven by probe (a) and by the tests, and rc 1 propagates through `check.sh`. ✓
5. Backlog: nothing out of scope was found in the code. ✓
6. Commits: all 15 are authored and committed by `michaelt-45 <202262075+michaelt-45@users.noreply.github.com>`. Each message ends with exactly one `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. There are no URLs or session links, and `git log -p` contains no e-mail addresses or local paths. ✓
- The README records the owner's approval of the thresholds on 2026-10-25. ✓

## Decisions I made
- I proved the classifier-side gate with an oracle registered in-process, because the config path cannot register a non-control strategy before B4. The alternative was a fixture-only proof, which the tests already provide.
- I treated the CLI flags that the Trim note kept as owner-approved, not as blocking scope creep.

## What you should check yourself
1. https://github.com/michaelt-45/commit-kind/blob/main/evals/config.json: thresholds 0.85 / 0.85 / 0.7 / 0.7, `"classifier": null` and `finished_blocks` `["B3"]`.
2. https://github.com/michaelt-45/commit-kind/blob/main/evals/baseline.json: the three controls with the numbers in the table above.
3. https://github.com/michaelt-45/commit-kind/blob/main/src/commit_kind/evaluate.py: the function `gate`, which holds the three failure rules in about 30 lines.
4. https://github.com/michaelt-45/commit-kind/blob/main/scripts/check.sh: the `run_step eval` line between the EVAL STEP markers.
5. `git clone https://github.com/michaelt-45/commit-kind && cd commit-kind && PYTHONPATH=src python3 -m commit_kind eval; echo $?` should print the table, `eval passed` and `0`.

## What you should do yourself
Nothing. The thresholds are already approved.

## Open questions, recommendation first
None that change B4. B4 registers `REGISTRY["rules"]`, sets `"classifier": "rules"` and runs `--write-baseline --block B4`.

## Risks, rollback
Low risk: the change is additive (one new module, config files and one `check.sh` line). To roll back, revert the B3 merge commit on main.

## Backlog: created / closed
None created, none closed.
