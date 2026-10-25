# B5 — Review gate
Status: 2026-10-25, branch `loop/B5`, 5 commits (`9127e3a`..`85d3d13`), not merged. **Verdict: merge-ready yes.**

## In one paragraph: what works now that did not before
`commit-kind classify` is new. It prints the label by default. `--json` prints label, rule and evidence. `--explain` prints one line saying why. `-` reads all of stdin as one message, and bad bytes are replaced, so they cause no traceback. An empty message gives exit 1 and a usage error gives exit 2. On every error the message goes to stderr and stdout stays empty. Test child processes now block sockets through `tests/sitecustomize.py`. The README is rewritten with real output and states its limits honestly. Merging B5 with `check.sh` green completes milestone 1.

## Proof
- `./scripts/check.sh`: 5 PASS (ruff, ruff format, mypy strict, pytest 128 passed, eval), `check passed`, rc 0.
- Eval: the output is byte-identical to `main` (same md5). rules scores 1.0000 on all 4 metrics. majority, keyword_spam and random fail every metric. `git diff main...loop/B5 -- evals/` changes only `written_for_block` B4→B5 and appends `B5` to `finished_blocks`.
- Run by hand (`PYTHONPATH=src python3 -m commit_kind`):

| Case | Result |
|---|---|
| golden path | `fix`, rc 0 |
| `--json` | the 3 keys, rc 0 |
| `--explain` (prefix, ambiguous, verb, object, fallback) | correct phrase for each |
| stdin with a body | `docs` |
| `\xff\xfe` bytes on stdin | rc 0 (`chore`), no traceback |
| `\xe9` on stdin | `fix` |
| empty stdin, blank-only stdin, `""`, `"   "` | rc 1, stdout empty, `classify: error: empty commit message` |
| no message, `--json --explain`, `--bogus`, two positionals, no command | rc 2, usage on stderr, stdout empty |
| `--version` | rc 0 |
| `eval --split dev` | rc 0 |

- Entry point: `pyproject.toml` maps `commit-kind` to `commit_kind.cli:main`, and that import resolves to the function. `__main__` calls the same `main`.
- Guard:
  - A child with `PYTHONPATH=src:tests` has `create_connection` and `getaddrinfo` replaced by `_netguard.blocked`.
  - Negative control: without the guard, the same call raises `ConnectionRefusedError`, so `test_child_network_blocked` would fail.
  - `tests/` is on PYTHONPATH only in the new test helper and in pytest's in-process `pythonpath`. pytest adds that after startup, so `sitecustomize` is not imported there. `check.sh` exports only `src`.
- README: every example matches a fresh run (usage block and eval table). Every factual claim checks out against the code and data:
  - Python ≥ 3.10
  - perf maps to refactor; style, build, ci and revert map to chore
  - scope and `!` are allowed
  - only the summary line is read
  - 360 messages
  - eval exit codes 0/1/2/3
  - the `PYTHON=` override
  - the B2 first-word note (`.planning/B2/REVIEW.md` line 7)
- Size (lines):

| File | Result | Plan's guide |
|---|---|---|
| `cli.py` | +45 | about 60 |
| tests | +81 + 3 | about 80 |
| `README.md` | 86 | 90 |

## Findings
**Blockers:** none.

**Should:**
- S1 `tests/test_classify_cli.py:68-79`: a leftover `run("-c", code) if False else subprocess.run(...)` is dead code and reads oddly in a public demo. Smallest fix: assign `r = subprocess.run(...)` directly.
- S2: the backlog item `20261025-subprocess-netguard` is set to `done`, but the two older subprocess tests still pass `PYTHONPATH=src` only, so their children run unguarded (`tests/test_cli.py:21`, `tests/test_eval.py:219`). Neither uses the network today. Smallest fix: use `os.pathsep.join(["src", "tests"])` in both, 2 lines. Otherwise, note in the backlog item that it covers only the B5 tests.

**Could:**
- C1: messages that start with `-` need `--` (argparse default, for example `classify -- "-x fix"` works). The README could say so in one clause.
- C2: `.planning/B5/SUMMARY.md` says "four commits"; the range now has five, counting the summary commit itself.

**Scope creep:** none. The diff touches only the files the plan owns, plus PLAN and SUMMARY. The simplified stdin and the dropped `--single` follow the orchestrator's override.

## Hard rules: result per rule
1. Secrets: pass (none).
2. Personal data and paths: pass. `git grep` and `git log -p main..loop/B5` find no local paths, and the only e-mail addresses are the noreply ones.
3. Network in tests: pass. The pytest process and the new test's children are guarded; the two older child tests are covered in S2.
4. Negative controls: pass. All 3 controls fail every metric.
5. Backlog: pass. No out-of-block code.
6. Author and trailer: pass. All 5 commits are by `michaelt-45 <202262075+…@users.noreply.github.com>` and end with exactly `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No session links. The README mentions no other project, and its only link is https://github.com/michaelt-45/gated-build-loop.

## Decisions I made (decision, alternative, why)
- **S1 and S2 are Should, not Blocker.** Alternative: block the merge. Why: both are small hygiene fixes with no effect on behavior.
- **I accepted the tests' +81 lines against the plan's guide of about 80.** Why: the plan sets a rough budget, not a hard limit.
- **I accepted chore for messages with invalid bytes in front.** Why: replaced bytes before the prefix are garbage, so no prefix match is the honest answer.

## What you should check yourself
- After the merge and push, open the README: https://github.com/michaelt-45/commit-kind/blob/main/README.md and check that the Usage and Limits sections read the way you want.
- One command, from the repo root: `PYTHONPATH=src python3 -m commit_kind classify --explain "add retry to the client"`. It should print `feat because the verb phrase "add" matched (rule ambiguous.add)`.

## What you should do yourself
Nothing beyond answering this gate. Milestone 1 is done once the orchestrator merges and `check.sh` is green on `main`.

## Open questions, recommendation first
None that change the next block. I recommend folding S1 and S2 into one small commit, either before the merge or right after it.

## Risks, rollback
README output goes stale if the rules change later. Rollback: `git revert -m 1 <merge>`, which also removes B5 from `finished_blocks`. Never `--force`.

## Backlog: created / closed
- Closed: `20261025-subprocess-netguard` (with the S2 caveat).
- Created: none.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"
