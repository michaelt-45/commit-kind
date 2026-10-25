# Review gates (newest first)

## B4 — Rule-based classifier (merged 2026-10-25, merge commit "Merge block B4: rule-based classifier")

Full gate: `.planning/B4/REVIEW.md`. Summaries: `.planning/B4/SUMMARY.md`, `SUMMARY-rework1.md`.

**What works now:** `commit_kind.classify("fix: handle empty input")` → `Classification(label='fix',
rule='prefix.fix', evidence='fix:')`. Rules live in one data table (`src/commit_kind/rules.py`): Conventional
prefix, leading verb, ambiguous verb resolved by its object, object word, fallback `chore`. It is the gated
classifier of the eval.

**Proof:** merged tree `./scripts/check.sh` → 5 × PASS, 116 tests. Eval (test split): rules 1.0 on all four
metrics; controls unchanged and failing. The test split was scored once for the build and once as the gate after
rework (no tuning on test).

**Review:** merge-ready. The 1.0 is an artefact of dev and test sharing templates (accepted for the demo; it says
nothing about real repositories). A probe with invented everyday messages found gaps ("Refactor the loader" →
fallback); rework 1 added generic words (refactor, implement, fixes, docs, remove, …), not taken from test data.

**Decisions I made (overrule here):** object conflicts are decided by rule priority (chore > test > docs > fix >
feat) instead of the rightmost word; merged without a second review after a data-only rework that I verified.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"

## B3 — Eval harness with negative controls (merged 2026-10-25, merge commit "Merge block B3: eval harness with negative controls")

Full gate: `.planning/B3/REVIEW.md`. Summaries: `.planning/B3/SUMMARY-steps1-3.md`, `SUMMARY-trim.md`, `SUMMARY-step4.md`.

**What works now:** `python -m commit_kind eval` scores the test split on accuracy, macro-F1, min recall and
misleading accuracy; majority, keyword_spam and random must fail every metric, otherwise "too lenient" and rc 1.
`./scripts/check.sh` runs it as step 5.

**Proof:** merged tree `./scripts/check.sh` → 5 × PASS, 61 tests, eval passed. Reviewer probes on real data: a
lowered threshold → "too lenient"; an oracle classifier below threshold or below baseline → rc 1; stored-precision
comparison; missing inputs → rc 3; a refused baseline write leaves files unchanged.

**Review:** merge-ready on the first pass; four "could" notes, none needed for a demo. Before review the module was
trimmed from about 830 to 261 lines and the tests from about 1,070 to 284 (owner: "only as big as necessary").

**Decisions I made (overrule here):** kept `--split dev --show-errors` as the B4 tuning aid; removed the
classifier-required flag, dataset hash and baseline notes as beyond the roadmap.

**Thresholds:** 0.85 / 0.85 / 0.70 / 0.70, approved by the owner in chat on 2026-10-25 ("ja passt").

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"

## B2 — Synthetic dataset (merged 2026-10-25, merge commit "Merge block B2: synthetic dataset")

Full gate: `.planning/B2/REVIEW.md`. Rework: `.planning/B2/SUMMARY-rework1.md`.

**What works now:** `python3 scripts/generate_dataset.py --out data/commits.jsonl` writes 360 synthetic commit
messages (60 per label; slices prefixed / plain / misleading; exactly 50/50 dev/test), byte-identical on every run.
The committed file equals a fresh generation (tested).

**Proof:** merged tree `./scripts/check.sh` → 4 × PASS, 32 tests. Controls on the test split: keyword_spam
0.54 / 0.55 / 0.40 / 0.00, majority 0.17 / 0.05 / 0.00 / 0.17, random 0.17 / 0.18 / 0.07 / 0.15 (accuracy,
macro-F1, min recall, misleading accuracy) — all below the proposed thresholds.

**Review:** first verdict "not merge-ready": the held-out vocabulary meant to keep B4 honest did not hold
(B-1), plus mislabelled decoys. Rework 1 removed the mechanism, fixed the labels and shrank generator and tests
from about 1,670 to 448 lines (owner: "only as big as necessary, just a demo").

**Decisions I made (overrule here):**
- Dropped the held-out mechanism instead of repairing it; honesty in B4 is a process rule (tune on dev only).
- Accepted the reviewer's leniency probe: a dev-fitted first-word lookup would pass the thresholds. For a demo
  the dataset stays easy; the three required controls fail by a wide margin.
- Merged after rework 1 without a second review agent; I re-ran the check and read a sample of messages.

**Open questions:** eval thresholds 0.85 / 0.85 / 0.70 / 0.70 — approval needed before B4 merges.

**Owner's answer (chat, 2026-10-25):** "ja passt" — thresholds approved, gate ok.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"

## B1 — Gate skeleton (merged 2026-10-25, merge commit on `main`: "Merge block B1: gate skeleton")

Full gate: `.planning/B1/REVIEW.md`. Rework: `.planning/B1/SUMMARY-rework1.md`.

**What works now:** `./scripts/check.sh` runs ruff, ruff format, mypy --strict and pytest, prints PASS/FAIL per
step and exits non-zero if any step fails (proven by a self-test mode and by injected ruff, mypy, format and test
failures). `python -m commit_kind --version` works. Tests cannot open sockets or resolve names, for the whole
session.

**Proof:** on the merged tree `./scripts/check.sh` → 4 × PASS, 24 tests passed, exit 0.

**Review:** first verdict "not merge-ready" for one blocker (the build summary quoted a temp path and claimed the
path scan was empty); fixed by the orchestrator in the summary text. Should S-1 (guard session-wide plus DNS) and
Could C-1, C-2, C-3, C-5 fixed in rework round 1. S-2, S-3 and the builder's proposals filed in
`.planning/backlog/`.

**Decisions I made (overrule here):**
- Merged after rework 1 without a second review agent: the rework touched test infrastructure only; I read the
  diff and ran the check on the merged tree. Alternative: second opus review.
- The check runs every step and reports all failures, instead of stopping at the first.
- No heavy-run lock: the full check takes about one second.
- Worktrees live outside the repo and outside the session's temp dir after a restart deleted the first one.

**Open questions:** none.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"
