# B2 — Review gate
Status: 2026-10-25, branch `loop/B2`, 8 commits (`2b7c32c..c139249`). Not merged, not pushed. Worktree clean after the review; the throwaway audit scripts ran in a temp directory outside the repo and have been deleted. **Verdict: merge-ready no.** There is one blocker (B-1), and it is cheap to fix inside B2. Open question Q1 is for you to decide; it should go into the same rework.

## In one paragraph: what works now that did not before
`scripts/generate_dataset.py` is a standard-library generator that only uses `randrange`. It writes 360 synthetic commit messages: 60 per label, 22/18/20 per slice, and exactly 50/50 dev/test for every (label, slice). The output is byte-identical across runs, across hash seeds and across Python 3.10, 3.13 and 3.14. `data/commits.jsonl` equals a fresh generation. 26 tests cover format, schema, balance, slice invariants, privacy hygiene, held-out tokens and every error path. `check.sh` now also lints and type-checks `scripts/`. All three negative controls fail every proposed threshold on the test split by a wide margin, and B3's own eval code gives the same numbers. Two problems remain:
- The "dev reveals everything except the held-out vocabulary" property that B4's honesty check relies on does not hold (B-1).
- A dev-fitted first-word lookup table passes all four proposed thresholds (Q1).

## Proof
**Check command:** `./scripts/check.sh`
- ruff-check PASS; ruff-format PASS (12 files); mypy --strict PASS (12 files); pytest PASS, 55 passed in 0.76 s.
- Output ends with `check passed`, exit 0. `grep -c 'src tests scripts' scripts/check.sh` prints 3.

**Plan section 5, re-run by the reviewer:**
1. Regenerate, then `git diff --exit-code`: clean ✓
2. Two runs, the second with `PYTHONHASHSEED=1`: `cmp` with each other and with the committed file prints `same` ✓. Seed 1 gives different bytes ✓. Python 3.13 and 3.14 give byte-identical output too. Seeds 0–59 all generate without a `RuntimeError` (1.4 s in total).
3. `wc -l` prints 360 ✓; `tests/test_dataset.py` passes ✓
4. The `@|https?://|www\.` count is 0 ✓
5. `--seed abc` prints usage and exits 2, and no file is created ✓. `--out <dir>` exits 1 with `error: --out is a directory` ✓
6. `check.sh` exits 0 ✓. `git diff main -- scripts/check.sh` changes exactly the 3 `run_step` lines; the EVAL block is untouched ✓
7. Audit numbers are in the table below ✓
8. Scan a matches only the forbidden-pattern literals: `scripts/generate_dataset.py:882`, `tests/test_dataset.py:193`, and the plan and summary text. There are no real paths. Scan b is empty ✓
9. All 8 commits are by `michaelt-45 <202262075+michaelt-45@users.noreply.github.com>`. Each ends with exactly one `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No session links ✓
10. ✗ (minor, see S-4): the diff also touches `tests/conftest.py` (a docstring) and two `.planning/backlog/` files (status changed to done).

**Step 4 audit, test split (n = 180).** Thresholds (proposal): 0.85 / 0.85 / 0.70 / 0.70.

| Strategy | accuracy | macro-F1 | min recall | misleading acc | result |
|---|---|---|---|---|---|
| majority (`feat`, all dev labels tie) | 0.1667 | 0.0476 | 0.0000 | 0.1667 | fails all; smallest margin 0.5333 |
| keyword_spam, ties to the first label in `LABELS` order (B3 rule) | 0.5389 | 0.5424 | 0.4667 | 0.0000 | fails all; smallest margin 0.2333 (min recall) |
| keyword_spam, ties and zero hits go to `feat` (B2 test rule) | 0.5389 | 0.5424 | 0.4667 | 0.0000 | identical |
| random, seed 20261025 | 0.1333 | 0.1316 | 0.0667 | 0.1333 | fails all; smallest margin 0.5667 |
| random, worst of seeds 0–199 | 0.2500 | 0.2505 | 0.2000 | 0.2833 | still fails; margin 0.4167 |
| *Probe:* Conventional prefix, else `feat` | 0.4722 | 0.5117 | 0.3667 | 0.1667 | fails |
| *Probe:* Conventional prefix, else keyword_spam | 0.5389 | 0.5424 | 0.4667 | 0.0000 | fails |
| *Probe:* keyword_spam on the summary line only | 0.5722 | 0.5846 | 0.4667 | 0.1167 | fails |
| *Probe:* first token → dev-majority label (run as a classifier through B3's `run_eval`) | **0.8833** | **0.8842** | **0.7000** | **0.7833** | **passes all 4** |
| *Probe:* prefix, else first word after the prefix → dev table | **0.9333** | **0.9329** | **0.8000** | **0.9167** | **passes all 4** |
| *Probe:* prefix, else first two words → dev table | 0.9444 | 0.9444 | 0.8333 | 0.9500 | passes all 4 |

- **The plan's bounds hold:** keyword_spam misleading accuracy is 0.0000; its min recall (0.4667) and accuracy (0.5389) are ≤ 0.6667; its macro-F1 (0.5424) is ≤ 0.80. Majority matches the prediction exactly.
- **Cross-check:** B3's `run_eval` (read-only from the B3 worktree, with a temp config at the proposal thresholds) reproduces every control number above to 4 digits.

**Message reading.**
- **Coverage:** I read all 360 messages. For the plan's limit I also drew a seeded, stratified sample of 60 (10 per label; 27 misleading, 20 prefixed, 13 plain; 33 dev, 27 test). It contains **2 flagged messages (c0268, c0349), so the ≤ 3 limit is met.**
- **Whole dataset:** 8 of 360 flagged (2.2 %). 4 of them are in test (c0125, c0268, c0275, c0276).
  - Mislabelled: c0258 "Tidy the README, changelog and docs index" is labelled chore. It is a docs-only change.
  - Ambiguous, because a purpose clause states a competing intent:
    - c0087 "Restore the line ordering to simplify and extract the shared code" (fix or refactor)
    - c0275, c0276, c0349 "Extract … to resolve the issue and the regression" (refactor or fix)
    - c0125 "Enable a dry-run hook to resolve the issue and the regression" (feat or fix)
    - c0007 "Added a limit hook for the chore that handles the CI deps" (feat or chore)
    - c0268 "Stop writing partial files for the chore that handles the CI deps" (fix or chore)
  - Borderline, not counted:
    - c0109, c0147, c0300, c0358 "Introduce … and rename the move helpers" (two changes in one commit; feat leads)
    - c0179, c0301, c0322 "Add … to run the spec and fixtures"
    - c0069
- **The 6 primary probes:** all are unambiguous to a human: c0359 feat "Add a plugin slot", c0334 fix "Fix a livelock", c0289 docs "Write a runbook", c0169 refactor "Untangle the callback chain", c0105 test "Extend the snapshot cases", c0339 chore "Update the Dockerfile base image".
  - 3 of the 6 carry a body sentence from their label's body pool, which reveals the label: c0359, c0289 (which also contains the docs keyword "guide"), and c0339. See S-5.
  - The first-word probe misses c0169, c0289 and c0339.
- **Privacy:** no names, e-mail addresses or URLs. Mid-line capitalised tokens are only README, Python, CI, JSON, YAML, TSV, Markdown, Makefile and Dockerfile, plus verbs after a prefix.

## Findings
**Blockers**
- **B-1: Dev does not show everything the generator does, so B4's honesty check and the plan's accuracy ceiling don't hold.**
  - **What the plan claims:**
    - `.planning/B2/PLAN.md:229`: "Dev and test share all templates, so dev already reveals everything … except the held-out vocabulary"
    - `.planning/B2/PLAN.md:19`: "a small amount of held-out vocabulary"
    - `.planning/B2/PLAN.md:143`: ceiling ≥ 0.967
  - **What the data shows:**
    - 10 templates are used only in test. These include both docs uses of `Describe …` (`scripts/generate_dataset.py:411`, `:479`) and `Write a docstring for the {mod} class` (`:414`). The others are "Introduce {opt} for the {mod}", "Stop the {mod} from {gerund}", "Explain how …", "Consolidate duplicate helpers in {file}", "Extract … into a helper" and "Cover the {mod} {edge} with tests". As a result, docs+Describe and docs+Write never appear in dev.
    - H = test tokens − dev tokens has 81 non-numeric tokens, not just the 30 held-out ones. They include natural words such as `fixes`, `watch`, `timeout`, `class`, `quickstart`, `setup`, `count` and `described`.
  - **Consequences:**
    - B4's planned mechanical check ("no rule contains a token from H, computed from `data/commits.jsonl`") would flag legitimate rules, for example one for "fixes".
    - The −3.3 % worst-case bound and the ≥ 0.967 ceiling are not guaranteed.
  - **Reproduction:** compute `{tokens of test} − {tokens of dev}` with `re.findall(r"[a-z0-9]+", m.lower())`.
  - **Smallest fix in `generate()`:**
    - (a) For dev, pick PLAIN and SHORT templates round-robin from a seeded shuffle, so every template appears in dev. Plain and prefixed dev together have 20 slots per label against at most 10 PLAIN templates; misleading dev has 10 slots against 7 SHORT templates.
    - (b) Build all dev records first. Then reroll any test candidate whose non-numeric tokens are not in the dev token set, unless they are HELDOUT tokens.
    - (c) In `tests/test_dataset.py::test_heldout_tokens_only_in_test`, assert that the non-numeric part of H equals the HELDOUT token set.
    - (d) Correct the plan text accordingly.

**Should**
- **S-1: Purpose-clause decoys and one mislabelled special** (`scripts/generate_dataset.py`).
  - Tails that state an intent rather than context:
    - `:525` "to resolve the issue and the regression" (5 records)
    - `:541` "to simplify and extract the shared code" (2 records)
    - `:555` "for the chore that handles the CI deps" (2 records)
  - `:618` SPECIALS `("chore","docs")` "Tidy the README and changelog" and "…docs index" are docs-only changes labelled chore (c0258).
  - Fix: rewrite the tails as context, for example "after the issue and regression reports", "after the shared code moved" and "for the CI deps job". Replace the chore/docs specials with a tooling-led lead, for example "Pin the docs theme to {ver} for the README and changelog" (docs hits 3 > chore hits 0, and the label is clearly chore).
- **S-2: Record the leniency probe** (numbers above; decision in Q1). If you accept the dataset as it is, add an informational note to the gate. If you rebalance, add a B2 test that asserts the first-word probe stays below the thresholds.
- **S-3: The keyword_spam tie rule in the B2 test differs from B3's contract** (`tests/test_dataset.py:155-159`).
  - B2's test sends ties to `feat`; B3 sends them to the first tied label in `LABELS` order. The numbers are equal on today's data but can diverge after a rework.
  - Fix: `return max(LABELS, key=lambda label: counts[label])`.
- **S-4: Scope (acceptance criterion 10).**
  - The diff touches `tests/conftest.py` and `.planning/backlog/20261025-{netguard-docstring,scripts-lint-targets}.md`, which plan section 2 excludes.
  - The changes themselves are correct: the docstring now matches the body, and both backlog items are tagged `block: B2`.
  - Fix: record it as an accepted deviation (see Decisions).
- **S-5: Primary probes leak their label through the body pool** (c0359, c0289, c0339).
  - Fix: in `build_plain` and `build_misleading` (`scripts/generate_dataset.py:994`, `:1006`), skip `body_lines` when `held["role"] == "primary"`.

**Could**
- **C-1:** Article errors such as "a interactive hook" and "a offline mode" come from `OPT_FORMS` (`scripts/generate_dataset.py:185`); 5 records: c0109, c0179, c0263, c0291, c0343. Use "an" before a vowel.
- **C-2:** 25 "Done <tail>." body lines read unnaturally (`:1003`), for example c0351 "Done for the broken bugfix in the batch runner."
- **C-3:** `!` and `BREAKING CHANGE` appear on docs, test and chore commits (`:983`), for example c0064 "test!: … BREAKING CHANGE: callers must pass the config path explicitly". Limit `!` to feat, fix and refactor.
- **C-4:** `tests/test_dataset.py:50-51` loads the data and the generator at import time. A missing file then shows up as a collection error instead of a named failing test.
- **C-5:** All 6 primary probes are in `plain`, so the plan's misleading-accuracy ceiling (54/60) is conservative. Correct the text when reworking.

**Code review notes (no finding):**
- Randomness comes only from `randrange`, through `Rng.pick`, `chance` and the Fisher–Yates shuffle.
- Pools are tuples; there is no set iteration and no float output; dicts are insertion-ordered; `json.dumps(sort_keys=True, ensure_ascii=True)`.
- The reroll loop advances the RNG on every try and is capped at 1000 attempts.
- `validate` checks the held-out leak at token level: each token is in exactly one record, in test, with the right label and slice.
- Writes are atomic and clean up the temp file.
- Exit codes are 0, 1 and 2 as specified.
- No test reads `evals/` or other live state; the reads of the committed data file and `check.sh` are the intended static checks.
- The generator imports nothing network-related. The subprocess runs are not under the network guard, which is the known backlog item `20261025-subprocess-netguard`.

## Hard rules: result per rule
1. **Secrets:** ✓ none in the diff or the data.
2. **Personal data and paths:** ✓ the data is synthetic and has no names, e-mail addresses or URLs (all 360 messages read). The only path-like strings in committed files are the forbidden-pattern literals. `~/.cache/...` in `.planning/STATE.md` and `HANDOFF.md` predates B2 and is not absolute.
3. **No network in tests:** ✓ an AST test enforces standard-library-only imports; nothing is downloaded.
4. **Negative controls:** ✓ all three fail every gated metric on this data, confirmed with B3's code. The leniency caveat is under Q1.
5. **Backlog:** ✓ the builder's ideas are in the summary, not in code. They still need to be filed (see Backlog).
6. **Identity and commits:** ✓ 8/8 commits by `michaelt-45` with the noreply address, exactly one trailer each, no session links. The diff mentions no other project.

## Decisions I made (decision, alternative, why) — the human can overrule only here
- **keyword_spam tie rule:** I took B3's rule as authoritative, not the B2 test's ties-to-`feat` rule, because B3 owns the metric. Both give the same numbers.
- **Cross-check against B3:** I ran B3's `run_eval` from its unmerged worktree with a temp config, instead of trusting only my own script, because B3 is the authority after merge.
- **How much I read:** all 360 messages instead of only 60, to be strict on data quality. The plan's ≤ 3 limit is judged on a seeded, stratified 60-sample.
- **Borderline messages:** the two-change "Introduce … and rename …" messages and the "flag to run the spec" messages count as borderline, not ambiguous, because the leading phrase clearly carries feat.
- **Severity:** I rated the H and dev-coverage gap as a blocker, because it breaks an interface B2 promised to B4. I left the first-word leniency to you, because dataset difficulty is a decision about numbers.
- **Scope deviation:** I would accept the conftest docstring and the backlog status edits; the alternative is to revert them. They are correct and tagged for B2.
- **Python versions:** I did not test 3.11 or 3.12 (not on PATH). 3.10, 3.13 and 3.14 give identical output.

## What you should check yourself (max. 5 clicks, with command or link)
These links work after the merge; the branch is not pushed yet.
1. https://github.com/michaelt-45/commit-kind/blob/main/data/commits.jsonl — search for `c0258` (labelled chore) and `c0275` (labelled refactor). Would you give them the same labels?
2. https://github.com/michaelt-45/commit-kind/blob/main/scripts/generate_dataset.py — the `TAILS` and `SPECIALS` blocks, where the decoys come from.
3. https://github.com/michaelt-45/commit-kind/blob/main/.planning/B2/PLAN.md — section 2 "Intended signal" (why the first word decides so much) and section 7 (the claim that B-1 breaks).
4. Command: `python3 scripts/generate_dataset.py --out data/commits.jsonl && git diff --exit-code data/commits.jsonl && echo same`

## What you should do yourself (guided steps: goal, duration, per step link, click, input, result; never "see file X")
Goal: decide how hard the dataset should be (Q1). About 5 minutes.
1. Open the plan link above and read "Intended signal" in section 2. Result: you see that unambiguous leading verbs decide the label on their own.
2. In this gate, look at the two bold probe rows in the Proof table. Result: a first-word lookup table already reaches 0.88–0.93 accuracy.
3. Reply with one of the following. Result: the orchestrator starts the B2 rework with or without the rebalance.
   - `ok, but Q1: rebalance`
   - `ok, but Q1: accept`

## Open questions, recommendation first (only those that change the next block)
- **Q1 — How hard should the dataset be? Recommendation: rebalance in the same rework as B-1.**
  - Make about half of the plain and misleading leading phrases use the ambiguous verbs Add, Update, Fix, Write and Extend, so the label needs verb plus object.
  - Targets: the first-word probe below 0.80 accuracy and below 0.70 misleading accuracy and min recall, while a verb+object rule set stays at ≥ 0.95.
  - Alternative: accept as it is (the leading verb is the plan's intended signal) and raise the thresholds after B4. With a ceiling of about 0.96, that leaves little room.
  - Blocks: B3's baseline written on merge, and B4's tuning.
- **Q2 — What should B4's peeking check use as H? Recommendation: the HELDOUT distinctive tokens**, asserted equal to the test-only non-numeric tokens once B-1 is fixed. Blocks: B4's plan.

## Risks, rollback (one line)
The rework regenerates `data/commits.jsonl`, so B3's trial merge and baseline must be re-run on it afterwards. Rollback: nothing is merged; revert or redo the commits on `loop/B2`.

## Backlog: created / closed
- **Closed (verified):** `20261025-netguard-docstring` (the docstring now matches the body) and `20261025-scripts-lint-targets` (`check.sh` lints and type-checks `scripts`).
- **To create** (the orchestrator files them; the reviewer is read-only):
  - B4: a consistency test that `CONTROL_KEYWORDS` equals the lists in `evals/config.json` (builder's proposal).
  - Uniform capitalisation after the prefix (builder's proposal; low priority).
  - C-1 to C-4 if the rework does not include them.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"
