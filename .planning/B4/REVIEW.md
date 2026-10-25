# B4 — Review gate
Status: 2026-10-25, branch `loop/B4` (commits `17c6603` plan, `94b6312` classifier, `d4af4a9` eval and baseline, `62f1539` summary). The branch already contains `main`. Not merged. **Verdict: merge-ready yes.** I recommend fixing S1 before the merge (data only, about 15 minutes).

## In one paragraph: what works now that did not before
`commit_kind.classify(msg)` returns `Classification(label, rule, evidence)` from an ordered rule table kept in its own data module (`src/commit_kind/rules.py`). The engine in `src/commit_kind/classifier.py` reads only the first non-blank line and tries the rules in this order:
1. A Conventional Commit prefix (any case, optional scope and `!`, colon followed by whitespace or the end).
2. A leading verb.
3. An ambiguous verb, decided by its object up to the first boundary word.
4. An object word alone.
5. The `chore` fallback.

It is registered as `REGISTRY["rules"]` and is now the gated classifier. The eval passes every threshold, and all three controls still fail every metric.

## Proof
- `./scripts/check.sh` on the branch: 5 PASS (ruff-check, ruff-format, mypy, pytest with 108 tests, eval), `check passed`, rc 0.
- `PYTHONPATH=src python3 -m commit_kind eval --json`: `ok: true`, `failures: []`. Thresholds are 0.85 / 0.85 / 0.70 / 0.70.

| strategy | accuracy | macro_f1 | min_recall | misleading_acc |
|---|---|---|---|---|
| majority | 0.1667 fail | 0.0476 fail | 0.0000 fail | 0.1667 fail |
| keyword_spam | 0.5389 fail | 0.5454 fail | 0.4000 fail | 0.0000 fail |
| random | 0.1667 fail | 0.1671 fail | 0.1333 fail | 0.1333 fail |
| rules | 1.0000 pass | 1.0000 pass | 1.0000 pass | 1.0000 pass |

- **Control numbers:** identical to the B3 baseline.
- **`evals/` diff:** `git diff main...loop/B4 -- evals/` changes only these:
  - `classifier`: from `null` to `"rules"`;
  - `finished_blocks`: `B4` added;
  - `baseline.json`: a new `rules` entry, and `written_for_block` set to B4.
- **Why the test split scores 1.0:** since B2 rework 1, dev and test are drawn from the same templates on purpose; `test_every_template_appears_in_dev` checks this. In a check that printed no test content, 95 % of test messages begin with a word that also begins a dev message.
  - What 1.0 proves: the rule table covers every template family and the misleading tails, the ordering is right, and the controls show the metrics can fail.
  - What it does not prove: anything about real commit messages (see the probe below).
  - This is accepted for the demo and is not a blocker. B5's README should say it in one sentence.
- **Classifier checks.** I ran these myself in a throwaway directory that I have deleted.
  - 20,000 random strings, including non-ASCII, `():!/` and newlines: there were no unexpected exceptions. Evidence was always a non-empty substring of the message, or `""` with rule `fallback`. Two calls on the same input always returned the same result.
  - Long input: `"a(" * 50000 + ":"`, `"fix(" + "(" * 100000 + "):"` and 200k characters followed by `:` each took ≤ 1 ms. `"Fix " + "the " * 100000` (400k characters) took 0.5 s. Time grows linearly with input; the regex has no nested quantifiers.
  - Prefix grammar: `Fix:` and `fix!:` give `fix`; `Feat!: x` gives `feat`; `docs:\tx` gives `docs`.
  - These are not treated as prefixes, by design: `fix(scope):x` (no space after the colon), `fix(a)(b): x` and `Ändere: x`. They are classified by their content.
- **By hand:** `classify("fix: handle empty input")` gives `fix` / `prefix.fix` / `fix:`. `classify("   ")` raises `EmptyMessageError`, rc 1.
- **Size budget:** `rules.py` 115 + `classifier.py` 72 = 187 lines (budget about 200). `tests/test_classifier.py` is 110 lines (budget about 200).

**Probe with invented messages** (not from the dataset). 38 of 56 got the label a reader would expect, and several `chore` results are right only because of the fallback.

| message | got | rule | expected |
|---|---|---|---|
| Refactor the loader / Refactored the loader | chore | fallback | refactor |
| Remove unused imports / Delete dead code | chore | fallback | refactor |
| Optimize the tokenizer / Speed up startup | chore | fallback | refactor |
| Implement retry with backoff | chore | fallback | feat |
| Fixes #123 | chore | fallback | fix (`adds` is listed, `fixes` is not) |
| Correct the off-by-one in pagination | docs | verb.docs | fix (side effect of dev tuning) |
| Update the docs / Update documentation | chore | ambiguous.update | docs |
| Fix docs / Add documentation for the CLI | fix / feat | ambiguous.* | docs |
| Update docstrings / Update examples | chore | ambiguous.update | docs (only singular forms are listed) |
| Improve error messages | fix | object.fix | debatable |
| Remove the deprecated flag | feat | object.feat | debatable |
| Fix login bug / Fixes crash on start | fix | object.fix | ✓ |
| Write tests for the parser / Test the retry logic / Fix flaky test | test | object.test | ✓ |
| Add support for YAML config / Create the export command | feat | ambiguous.add / object.feat | ✓ |
| Rename config to settings | refactor | verb.refactor | ✓ |
| Fix typo in README / Update README | docs | object.docs | ✓ |
| Add CI workflow / Fix lint errors / Bump version to 1.2.0 | chore | object.chore / verb.chore | ✓ |
| Revert "Add caching" / Merge branch 'main' into dev / wip | chore | fallback | ✓ (by fallback; the Revert and Merge items are in the plan's backlog) |

## Findings
**Blockers:** none.

**Should**
- **S1. Common everyday words are missing** (`src/commit_kind/rules.py`). This is what readers will try first. The smallest fix changes data only, with one test row per change in `tests/test_classifier.py`:
  - `verb.refactor`: add `refactor`, `refactored`, `restructure`, `reorganize`, `optimize`, `speed up`. This matches `perf:` → refactor.
  - `verb.feat`: add `implement`.
  - `verb.chore`: add `clean up`, `cleanup`.
  - `ambiguous.fix`: add `fixes`, and move `correct` here from `verb.docs`.
  - `object.docs`: add `spelling` (this keeps the dev case "Correct the spelling …" as `docs`), plus `docs`, `documentation`, `docstrings`, `examples`.
  - `object.chore`: add `dependencies`.
  - Optional: a new `ambiguous.remove` rule (`remove`, `delete`, `drop`, default `refactor`), with one row.
  - Leave out `improve`. It is genuinely ambiguous between feat, refactor and docs.

  These are generic English words, not taken from the test split, so the honesty rule is kept. Afterwards run `PYTHONPATH=src python3 -m commit_kind eval --write-baseline --block B4`, then `./scripts/check.sh`. That run is a gate, not tuning: if test drops below 1.0, drop the word that causes it rather than tuning on test.
- **S2. The plan's backlog items were not filed.** These are: classifying `revert` by its header, `Merge …` commits, and an invented realistic smoke set. They exist only in `.planning/B4/PLAN.md`; hard rule 5 wants them in `.planning/backlog/`. The smoke set would turn the probe above into a check that guards against regressions.

**Could**
- In `src/commit_kind/classifier.py:66`, `rule, end = found` reassigns the loop variable. It is correct because the function returns at once, but a separate name would read better.
- The test `test_very_long_message_is_fast` has a 1 s limit. It is linear and well under the limit here, but the limit could be tight on a slow CI runner.

## Hard rules: result per rule
1. **Secrets:** none. ✓
2. **Personal data and paths:** tests use invented messages only. `git grep` and `git log -p main..loop/B4` find no local paths or e-mail addresses beyond the noreply author and `@pytest`. ✓
3. **No network:** the classifier is pure standard library. `tests/conftest.py` blocks sockets for the whole session. `tests/test_classifier.py` does not read the dataset. ✓
4. **Controls:** all three fail all four metrics, and the eval exits 0. ✓
5. **Backlog:** partly met; see S2. ◐
6. **Commits:** all 4 have author and committer `michaelt-45 <202262075+michaelt-45@users.noreply.github.com>`. Each message ends with exactly `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No session links, and no other project is named in B4's diff. ✓

## Decisions I made (decision, alternative, why)
- **Object conflicts are settled by rule priority** (chore > test > docs > fix > feat), not by the rightmost word as the plan said. The builder disclosed this. It is simpler, the plan's ordering tests pass either way, and the alternative (rightmost) would make "Add an error option" `feat` instead of `fix`. I accepted it.
- **The 1.0 on the test split is accepted** as an artefact of the shared templates, not a blocker. The alternative was asking for a held-out split, which B2 rework 1 already decided against.
- **S1 is a Should, not a Blocker.** All gates pass. The gap shows only on real-world text, which the roadmap does not gate.
- **The B2/B3 `.planning` mentions** of `~/.cache/...` and the skill name were already accepted in B2, so I did not raise them again.

## What you should check yourself
- Rule table: https://github.com/michaelt-45/commit-kind/blob/main/src/commit_kind/rules.py
- Engine: https://github.com/michaelt-45/commit-kind/blob/main/src/commit_kind/classifier.py
- One row per rule: https://github.com/michaelt-45/commit-kind/blob/main/tests/test_classifier.py
- Baseline: https://github.com/michaelt-45/commit-kind/blob/main/evals/baseline.json
- Command (in a checkout of `main`): `PYTHONPATH=src python3 -c 'import commit_kind as c; print(c.classify("Refactor the loader"))'`. Today this shows the S1 gap (`chore`/`fallback`); after S1 it should show `refactor`/`verb.refactor`.

## What you should do yourself
Nothing, apart from answering this gate.

## Open questions, recommendation first
- Should S1 be fixed on `loop/B4` before the merge? Recommendation: **yes**. It is a short sonnet rework, data only, followed by a baseline rewrite. B5's README will show real examples, so B5 is better off building on a classifier that handles "Refactor X" and "Fixes #N".

## Risks, rollback
Risk: readers judge the classifier by everyday messages (S1). Rollback: `git revert -m 1 <merge>`; this also removes B4 from `finished_blocks`.

## Backlog: created / closed
- To create (S2): revert-by-header, `Merge …` commits, invented smoke set.
- Closed: none.

Answer format: "ok" · "ok, but <point>: <change>" · "no: <reason>"
