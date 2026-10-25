---
id: 20261025-revert-by-header
source: review:B4
impact: 1
confidence: 0.8
effort: 1
risk: 1
blocking: false
score: 0.8
block: later
status: open
---
# Classify revert commits by the reverted header
**Finding:** revert: and Revert "…" always give chore (prefix map or fallback).
**Evidence:** `.planning/B4/REVIEW.md` (S2) and the backlog list in `.planning/B4/PLAN.md`.
**Proposal:** Classify the quoted header instead; small change in classifier.py plus test rows.
