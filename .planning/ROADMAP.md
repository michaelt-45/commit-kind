# Roadmap

## Milestone 1: classifier, CLI and gated eval

Goal: `commit-kind classify "fix: handle empty input"` prints `fix` and the rule that fired; `commit-kind eval`
scores the classifier on a synthetic, seeded dataset against a baseline and three negative controls; one command
(`./scripts/check.sh`) runs ruff, mypy, pytest and the eval.

Labels (fixed for the milestone): `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Order and parallel groups: **B1** → (**B2** ∥ **B3**) → **B4** → **B5**. B2 and B3 share only the dataset schema
below, which is fixed here so they can run in parallel.

Dataset schema (JSONL, one object per line):
`{"id": "c0001", "message": "<full commit message, may contain newlines>", "label": "<one of the six>",
"split": "dev" | "test", "slice": "<generator slice name, e.g. prefixed | plain | misleading>"}`

---

### B1 — Gate skeleton

Package skeleton and the single check command, before any feature.

Acceptance criteria:
- `./scripts/check.sh` exists, runs `ruff check`, `ruff format --check`, `mypy --strict` on `src/` and `tests/`,
  and `pytest`; exits 0 on a clean tree and non-zero if any step fails (a test proves a failing step propagates).
- `pyproject.toml` (Python ≥ 3.10, no runtime dependencies; dev tools listed as an optional extra), `src/commit_kind/`
  package with `__version__`, console script `commit-kind` and `python -m commit_kind --version`.
- Tests block network access: a test asserts that opening a socket during tests raises.
- `.gitignore`, `LICENSE` (MIT), minimal `README.md` (what it is, how to run the check).
- `check.sh` has a clearly marked place where B3 adds the eval step.

### B2 — Synthetic dataset (parallel with B3)

Acceptance criteria:
- `scripts/generate_dataset.py --seed 20261025 --out data/commits.jsonl` writes ≥ 300 messages (target 360,
  60 per label), uses only the standard library and templates/vocabulary defined in the script; no real repos, no
  names, no e-mail addresses, no URLs.
- Running it twice with the same seed gives byte-identical output; the committed `data/commits.jsonl` equals a fresh
  generation (test).
- Records follow the schema above; ids unique; every label has ≥ 40 messages; `split` is about 50/50 dev/test per
  label, deterministic by seed.
- Slices: `prefixed` (Conventional Commit prefix, sometimes with scope, `!`, body or footer), `plain` (no prefix,
  type follows from content), `misleading` (contains keywords of another class, e.g. "add tests for the login fix"
  is `test`, "fix typo in README" is `docs`). Each slice ≥ 20 % of the data.
- A test fails if any message matches an e-mail or URL pattern.

### B3 — Eval harness with negative controls (parallel with B2)

Acceptance criteria:
- `commit_kind.evaluate` computes on the `test` split: accuracy, macro-F1, minimum per-class recall, and accuracy on
  the `misleading` slice. Values are rounded to 4 digits at the point of comparison and storage.
- Negative controls as strategies: `majority` (always the most frequent dev label), `keyword_spam` (predict the class
  whose keyword list has the most hits in the message, no structure), `random` (seeded uniform). Each must fail every
  gated metric; if any control passes any metric the eval exits non-zero and names the metric as too lenient.
- `evals/config.json`: thresholds per metric (proposal: accuracy ≥ 0.85, macro-F1 ≥ 0.85, min recall ≥ 0.70,
  misleading accuracy ≥ 0.70; approval open), `finished_blocks`, dataset path. `evals/baseline.json`: metrics per
  strategy. The eval exits non-zero if the classifier is below threshold or below baseline.
- Until B4, the classifier slot may be empty: the eval then scores controls only and exits 0 if all controls fail.
- `python -m commit_kind eval [--json]` prints a table (strategy × metric, pass/fail); `check.sh` runs it.
- Tests use fixtures, never the live config or baseline: per metric one fixture where it fails and one where it
  passes; a rounding test with a non-terminating fraction (e.g. 246/291) against a stored baseline.

### B4 — Rule-based classifier

Acceptance criteria:
- `commit_kind.classify(message) -> Classification(label, rule, evidence)`; deterministic, pure, standard library.
- Rules are ordered and data-driven (a rule table in its own module, not scattered `if`s): Conventional Commit
  prefix first (including scope and `!`), then content rules; every result names the rule id and the matched text.
- Built and tuned on the `dev` split only; the `test` split is scored by the eval, not read by the builder.
- On the merged tree the eval passes every threshold; all three controls still fail every metric; baseline
  rewritten with the classifier's numbers.
- Unit tests per rule, including empty message, whitespace only, non-ASCII, very long message, and a prefix that is
  not one of the six labels.

### B5 — CLI and docs

Acceptance criteria:
- `commit-kind classify "<message>"`, `commit-kind classify -` (stdin, one message per blank-line-separated block or
  the whole input with `--single`), `--json` (label, rule, evidence), `--explain` (human-readable reason).
- Exit codes: 0 success, 2 usage error, 1 for an empty message; errors go to stderr.
- End-to-end tests run the CLI in a subprocess (no network, `PYTHONPATH=src`).
- README: install, usage examples with real output, how the classifier decides, how to run `check.sh` and the eval,
  the dataset and its limits (synthetic, generated by the same project), the `.planning/` folder explained in three
  sentences.
- Milestone 1 is done when B5 is merged and `./scripts/check.sh` is green on `main`.
