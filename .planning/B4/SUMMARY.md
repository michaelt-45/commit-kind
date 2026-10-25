# B4 — Summary

## Status
Done. Date 2026-10-25, branch `loop/B4`. B4 commits are `94b6312` and `d4af4a9`, on top of the plan commit `17c6603`. Nothing was pushed or merged.

## Done
- Added `src/commit_kind/rules.py`: a frozen `Rule` dataclass, the ordered `RULES` table and `BOUNDARY_WORDS`.
- Added `src/commit_kind/classifier.py`. It exposes `classify`, `Classification` and `EmptyMessageError` and is pure standard library.
  - The engine takes the first non-blank line, then checks the prefix. A known type decides; an unknown type is stripped and the rest classified.
  - Next come verbs, then the ambiguous-verb object scan up to the first boundary word, then the object-only scan, then the `chore` fallback.
- `__init__.py` exports the three names.
- `strategies.py` registers `REGISTRY["rules"]` as a plain callable taking the context.
- Added `tests/test_classifier.py`, with one row per rule id, ordering and edge cases, empty and long input, and the registry entry.
- Set `evals/config.json` to `"classifier": "rules"` and appended `B4` to `finished_blocks`. The only other change is the formatting `--write-baseline` writes. `evals/baseline.json` now has a `rules` entry and `written_for_block` B4, written with `--write-baseline --block B4`.

## Deviations from the plan
- **Object scan order.** Among the object rules hit in the phrase before the first boundary word, rule order decides (chore, test, docs, fix, feat). It is not the rightmost token. For example, "Update the lint settings for the package" gives `chore`, not `feat`. The plan's ordering tests pass either way.
- **Evidence.** When an object decides, the evidence runs from the verb (or the start of the text) through the last hit of the winning rule.
- **Commits.** Steps 1 and 2 are one commit, because the tests import the registry entry. Step 3 is its own commit. The orchestrator-note step 4 verification was done inline.
- **No `--reason`.** The B3 trim removed it.
- **Dev tuning.** Three rule-data additions, with test rows: `mock` and `assert` under `verb.test`, and `correct` under `verb.docs`.

## Checks
- `./scripts/check.sh`: 5 PASS (ruff-check, ruff-format, mypy, pytest, eval) and `check passed`. 108 tests pass.
- `wc -l`: `rules.py` 115, `classifier.py` 72 (187 together), `tests/test_classifier.py` 110.
- Dev (informational, scratch config):
  - Before tuning: accuracy 0.9611, macro_f1 0.9612, min_recall 0.8000, misleading_accuracy 0.9500.
  - After tuning: 1.0000 on all four metrics.

Single test-split eval from `--write-baseline --block B4`; thresholds are 0.85 / 0.85 / 0.70 / 0.70:

| strategy | accuracy | macro_f1 | min_recall | misleading_accuracy |
|---|---|---|---|---|
| majority | 0.1667 fail | 0.0476 fail | 0.0000 fail | 0.1667 fail |
| keyword_spam | 0.5389 fail | 0.5454 fail | 0.4000 fail | 0.0000 fail |
| random | 0.1667 fail | 0.1671 fail | 0.1333 fail | 0.1333 fail |
| rules | 1.0000 pass | 1.0000 pass | 1.0000 pass | 1.0000 pass |

Output was `eval passed` and `baseline written for B4`, rc 0.

- Test-split runs: 1.
- Remaining dev errors: none. Before tuning, the 7 errors were all expected `test` or `docs` but got `chore`:
  - Six had an unlisted verb, `Mock` or `Assert`, and fell to the fallback.
  - One had an unlisted verb, `Correct`, so "spelling ... comments" fell to the fallback.
- By hand:
  - `classify("fix: handle empty input")` printed `Classification(label='fix', rule='prefix.fix', evidence='fix:')`, rc 0.
  - `classify("   ")` raised `EmptyMessageError: empty commit message`, rc 1.
- Hygiene: scanning `git log -p main..` for local paths and e-mail addresses printed nothing relevant. The only hits were `@pytest` decorators.
- Cleanup: the scratch config directory was removed. The worktree is clean. Scratch config and its dataset path were never committed.

## Files changed
- `src/commit_kind/rules.py` (new)
- `src/commit_kind/classifier.py` (new)
- `src/commit_kind/__init__.py`
- `src/commit_kind/strategies.py`
- `tests/test_classifier.py` (new)
- `evals/config.json`
- `evals/baseline.json`
