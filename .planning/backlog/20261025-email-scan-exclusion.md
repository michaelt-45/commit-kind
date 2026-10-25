---
id: 20261025-email-scan-exclusion
source: review:B1
impact: 1
confidence: 0.9
effort: 1
risk: 1
blocking: false
score: 0.9
block: B2
status: open
---
# E-mail hygiene scan always hits CLAUDE.md
**Finding:** The documented noreply identity in CLAUDE.md matches the e-mail pattern, so the scan can never be empty.
**Evidence:** review B1 S-2; CLAUDE.md lines 17-18.
**Proposal:** Plans exclude CLAUDE.md from the scan or allow the two known noreply addresses.
