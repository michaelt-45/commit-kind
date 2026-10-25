---
id: 20261025-scripts-lint-targets
source: review:B1
impact: 1
confidence: 1.0
effort: 1
risk: 2
blocking: false
score: 2.0
block: B2
status: done
---
# check.sh does not lint scripts/
**Finding:** ruff and mypy run on src and tests only; B2 adds scripts/generate_dataset.py.
**Evidence:** scripts/check.sh run_step lines.
**Proposal:** B2 adds scripts to the ruff and mypy targets.
