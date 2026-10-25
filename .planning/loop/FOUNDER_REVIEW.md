# Review gates (newest first)

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
