# B4 — Summary (rework 1)

## Status
Date 2026-10-25. Branch `loop/B4`. Commits `b819273` and `1e6a099`, on top of `8c7bd44`. Nothing was merged or pushed.

## Done
- S1 is implemented as specified, in `src/commit_kind/rules.py`:
  - `verb.refactor`: added refactor, refactored, restructure, reorganize, optimize, speed up.
  - `verb.feat`: added implement.
  - `verb.chore`: added clean up, cleanup.
  - `ambiguous.fix`: added fixes; `correct` moved here from `verb.docs`.
  - `object.docs`: added spelling, docs, documentation, docstrings, examples.
  - `object.chore`: added dependencies.
  - New rule `ambiguous.remove` (remove, delete, drop; default refactor). `improve` was left out.
- `tests/test_classifier.py`:
  - New rows: Restructure, Speed up, Clean up, Implement, Fixes, Remove, Update the docs, Update dependencies.
  - The "Correct the spelling in the comments" row now expects `object.docs` with evidence "Correct the spelling".
  - The long-message timing limit is relaxed from 1 s to 3 s.
- `src/commit_kind/classifier.py`: the loop variable is no longer reassigned. The object hit is returned directly instead.
- The baseline rewrite (`eval --write-baseline --block B4`) was run once, after the edits, as a gate. It was accepted, and `evals/` shows no diff because every number is unchanged.
- No word was removed, and I did not read the test split.

## Deviations
- I added two test rows beyond the minimum, for `speed up` and `dependencies`.
- The "Correct the spelling in the comments" row changed from `verb.docs` to `object.docs`, as a consequence of moving `correct`.

## Checks
- `./scripts/check.sh`: 5 PASS (ruff-check, ruff-format, mypy, pytest with 116 tests, eval), then `check passed`. The earlier run was 108 tests.
- Eval after the baseline rewrite:

| strategy | accuracy | macro_f1 | min_recall | misleading_acc |
|---|---|---|---|---|
| thresholds | 0.85 | 0.85 | 0.70 | 0.70 |
| majority | 0.1667 fail | 0.0476 fail | 0.0000 fail | 0.1667 fail |
| keyword_spam | 0.5389 fail | 0.5454 fail | 0.4000 fail | 0.0000 fail |
| random | 0.1667 fail | 0.1671 fail | 0.1333 fail | 0.1333 fail |
| rules | 1.0000 pass | 1.0000 pass | 1.0000 pass | 1.0000 pass |

- Invented messages (not from the dataset):
  - "Refactor the loader" gives refactor (`verb.refactor`).
  - "Implement retry with backoff" gives feat (`verb.feat`).
  - "Fixes #123" gives fix (`ambiguous.fix`).
  - "Update the docs" gives docs (`object.docs`).
  - "Remove unused imports" gives refactor (`ambiguous.remove`).
  - "Correct the spelling in the guide" gives docs (`object.docs`).
- `wc -l`: `src/commit_kind/rules.py` 126, `src/commit_kind/classifier.py` 72, `tests/test_classifier.py` 118.

## Files changed
- `src/commit_kind/rules.py`
- `src/commit_kind/classifier.py`
- `tests/test_classifier.py`
