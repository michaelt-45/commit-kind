---
id: 20261025-netguard-docstring
source: review:B1
impact: 1
confidence: 1.0
effort: 1
risk: 0.5
blocking: false
score: 0.5
block: B2
status: open
---
# Autouse fixture docstring says re-apply, the code only asserts
**Finding:** tests/conftest.py _block_network docstring does not match its body.
**Evidence:** tests/conftest.py, fixture _block_network.
**Proposal:** Reword to 'assert the guard is still installed'.
