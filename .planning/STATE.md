# State

Milestone 1, setup done 2026-10-25. B1 merged; B2 and B3 being planned.

## Blocks
- B1 Gate skeleton: merged 2026-10-25 (review: 1 blocker fixed, rework 1), check green, 24 tests
- B2 Synthetic dataset: waiting for B1
- B3 Eval harness: waiting for B1
- B4 Classifier: waiting for B2, B3
- B5 CLI and docs: waiting for B4

## Decisions
- 2026-10-25: five blocks, B2 ∥ B3 after B1, dataset schema fixed in the roadmap so they can run in parallel.
- 2026-10-25: eval scores the held-out `test` split; the classifier is tuned on `dev` only.
- 2026-10-25: eval thresholds are a proposal (approval open), listed in the B3 gate.
- 2026-10-25: no heavy-run lock; the full check takes seconds, and at most 2 local agents run.
- 2026-10-25: worktrees live in `~/.cache/gated-build-loop/commit-kind/wt/<BLOCK>`; a session restart deleted the
  first one, which sat in the session's temp dir.
