# Review gates (newest first)

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
