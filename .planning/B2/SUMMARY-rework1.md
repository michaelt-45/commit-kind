# B2 — Summary (rework 1)

## Status
Date 2026-10-25, branch `loop/B2`, commits `516943e..6512e04` (2 commits: `b6d840b` generator, tests and data; `6512e04` plan note). Not merged, not pushed. Worktree is clean. Both commits are authored by `michaelt-45` with the noreply address and end with exactly one trailer.

## Done per finding
- **B-1:** `HELDOUT`, the primary/secondary probes, the held-out tests and the test-only token machinery are removed. Dev templates are now taken round-robin from a seeded shuffle, one cycle per (label, pool), shared by prefixed and plain. `test_every_template_appears_in_dev` checks that every template matches at least one dev record.
- **S-1:** The decoy tails are now context:
  - "after the issue and regression reports"
  - "after the shared code was moved and renamed"
  - "for the CI deps job"
  - "after the bug/crash/refactor/docs ..." variants
  The chore/docs special is now "Pin the docs theme to {v} for the README and changelog" (docs 3 hits, chore 0).
- **S-3:** `test_keyword_spam_fails_on_test_split` uses `max(gen.LABELS, key=counts)`, the B3 tie rule.
- **C-1:** A regex fixes "a" to "an" before a vowel. No "a <vowel>" remains in the data.
- **C-3:** `!` and `BREAKING CHANGE` appear only on feat, fix and refactor. A test asserts this.
- **C-2:** The "Done <tail>." body lines are gone. Bodies now come from one neutral pool of 6 sentences with no keywords.
- **S-5:** Not applicable; the primary probes are gone.
- **Kept:**
  - Stdlib only; one `Random` using only `randrange`; own Fisher–Yates.
  - `--seed` default 20261025, `--out` required, exit codes 0/1/2.
  - Counts 360 / 60 per label / slices 22/18/20 / exact 50/50 per (label, slice).
  - Global shuffle, then ids; byte-identical serialisation with atomic write.
  - `CONTROL_KEYWORDS` with the plan's lists. They are stored as `label: list`, built from space-separated strings, which keeps ruff's SIM905 rule quiet.
  - `tests/conftest.py` and `scripts` in `check.sh` are unchanged.
- **Plan:** Appended a "Rework 1" section (8 lines, a bit over the 3–5 requested) to `.planning/B2/PLAN.md`. It covers the removed held-out mechanism, the compact generator, template coverage in dev, the S/C fixes and the accepted first-word leniency.

## Deviations
- The generator is 327 lines after `ruff format`, a little over the ~300 budget. About 125 of those lines are template and pool data.
- Seven misleading templates dropped the `{m}` slot to stay within 72 characters; they still have plenty of fill variety.
- Plain/prefixed templates went from about 8 to 7 per label (past-tense "Added" and "Fixed" kept).
- The prefixed uniqueness key is the summary text without the prefix, which is stricter than the plan.
- Per review S-4, `tests/conftest.py` and the backlog edits from the first round stay as they were.
- The test file contains the forbidden-pattern literal `/Users/` (in a regex, as in round 1); it is not a real path.

## Checks
- `./scripts/check.sh`: ruff-check PASS; ruff-format PASS (11 files); mypy --strict PASS (11 files); pytest PASS, 32 passed; "check passed".
- `wc -l`: `scripts/generate_dataset.py` 327, `tests/test_dataset.py` 121. The old `tests/test_generate_dataset.py` (263 lines) is deleted.
- Counts: 360 records, 60 per label, 22/18/20 per slice, 30 dev and 30 test per label. All 18 (label, slice) cells are exactly 50/50 (tested).
- Each label has 5 distinct decoy labels in its misleading slice.
- Determinism:
  - Output with `PYTHONHASHSEED` 0, 1 and 2 is identical.
  - The committed file equals a fresh generation (tested for hash seeds 1 and 2).
  - `--out <dir>` exits 1; `--seed abc` exits 2 and creates no file.
- Controls on the test split (n = 180):

| Control | accuracy | macro-F1 | min recall | misleading accuracy |
|---|---|---|---|---|
| keyword_spam (B3 tie rule) | 0.5389 | 0.5454 | 0.4000 | 0.0000 |
| majority (`feat`) | 0.1667 | 0.0476 | 0.0000 | 0.1667 |
| random (seed 20261025) | 0.1667 | 0.1755 | 0.0667 | 0.1500 |

  All fail the proposed thresholds of 0.85 / 0.85 / 0.70 / 0.70.
- Hygiene: the committed data and diff have no `@`, URLs, e-mail addresses or local paths. Temp dirs from `mktemp -d` are removed.

## Files changed
- `scripts/generate_dataset.py` (rewritten)
- `data/commits.jsonl` (regenerated)
- `tests/test_dataset.py` (rewritten)
- `tests/test_generate_dataset.py` (deleted)
- `.planning/B2/PLAN.md` (Rework 1 note)
