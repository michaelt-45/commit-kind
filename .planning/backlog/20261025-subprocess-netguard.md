---
id: 20261025-subprocess-netguard
source: review:B1
impact: 2
confidence: 0.8
effort: 2
risk: 2
blocking: false
score: 1.6
block: B5
status: done
---
# Network guard does not cover child processes
**Finding:** The in-process socket patch does not reach subprocesses started by tests (CLI end-to-end tests in B5).
**Evidence:** tests/_netguard.py patches the socket module of the pytest process only.
**Proposal:** Put a sitecustomize-style guard on PYTHONPATH for subprocess tests; take it in B5.
