# B1 — Review gate
Status: 2026-10-25, branch `loop/B1`, 6 commits (`0373b77..1cbeb21`) on top of `main` `3c6bad0`. Not merged, not pushed. **Verdict: merge-ready no.** There is one blocker and it is a one-line text fix. Once it is fixed and acceptance criterion 10 and `./scripts/check.sh` are re-run, the branch can merge without another review.

## In one paragraph: what works now that did not before
The repo now has a working gate and a package skeleton. `./scripts/check.sh` runs `ruff check`, `ruff format --check`, `mypy --strict` (on `src` and `tests`) and `pytest`. It prints one PASS/FAIL line per step and a summary. It exits 0 only when every step passes, 1 when any step fails, 2 on a usage error, and 3 when it refuses a recursive run. It works from any directory, under macOS bash 3.2, and with `PYTHON=` set to choose the interpreter. There is a marked place where B3 adds the eval step. `src/commit_kind` has `__version__ = "0.1.0"`. `python -m commit_kind --version` prints `commit-kind 0.1.0`. Running it with no arguments exits 2, which matches B5's exit-code contract. `pyproject.toml` declares Python ≥ 3.10, no runtime dependencies, a `dev` extra and the `commit-kind` console script. An autouse fixture blocks sockets in tests. `.gitignore`, the MIT `LICENSE` and a minimal `README.md` are in place.

## Proof
- **Check command** (bash 3.2.57, Python 3.10.13, ruff 0.15.12, mypy 2.1.0, pytest 9.0.2):
  - `./scripts/check.sh; echo $?` gave `PASS ruff-check` (ruff: 8 files formatted), `PASS ruff-format`, `PASS mypy` ("no issues found in 8 source files"), `PASS pytest` (21 passed in 0.09 s), `check passed`, `0`. Wall time 0.9 s.
  - The 21 tests break down as: network guard 4, package 5, CLI 4, check script 8.
- **Negative controls for the gate.** Each was injected by me, the exit code was captured directly with `; echo $?`, and the file was then deleted:
  - `--selftest-fail` showed `PASS before-failure`, `FAIL injected-failure (exit 1)`, `PASS after-failure`, `check failed: injected-failure`, and rc **1**. `--selftest-pass` gave rc 0. `--bogus` printed usage on stderr, rc **2**.
  - Ruff: `import os` in `src/commit_kind/_tmp_bad.py` gave `FAIL ruff-check (exit 1)`, the other three steps PASS, `check failed: ruff-check`, rc **1**. The builder had not captured this exit code; I did.
  - Mypy only: `def f() -> int: return "x"` gave `FAIL mypy (exit 1)`, ruff and pytest PASS, rc **1**.
  - Pytest only: `assert len("ab") == 3` in `tests/test_tmp_injected.py` gave `FAIL pytest (exit 1)`, the other steps PASS, rc **1**. With `assert 1 == 2` both mypy (comparison-overlap) and pytest failed, `check failed: mypy pytest`, rc 1.
  - Format only: `x=1` gave `FAIL ruff-format`, rc 1.
  - `PYTHON=/nonexistent/python` gave all four steps `FAIL (exit 127)` and rc 1. The real exit code shows up in the FAIL line.
  - After each removal the run was `check passed`, rc 0, and `git status` was clean.
- **Robustness:**
  - Green when called from a parent directory, from inside `scripts/`, from `/` via `bash <path>`, as `sh scripts/check.sh`, and under `env -i PATH=… HOME=…` (unset `PYTHONPATH` and `PYTHON` do not trip `set -u`).
  - Green with `PYTHONPATH=/nonexistent` and with `COMMIT_KIND_CHECK_RUNNING=` (empty).
  - Refused with rc 3 when `COMMIT_KIND_CHECK_RUNNING=0`.
- **Plan section 5, re-run by me:**
  - Criteria 1–9, 11 and 12 pass.
  - 4: one EVAL marker line, line 44.
  - 5: `--version` gives rc 0; no arguments prints usage on stderr, rc 2.
  - 8: `100755`.
  - 11: the `%B` log of all 6 commits, including the plan commit the builder did not check, passes.
  - **Criterion 10 fails** (see Blocker B-1).
- **Network guard probes.** I ran a temporary test file, then deleted it. Sockets inside a test are blocked. But a socket opened in module-level test code (at collection), a socket opened in a module-scoped fixture, `socket.getaddrinfo("localhost", 80)` and `_socket.socket()` all succeeded (see S-1). monkeypatch restores the originals after each test, so nothing leaks between tests.
- **Evals:** none in B1. Transcripts: none. Nothing to click.

## Findings
**Blockers**
- **B-1 `.planning/B1/SUMMARY.md:21`: acceptance criterion 10 (path scan) fails at HEAD, and the summary says it passed.**
  - Line 21 contains a `/tmp`-rooted example path ("…temp path (`/tmp`…`/x` is a directory)").
  - Reproduce: `git grep -nE '/(Users|home|private|tmp)/'` prints that line. The plan says this scan must print nothing.
  - `SUMMARY.md:38` says "The path scan was empty". That was true before the summary commit and is false now.
  - It is not a privacy leak (no user name), but it breaks a written gate criterion.
  - Smallest fix: reword line 21, for example "my first criterion-1 run wrote to a temp path that turned out to be a directory". Commit, then re-run the scan and expect no output.
  - The REVIEW.md that gets committed must not quote such a path either.

**Should**
- **S-1 `tests/conftest.py:18-21`: the network guard is narrower than "the test suite blocks sockets".**
  - The roadmap criterion is met, and nothing in B1 touches the network. The gaps the plan does not name:
    - (a) The fixture is function-scoped. Module-level test code at collection time, and session- or module-scoped fixtures, run unguarded. Reproduced as described in Proof.
    - (b) `getaddrinfo`, `gethostbyname` and `gethostbyname_ex` are not patched, so a DNS lookup can leave the machine. Stdlib HTTP is covered because the patched `create_connection` raises before DNS. Third-party clients that resolve first are not covered.
  - Smallest fix:
    - Also patch the three resolver functions.
    - Install the patch once for the whole session, for example in `pytest_configure` or at conftest import, saving and restoring the originals in `pytest_unconfigure`. Keep the autouse fixture.
    - Add one test for `getaddrinfo`.
  - The ownership table in PLAN section 2 allows this kind of strengthening.
- **S-2 PLAN.md:189: the e-mail half of criterion 10 can never print nothing.** It always hits `CLAUDE.md:17-18`: the documented noreply identity, already on `main`. The builder flagged this correctly. Future plans should exclude `CLAUDE.md` from the scan or allow those two known noreply addresses.
- **S-3: hard rule 5.** The builder's three backlog proposals exist only in `SUMMARY.md`, not as files in `.planning/backlog/`. They are a subprocess-level network guard, the CLAUDE.md exclusion for the e-mail scan, and adding `scripts` to the ruff/mypy targets in B2. The orchestrator should create them on merge, together with S-1 if S-1 is deferred.

**Could**
- **C-1 `scripts/check.sh:35-37`:** the refusal message does not name the variable. Any non-empty `COMMIT_KIND_CHECK_RUNNING`, even `0`, gives exit 3 with no hint. The variable is exported only inside the script's own process, so it never leaks into the caller's shell; a wrong refusal needs an explicit user export. Fix: print `refusing recursive check.sh run (COMMIT_KIND_CHECK_RUNNING is set; unset it)`.
- **C-2 `scripts/check.sh:33`:** extra arguments are silently ignored. `--selftest-fail extra` runs normally, and `check.sh "" x` runs real mode. Fix: `[ $# -le 1 ]` or a usage error.
- **C-3 `src/commit_kind/cli.py:13`:** usage shows `{} ...`, and an unknown command prints "choose from )". Fix: `add_subparsers(dest="command", metavar="<command>")`. Alternatively let B3's `eval` subcommand make it go away.
- **C-4 `tests/test_package.py:33-35`:** the test checks the entry-point string and `callable(main)` separately. Resolving the string with `importlib` plus `getattr` would prove the target. The regex-based pyproject tests are brittle but fail closed, which is acceptable without `tomllib`.
- **C-5 `tests/test_check_script.py:6`:** `from conftest import NetworkBlockedError` relies on pytest's default `prepend` import mode and a single conftest. It breaks if a later block adds a nested `conftest.py` or switches to `importlib` mode. A small helper module, or matching `RuntimeError` plus the message, avoids that.
- **C-6 `tests/test_check_script.py:61-62`:** the static check misses `set -o errexit`. It also does not check that the `run_step` lines sit in the real-mode branch. Low value.

**Builder claims verified:** all accurate except `SUMMARY.md:38` (B-1). The file count of 15 predates the summary commit; the diff has 16 files, all within the plan's list plus `.planning/B1/`.

## Hard rules: result per rule
1. **Secrets:** pass. None in files or in the log; the `git grep` for key, secret, token and password hits only the rule text in CLAUDE.md.
2. **Personal data and local paths:** pass on substance. There is no personal data, no user name and no other-project mention (I searched for tool, skill and user names). The temp-path example is the formal failure, B-1.
3. **No network in tests:** pass for B1. An autouse guard is in place and four tests prove it, including that urllib's `OSError` handling cannot swallow the error. The gaps are listed under S-1.
4. **Negative controls:** not applicable to evals until B3. The gate's own negative control (`--selftest-fail`) plus my injected ruff, mypy, pytest and format failures all propagate as rc 1.
5. **Backlog, not code:** pass for code (no out-of-scope features). The entries still need to be filed (S-3).
6. **Commits:** pass. All 6 commits on `main..loop/B1` have author and committer `michaelt-45` with the GitHub noreply address. Each message's last line is exactly `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, once per message, with no session links and no URLs in the messages.

## Decisions I made (decision, alternative, why) — the human can overrule only here
- **B-1 is a blocker** although it leaks nothing. Alternative: rate it Should. Why: the section 5 criteria are the merge contract, the summary misreports it, and the fix is one line.
- **The network guard gaps are Should, not Blocker.** Alternative: block until the guard is session-wide and covers DNS. Why: the roadmap criterion is met, no B1 code uses the network, and B2/B3 may strengthen the guard under the ownership table.
- **"A test proves a failing step propagates" counts as met.** The proof is the self-test mode, the static step-list test and my manual real injections, not an automated test that runs real mode with a broken file. Alternative: require a test that runs real mode on a temporary copy of the repo. Why: that would mean nested pytest runs; the plan chose this design on purpose and the recursion guard is tested.
- **The regex-based `pyproject.toml` tests are accepted.** Alternative: a TOML parser. Why: Python 3.10 has no `tomllib`, runtime dependencies are not allowed, and the tests fail closed.

## What you should check yourself (max. 5 clicks, with command or link)
1. Open https://github.com/michaelt-45/commit-kind/blob/main/scripts/check.sh. You should see four `run_step` lines (ruff check, ruff format, mypy, pytest) and the block marked `EVAL STEP (added in B3)`.
2. Open https://github.com/michaelt-45/commit-kind/commits/main. Every commit should be by `michaelt-45`, and each message should end with the `Co-Authored-By: Claude Opus 5.5` line.
3. In a terminal with Python 3.10+ and ruff, mypy and pytest installed, run:
   `git clone https://github.com/michaelt-45/commit-kind && cd commit-kind && ./scripts/check.sh; echo $?`
   Expected: four `PASS` lines, `check passed`, then `0`. Then `./scripts/check.sh --selftest-fail; echo $?` should print `FAIL injected-failure` and then `1`.

## What you should do yourself (guided steps: goal, duration, per step link, click, input, result; never "see file X")
Nothing for B1. No credentials, accounts or outward-facing actions are needed.

## Open questions, recommendation first (only those that change the next block)
None that change B2 or B3. Optional: I recommend including S-1 (session-wide guard plus resolver functions, about 10 lines and 1 test) in the same fix commit as B-1. Otherwise file it in the backlog and do it before B5's subprocess end-to-end tests.

## Risks, rollback (one line)
Low risk: the block adds new files only, has no runtime dependencies and changes no state. Rollback is `git revert -m 1 <merge-commit>` on `main`, never `--force`.

## Backlog: created / closed
- Created (to be filed as files by the orchestrator):
  - network guard session-wide plus DNS resolvers (S-1);
  - subprocess-level network guard before B5 (builder);
  - exclude `CLAUDE.md` from the e-mail hygiene scan (S-2, builder);
  - B2 adds `scripts` to the ruff and mypy targets (builder);
  - `check.sh` refusal message and extra-argument handling (C-1, C-2).
- Closed: none.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"
