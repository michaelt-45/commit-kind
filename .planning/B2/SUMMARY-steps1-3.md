# B2 — Summary (steps 1–3)

## Status
- Date: 2026-10-25. Branch `loop/B2`. Steps 1–3 are done.
- Commits `2b7c32c..359c68f`, six commits on top of the plan commit. All end with the required `Co-Authored-By` trailer and nothing else:
  - `1b10201` generator
  - `6bad673` dataset
  - `ad0d7a0` check.sh targets
  - `5c42f8b` tests
  - `0a18c36` conftest docstring plus the two backlog entries marked done
  - `359c68f` README
- Working tree clean. Nothing pushed or merged. Step 4 (audit) and step 5 are not done.

## Done
- **Step 1:** `scripts/generate_dataset.py`, standard library only.
  - It follows the plan's recipe: `randrange`-only RNG with a hand-written Fisher–Yates shuffle, tuple pools, and rerolls capped at 1000 attempts.
  - Module constants are `LABELS`, `SLICES`, `PER_LABEL`, `SLICE_COUNTS`, `CONTROL_KEYWORDS` and `HELDOUT`. Functions are `generate`, `serialise` and `main`.
  - The self-checks are per-message (slice invariants, hygiene, line length ≤72, unique summary) and global (counts, balance, held-out token leaks).
  - The keyword lists are exactly the plan's contract, and the generator checks they are pairwise disjoint.
  - Misleading messages use 5 decoy tails per decoy label plus 30 hand-written "special" summaries.
  - Decoys are chosen cyclically so each of the 5 other labels appears 4 times per true label.
  - Held-out vocabulary: 4 entries per label (3 secondary, 1 primary), 24 test records in total.
- **Step 2:** `data/commits.jsonl` committed. Two test files added (`tests/test_dataset.py`, `tests/test_generate_dataset.py`) covering every test named in section 4 of the plan, plus a few extras:
  - a default-seed test
  - a success-message test
  - an unwritable-`--out` error path
  - a module-constants test
  - an in-process `main()` test
  - a breaking-footer-needs-`!` test
  - a recomputed keyword_spam control
  - a distinct-decoys test
- **Step 3:** ` scripts` appended to exactly the three `run_step` lines in `scripts/check.sh`. README gets a `## Dataset` section of 8 lines.
- **Backlog:** the `tests/conftest.py` fixture docstring now reads "assert the guard is still installed before each test". `20261025-netguard-docstring` and `20261025-scripts-lint-targets` are marked `status: done`.

## Deviations from the plan
1. **Order of commits.** The plan's `test_check_sh_lints_scripts` is part of step 2 but needs the step-3 `check.sh` edit. I committed the `check.sh` edit between the data and the tests so every commit is green. The README part of step 3 came last.
2. **Refactor primary probe.** The plan's primary probe is "ambiguous verb + held-out artefact noun", but refactor has no ambiguous verbs. I used a held-out verb plus noun instead: "Untangle the callback chain in the {mod}". The held-out tokens are `untangle callback`.
3. **Uniqueness key.** It is stricter than the plan: the summary after stripping any Conventional prefix, case-folded and whitespace-collapsed. A prefixed record therefore cannot repeat a plain summary. `test_summaries_unique` checks both the full line and the stripped form.
4. **Misleading tails.** If lead plus tail would exceed 72 characters, the tail moves to a body sentence "Done <tail>." instead of the summary line.
5. **Hygiene scan 8 is not empty.** `git grep -nE '/(Users|home|private|tmp)/'` matches only the forbidden-pattern literals `/home/` in `scripts/generate_dataset.py` and `tests/test_dataset.py`. The `.planning/B2/PLAN.md` matches are the plan's own text. There are no real paths.
6. **Generator file length.** `ruff format` explodes the tuples, so the generator is about 1180 lines. That is harmless.

## Checks
- `./scripts/check.sh`: all steps PASS, `check passed`, exit 0.
  - ruff-check, ruff-format and mypy `--strict src tests scripts` are clean (12 files).
  - pytest: 55 passed.
- `grep -c 'src tests scripts' scripts/check.sh` prints 3.
- `wc -l data/commits.jsonl` prints 360.
- Counts:
  - per label: feat 60, fix 60, docs 60, refactor 60, test 60, chore 60
  - per slice: prefixed 132, plain 108, misleading 120
  - per split: dev 180, test 180
  - per (label, slice, split): exactly 11/9/10 for each of dev and test (checked by the tests)
- Determinism: `cmp` of a run with the default hash seed against a run with `PYTHONHASHSEED=1` is silent, and both equal the committed file (`same`). Regenerating with `--seed 20261025 --out data/commits.jsonl` leaves `git diff --exit-code` clean.
- `grep -cE '@|https?://|www\.' data/commits.jsonl` prints 0.
- Test-split controls (checked in `tests/test_dataset.py`):
  - keyword_spam gets 0 of 60 misleading rows right.
  - Its per-label recall is at most 0.6667, as is its accuracy.
  - All 360 misleading and plain rows satisfy their invariants.
  - Any single label scores 30/180 on test.
- I did not do the isolated audit (step 4 task). I only read the first 40 records.

## Backlog (proposals)
- B4 may add a test that `CONTROL_KEYWORDS` equals the lists in `evals/config.json`.
- Prefixed summaries mix capitalisation after the colon, for example "fix: Restore ...". It is realistic but could be made uniform.
- The step-4 auditor should check how plausible the decoy tails read. A few misleading messages are slightly odd, for example "Added a limit hook for the chore that handles the CI deps".

## Open / risks
- Step 4 must confirm the ambiguity count (at most 3 of 60 sampled) and that the leading phrase is unambiguous, especially for the 6 primary probes.
- The held-out tokens are listed in `HELDOUT` in the generator. B4's mechanical check (no rule contains a test-only token) should be computed from `data/commits.jsonl`.

## Files changed
- `scripts/generate_dataset.py` (new)
- `data/commits.jsonl` (new)
- `tests/test_dataset.py` (new)
- `tests/test_generate_dataset.py` (new)
- `scripts/check.sh` (3 lines)
- `README.md` (+11 lines)
- `tests/conftest.py` (docstring only)
- `.planning/backlog/20261025-netguard-docstring.md` (status)
- `.planning/backlog/20261025-scripts-lint-targets.md` (status)
