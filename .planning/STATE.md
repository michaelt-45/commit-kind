# State

Milestone 1, setup done 2026-10-25. B1–B4 merged; B5 next.

## Blocks
- B1 Gate skeleton: merged 2026-10-25 (review: 1 blocker fixed, rework 1), check green, 24 tests
- B2 Synthetic dataset: merged 2026-10-25 (review: 1 blocker, rework 1 removed held-out mechanism, compacted), 32 tests
- B3 Eval harness: merged 2026-10-25 (review merge-ready first pass; trimmed), 61 tests, eval in check.sh
- B4 Classifier: merged 2026-10-25 (review merge-ready; rework 1 added everyday words), 116 tests, eval 1.0
- B5 CLI and docs: waiting for B4

## Decisions
- 2026-10-25: five blocks, B2 ∥ B3 after B1, dataset schema fixed in the roadmap so they can run in parallel.
- 2026-10-25: eval scores the held-out `test` split; the classifier is tuned on `dev` only.
- 2026-10-25: eval thresholds are a proposal (approval open), listed in the B3 gate.
- 2026-10-25: no heavy-run lock; the full check takes seconds, and at most 2 local agents run.
- 2026-10-25: worktrees live in `~/.cache/gated-build-loop/commit-kind/wt/<BLOCK>`; a session restart deleted the
  first one, which sat in the session's temp dir.
- 2026-10-25: owner asked to keep everything only as big as necessary (demo); plans get size budgets.
- 2026-10-25: held-out test vocabulary dropped; first-word leniency accepted for the demo.
- 2026-10-25: eval thresholds 0.85 / 0.85 / 0.70 / 0.70 approved by the owner in chat ("ja passt"); B2 gate answered the same way.
