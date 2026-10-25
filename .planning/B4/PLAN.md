# B4 — Plan

## 1. Goal and user-visible result

B4 adds a small, transparent rule-based classifier and makes it the gated classifier of the eval. B4 starts on `main` after B2 and B3 are both merged.
- `commit_kind.classify("fix: handle empty input")` returns `Classification(label='fix', rule='prefix.fix', evidence='fix:')`.
- On the merged tree, `python -m commit_kind eval` shows `rules` passing all four metrics and the three controls failing all four. The baseline is rewritten for B4.
- **Size budget:** `rules.py` plus `classifier.py` stay at or under about 200 lines of code, and B4's tests at or under about 200 lines. No new flags, no configuration, nothing beyond the roadmap's B4 criteria.

## 2. Interfaces and file ownership (what other blocks may touch, what they must not)

| File | Owner | Later blocks may | Later blocks must not |
|---|---|---|---|
| `src/commit_kind/rules.py` (new: the rule table, data only) | B4 | change rule data, tuned on dev only, with a test and a baseline rewrite with `--reason` | add logic; add test-only words |
| `src/commit_kind/classifier.py` (new: the engine) | B4 | fix bugs with tests | put vocabulary or label names in code |
| `src/commit_kind/__init__.py` | B1 | **B4**: export `classify`, `Classification`, `EmptyMessageError` | — |
| `src/commit_kind/strategies.py` | B3 | **B4**: add the `"rules"` entry | change controls |
| `evals/config.json`, `evals/baseline.json` | B3 | **B4**: set `"classifier": "rules"` and write the baseline via the flag, in one commit | change thresholds or keyword lists; edit the baseline by hand |
| `tests/test_classifier.py` (new) | B4 | add tests | print test-split content |

B4 does not touch `evaluate.py`, `labels.py`, `cli.py` (B5), `scripts/`, `data/`, `pyproject.toml`, `README.md` (B5 documents the classifier) or `.planning/`.

**API** (`classifier.py`, standard library only, pure, deterministic):
```python
class EmptyMessageError(ValueError): ...           # "empty commit message"
@dataclass(frozen=True)
class Classification: label: str; rule: str; evidence: str
def classify(message: str) -> Classification: ...
```
- Empty input is an exception, not a label. The six labels are fixed, and a pseudo-label would break `Strategy.predict` (eval exit 3).
- B5 catches the exception and exits 1. In the eval, an empty record would make `predict` raise, so exit 3 names the record: it fails closed.

**Rule table** (`rules.py`):
- `Rule(id, kind, label, words)` is a frozen dataclass, and `RULES` is one ordered tuple.
- `kind` is one of `prefix`, `verb`, `ambiguous` (its `label` is the default), `object` or `fallback`.
- `BOUNDARY_WORDS` is a tuple.
- All words are lowercase literals. Rule ids are unique (a test checks this).

**Engine:**
1. **Summary.** Take the first non-blank line, stripped; the body is ignored. If there is none, raise `EmptyMessageError`.
2. **Prefix.** Match `^([A-Za-z]+)(?:\([^()\r\n]*\))?!?:(?=\s|$)` with the type case-insensitive. Any scope and `!` are allowed, and the colon must be followed by whitespace or the end.
   - A known type decides, and the evidence is the prefix as written.
   - An unknown type is stripped and the rest is classified by content.
3. **Leading phrase.** Tokens come from `\S+`, lowercased, with surrounding punctuation stripped. Paths stay whole.
   - A `verb` rule matches the first token or tokens.
   - An `ambiguous` verb is resolved by its object: scan the tokens up to the first boundary word right to left, and the first `object` hit decides; otherwise use the verb's default.
   - With no known verb, run the same object scan from the start of the text.
   - The evidence is the substring from the verb through the head.
4. **Fallback.** Label `chore`, evidence `""`. A summary with no known action or artefact is most often maintenance.

**Prefix mapping** (short and documented): the six labels map to themselves. Outside them:
- `perf` → `refactor`: a code change that neither fixes a bug nor adds a feature;
- `style`, `build`, `ci` → `chore`: tooling and upkeep, matching the dataset's chore family;
- `revert` → `chore`: what is reverted varies, and a revert fixes or adds nothing.

Nothing else is mapped.

**Initial table** (from dev only):

| Kind | Rule | Words | Label |
|---|---|---|---|
| verb | `verb.fix` | prevent, handle, avoid, guard against, stop, restore | fix |
| verb | `verb.refactor` | extract(ed), inline, split, consolidate, deduplicate, rename(d), move(d), simplify | refactor |
| verb | `verb.chore` | bump(ed), pin, regenerate, tidy | chore |
| verb | `verb.docs` | document, clarify, explain, describe, reword | docs |
| verb | `verb.test` | cover, parametrize | test |
| verb | `verb.feat` | introduce, support, allow, enable, expose, provide | feat |
| ambiguous | `ambiguous.add` | add(s, ed) | default feat |
| ambiguous | `ambiguous.extend` | extend | default feat |
| ambiguous | `ambiguous.fix` | fix(ed) | default fix |
| ambiguous | `ambiguous.update` | update(d) | default chore |
| ambiguous | `ambiguous.upgrade` | upgrade | default chore |
| ambiguous | `ambiguous.write` | write, wrote | default docs |
| object | `object.chore` | dependency, workflow, lint, pyproject.toml, makefile, .gitignore, ci | chore |
| object | `object.test` | test, tests, fixture(s), coverage, spec, and the path prefix tests/ | test |
| object | `object.docs` | readme, docstring, example, changelog, section, notes, intro, guide, description, typo, wording, and the path prefix docs/ | docs |
| object | `object.fix` | crash, hang, leak, race, deadlock, loop, off-by-one, error, bug, check | fix |
| object | `object.feat` | option, flag, subcommand, setting, mode, format, hook, export, iterator, output | feat |

- Object order is chore, test, docs, fix, feat; capabilities come last.
- Path prefixes are words ending in `/`, matched as prefixes.
- `BOUNDARY_WORDS`: for, to, in, on, of, from, with, after, ahead, following, during, per, that, when, so, by, before, into, out, since.

**Strategy:** `REGISTRY["rules"]` is a factory that ignores the context and returns an object whose `predict(m)` is `classify(m).label`. `evals/config.json` names it `"classifier": "rules"`.

**Honesty:**
- The builder does not open `scripts/generate_dataset.py` and reads only dev records, through a filter, for example `… if r["split"] == "dev"`.
- **Tuning:** copy the config to a `mktemp -d` scratch directory with `classifier: "rules"` and the resolved dataset path, then run `eval --config "$d/config.json" --split dev --show-errors`.
  - That scratch config has no baseline, so a test-split run with it exits 3 without printing metrics.
  - The live config keeps `null` until step 3.

## 3. Steps
| # | Step | Files | Check | Model | Size |
|---|---|---|---|---|---|
| 1 | Rule table, engine and exports, plus `tests/test_classifier.py` (section 4) | `rules.py`, `classifier.py`, `__init__.py`, `tests/test_classifier.py` | tests green; `./scripts/check.sh` green; LOC within budget (`grep -cv '^\s*\(#.*\)\?$'`) | sonnet | M |
| 2 | `"rules"` registry entry; dev tuning with the scratch config, changing rule data only and adding one test row per change | `strategies.py`, `rules.py`, `tests/test_classifier.py` | dev errors listed with reasons in the summary; `./scripts/check.sh` green | sonnet | S |
| 3 | `git merge main` if it moved; set `"classifier": "rules"`; `python -m commit_kind eval --write-baseline --block B4 --reason "B4: first baseline with the rules classifier"`; `./scripts/check.sh`; commit `evals/`. This is the only test-split run. If the write is refused, **stop and report**: no tuning on test | `evals/config.json`, `evals/baseline.json` | `baseline written for B4`; `eval` prints `eval passed`, rc 0 | sonnet | S |
| 4 | Verification of section 5, hygiene, summary | none | all items pass | haiku | S |

Note (orchestrator): B3 is trimmed before it merges; `classifier_required` and the dataset sha check are removed there, so B4 does not rely on them.

Order: serial on `loop/B4`, one agent at a time, `check.sh` after every step. Step 3 may run before the thresholds are approved; the merge waits for approval.

## 4. Tests (name — what it proves; include error paths and one negative control per metric)

`tests/test_classifier.py`, with invented messages only:
- `test_rules[...]`: one parametrised table with at least one row per rule id: message, label, rule, evidence. `test_every_rule_tested` asserts that the set of ids in the table equals the set of ids in `RULES`, which also proves the ids are unique.
- Ordering:
  - `docs: fix a crash` gives `docs` (the prefix wins);
  - `Add a regression test for the crash fix` gives `test` (rightmost head, boundary);
  - `Add a resume mode to report the crash` gives `feat`;
  - `Typo in README` gives `docs` (no verb);
  - `Update parser` gives `chore` (ambiguous default).
- Roadmap edge cases:
  - **empty:** `""` and `"  \n\t"` raise `EmptyMessageError`;
  - **non-ASCII:** `fix: 修复崩溃` gives `fix`/`prefix.fix`, and `Ändere die Ausgabe` gives `chore`/`fallback`/`""`;
  - **very long:** `"fix: " + "a" * 100_000` gives `fix`, and `"Add " + "word " * 50_000 + "option"` gives `feat`, each in under 1 s;
  - **prefix outside the six:** `perf:` gives `refactor`, `ci:` gives `chore`, `wip: add a --json option` gives `feat` (stripped), `wip:` gives `fallback`;
  - **prefix grammar:** `FIX(Parser)!: x` gives `fix` with evidence `FIX(Parser)!:`.
- Invariants and the strategy:
  - the evidence is `""` (fallback only) or a substring of the message;
  - `Classification` is frozen;
  - `REGISTRY["rules"]` predicts `classify(m).label`;
  - `predict("")` raises (error path).

Per metric: B4 adds no metric. The eval on real data is the control: any control at or above a threshold makes the eval report `too lenient`, and the baseline write refuses. B3's fixtures prove that each metric can fail.

## 5. Acceptance criteria (checkable by a machine or in five clicks)

1. The golden path by hand: `PYTHONPATH=src python3 -c 'import commit_kind as c; print(c.classify("fix: handle empty input"))'` prints the result from section 1. The error path: `… c.classify("   ")` raises `EmptyMessageError`, rc 1.
2. `./scripts/check.sh`: 5 PASS, `check passed`, rc 0.
3. `python -m commit_kind eval --json`: `classifier` is `rules`, `ok` is true; `rules` passes all four metrics; all three controls fail all four, with numbers equal to B3's baseline.
4. `git diff main...loop/B4 -- evals/config.json` changes only `classifier` and appends `B4` to `finished_blocks`. `baseline.json` has `written_for_block` B4, a `rules` entry.
5. The LOC budget is met: about 200 for `rules.py` + `classifier.py`, and about 200 for the test file.
6. The summary reports the dev numbers before and after tuning, the test numbers, and "test-split runs: 1".
7. `git diff main...loop/B4 --stat` touches only the section 2 files. The hygiene scans (local paths, e-mail addresses outside CLAUDE.md and `.planning`) print nothing. The author and trailer follow hard rule 6.

## 6. Eval metrics (name, direction, target as "proposal, approval open", what makes it fail)

| Metric | Direction | Threshold (proposal, approval open) | Controls (by construction) | What makes `rules` fail |
|---|---|---|---|---|
| accuracy | higher, `>=` | 0.85 | majority 0.1667, keyword_spam ≤ 0.6667 | verb families that do not generalise |
| macro_f1 | higher, `>=` | 0.85 | majority 0.0476, keyword_spam ≤ 0.80 | one label absorbed by a default |
| min_recall | higher, `>=` | 0.70 | majority 0.0, keyword_spam ≤ 0.6667 | a family's words missing |
| misleading_accuracy | higher, `>=` | 0.70 | keyword_spam 0.0 | reading decoy tails past the boundary |

A throwaway planner probe of this design scored 180/180 on **dev only**. Test numbers are not estimated.

## 7. Risks and rollback

**Risks:**
- **Overfitting to synthetic templates.** Accepted; B5's README says the data is synthetic.
- **Test below a threshold.** Stop; the human decides. No tuning on test.
- **Long input.** Only linear regexes, and only the summary is scanned.

**Rollback:** revert per step on the branch. After the merge, `git revert -m 1 <merge>`. This also removes B4 from `finished_blocks`, so the reverted tree is consistent. Never `--force`.

## 8. Open questions (recommendation first; mark which block a missing answer blocks)

- **Approve the thresholds** 0.85 / 0.85 / 0.70 / 0.70? Recommendation: approve. **Blocks B4's merge.** The orchestrator records the human's answer in `thresholds_status`.

Decisions I made:
- Empty input raises an exception instead of returning a label.
- Only the summary line is classified.
- An unknown prefix is stripped and the rest is classified by content.
- The prefix mapping in section 2.
- The fallback label is `chore`.
- The object head is the rightmost known word before the first boundary word.
- The registry name is `"rules"`.
- Honesty is a process rule (dev only, scratch config); no mechanical honesty test (orchestrator, after B2 rework 1 removed the held-out vocabulary).
- Tuning uses a scratch config that fails closed on test.
- No README change in B4 (B5 owns the docs).

Backlog: classifying `revert` by its header, `Merge …` commits, and an invented realistic smoke set.
