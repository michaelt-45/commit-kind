#!/usr/bin/env python3
"""Generate the synthetic commit-message dataset (standard library only).

Seeded and byte-reproducible: all randomness is ``Random.randrange`` and no set is iterated.
Slices: ``prefixed`` (Conventional Commit), ``plain`` (no prefix, the leading phrase decides)
and ``misleading`` (no prefix, keywords of another label outnumber the true label's).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

DEFAULT_SEED = 20261025
LABELS = ("feat", "fix", "docs", "refactor", "test", "chore")
SLICES = ("prefixed", "plain", "misleading")
PER_LABEL = 60
SLICE_COUNTS = {"prefixed": 22, "plain": 18, "misleading": 20}
MAX_LINE = 72
MAX_ATTEMPTS = 1000

# Keyword contract shared with the eval; a hit is a token of [a-z0-9]+ equal to an entry.
_WORDS = {
    "feat": "feat feature add adds added new support implement introduce allow enable",
    "fix": "fix fixes fixed bug bugfix crash error issue broken resolve typo regression",
    "docs": "docs doc documentation readme comment comments docstring guide changelog "
    "example examples",
    "refactor": "refactor refactoring rename renamed move moved extract simplify cleanup "
    "restructure",
    "test": "test tests testing spec coverage fixture fixtures mock assert pytest",
    "chore": "chore bump upgrade dependency dependencies deps ci build release version lint",
}
CONTROL_KEYWORDS = {label: words.split() for label, words in _WORDS.items()}

# Slot pools for {name} placeholders (v is computed). Indented lines continue a pool.
POOLS_TEXT = """
m parser|scheduler|cache|exporter|config loader|report builder|retry policy|diff engine
 |indexer|queue worker|path resolver|formatter
o a --dry-run option|a --limit option|a --quiet flag|a --format option|a --verbose flag
 |an --output option|a timeout setting|an offline mode|a retry hook
fmt JSON|CSV|TSV|YAML|Markdown
act skip empty entries|retry failed jobs|read settings from a file|reuse open connections
 |stream large inputs|ignore unknown keys
g retrying forever|writing partial files|dropping the last row|reading stale entries
 |hanging on empty input|skipping valid lines
edge empty input|a missing key|a closed socket|a partial read|a duplicate id|an unreadable file
flaw an off-by-one|a memory leak|a race|a hang|a wrong exit code|a missing null check
 |a deadlock
thing exit status|line ordering|retry delay|default timeout|cursor position
part the parsing logic|the retry loop|the path handling|the option handling
 |the formatting code
pkg fastcodec|tinyjson|ratelimit|pathkit|logshim|cliparse
case retry paths|empty input|timeout handling|ordering rules|default settings
scope cli|core|io|api|config|parser
body The change is small and stays inside one module.|Callers see the same behaviour as before.
 |Output order is stable between runs.|Nothing else in the module is touched.
 |Easy to revert on its own if needed.|Verified by hand on a small sample.
"""

# Templates per label: "p" lines are used by prefixed and plain, "m" lines by misleading.
# Misleading tails name another label's keywords as context, never as the leading phrase.
TEMPLATES = """
feat
 p Add {o} to the {m}
 p Added {o} to the {m}
 p Introduce {o} for the {m}
 p Support {fmt} output in the {m}
 p Allow the {m} to {act}
 p Enable {o} in the {m} by default
 p Provide {o} for the {m}
 m Introduce {o} for the release and build jobs
 m Add {o} for the {m} after the issue and regression reports
 m Support {fmt} output in the {m} for the README examples
 m Allow the {m} to {act} after the spec and coverage runs
 m Enable {o} after the shared code was moved and renamed
 m Provide {o} in the {m} for the lint and build jobs
fix
 p Prevent the {m} from {g}
 p Handle {edge} in the {m}
 p Guard against {edge} in the {m}
 p Stop {g} in the {m}
 p Restore the {thing} in the {m}
 p Fix {flaw} in the {m}
 p Fixed {flaw} in the {m}
 m Prevent the release build from {g}
 m Handle {edge} in the {m} for the new feature
 m Guard against {edge} after the test and coverage changes
 m Stop {g} after the refactor and rename
 m Restore the {thing} after the docs and README changes
 m Fix {flaw} in the {m} for the CI deps job
docs
 p Document the {thing} of the {m}
 p Clarify the {m} behaviour in the usage guide
 p Explain how the {m} picks its defaults
 p Describe {part} in the docs
 p Reword the {m} section of the README
 p Write a docstring for the {m} class
 p Correct the spelling in the {m} comments
 m Fix typo and broken wording in the README section on the {m}
 m Reword the notes on the new feature in the {m} guide
 m Describe how the {m} handles the crash and error cases
 m Clarify the {m} test and coverage notes in the docs
 m Reword the refactor notes for the {m}
 m Document the release and build steps for the {m}
refactor
 p Extract {part} from the {m} into a helper
 p Inline the {m} wrapper
 p Split the {m} into smaller functions
 p Consolidate duplicate helpers in the {m}
 p Rename the {m} helpers for clarity
 p Move {part} into the {m}
 p Simplify the {m} control flow
 m Extract the error and crash handling of the {m}
 m Inline the {m} wrapper used by the release build
 m Split the {m} into smaller functions for the new feature
 m Consolidate the {m} setup shared with tests and fixtures
 m Simplify the {m} code behind the README and changelog
 m Rename the {m} helpers after the issue and regression reports
test
 p Cover the {m} {case} with tests
 p Parametrize the {m} tests
 p Write tests for the {m} {thing}
 p Extend the {m} fixtures
 p Mock the clock in the {m} tests
 p Assert the exit code in the {m} tests
 m Add a regression test for the crash fix in the {m}
 m Cover the new {m} feature with tests
 m Parametrize the {m} tests for the release and build steps
 m Extend the {m} fixtures after the move and rename
 m Mock the {m} in the README examples
 m Assert the exit code for the error and crash paths of the {m}
chore
 p Bump {pkg} to {v}
 p Pin {pkg} to {v} in pyproject.toml
 p Regenerate the lock file after the {m} change
 p Tidy the .gitignore entries for {m} output
 p Update the lint settings for the {m} package
 p Update the CI workflow cache key for {m} jobs
 m Pin the docs theme to {v} for the README and changelog
 m Regenerate the {m} lock file after the pytest and coverage changes
 m Tidy the {m} lint settings after the refactor and rename
 m Bump {pkg} to {v} after the crash and error reports
 m Update the CI workflow of the {m} for the new feature branch
 m Pin {pkg} to {v} after the move and rename
"""

PREFIX_RE = re.compile(r"^\s*[A-Za-z]+(\([^)]*\))?!?:\s")
BREAKING = ("feat", "fix", "refactor")


def parse_pools() -> dict[str, list[str]]:
    pools: dict[str, str] = {}
    for line in POOLS_TEXT.strip().splitlines():
        name, _, rest = line.partition(" ")
        if name:
            key = name
            pools[key] = rest
        else:
            pools[key] += rest
    return {name: text.split("|") for name, text in pools.items()}


POOLS = parse_pools()


def parse_templates() -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for line in TEMPLATES.strip().splitlines():
        if not line.startswith(" "):
            out[line] = {"p": [], "m": []}
            label = line
        else:
            out[label][line[1]].append(line[3:])
    return out


def pick(rng: random.Random, seq: Sequence[str]) -> str:
    return seq[rng.randrange(len(seq))]


def shuffled(rng: random.Random, seq: Sequence[T]) -> list[T]:
    items = list(seq)
    for i in range(len(items) - 1, 0, -1):  # Fisher-Yates, randrange only
        j = rng.randrange(i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def cycle(rng: random.Random, seq: Sequence[T]) -> Iterator[T]:
    """Endless round-robin over reshuffled copies: every item shows up once per round."""
    while True:
        yield from shuffled(rng, seq)


def fill(rng: random.Random, template: str) -> str:
    def slot(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "v":
            return f"{1 + rng.randrange(3)}.{rng.randrange(20)}.{rng.randrange(10)}"
        return pick(rng, POOLS[name])

    return re.sub(r"\b(a) (?=[aeiou])", "an ", re.sub(r"\{(\w+)\}", slot, template))


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def hits(message: str) -> dict[str, int]:
    toks = tokens(message)
    return {label: sum(toks.count(word) for word in CONTROL_KEYWORDS[label]) for label in LABELS}


def valid(label: str, slice_: str, message: str) -> bool:
    lines = message.split("\n")
    if not message.isascii() or any(len(x) > MAX_LINE or x != x.rstrip() for x in lines):
        return False
    counts = hits(message)
    others = [counts[x] for x in LABELS if x != label]
    if slice_ == "prefixed":
        return True
    if any(PREFIX_RE.match(x) for x in lines):
        return False
    return max(others) == 0 if slice_ == "plain" else max(others) > counts[label]


def compose(rng: random.Random, label: str, slice_: str, summary: str) -> str:
    parts = []
    breaking = False
    if slice_ == "prefixed":
        if rng.randrange(2):
            summary = summary[0].lower() + summary[1:]
        scope = f"({pick(rng, POOLS['scope'])})" if rng.randrange(2) else ""
        breaking = label in BREAKING and rng.randrange(10) == 0
        summary = f"{label}{scope}{'!' if breaking else ''}: {summary}"
    parts.append(summary)
    if rng.randrange(10) < 3:
        parts.append("\n".join(shuffled(rng, POOLS["body"])[: 1 + rng.randrange(3)]))
    if slice_ == "prefixed":
        if breaking:
            parts.append("BREAKING CHANGE: callers must pass the config path explicitly")
        elif rng.randrange(5) == 0:
            parts.append(pick(rng, ("Refs", "Closes")) + f": #{1 + rng.randrange(900)}")
    return "\n\n".join(parts)


def generate(seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    templates = parse_templates()
    seen: set[str] = set()
    records = []
    for label in LABELS:
        # Dev templates go round-robin so every template appears in dev at least once.
        rounds = {k: cycle(rng, templates[label][k]) for k in "pm"}
        for slice_ in SLICES:
            kind = "m" if slice_ == "misleading" else "p"
            n = SLICE_COUNTS[slice_]
            for i in range(n):
                split = "dev" if i < n // 2 else "test"
                fixed = next(rounds[kind]) if split == "dev" else ""
                for _ in range(MAX_ATTEMPTS):
                    summary = fill(rng, fixed or pick(rng, templates[label][kind]))
                    message = compose(rng, label, slice_, summary)
                    key = " ".join(summary.lower().split())
                    if key not in seen and valid(label, slice_, message):
                        break
                else:
                    raise RuntimeError(
                        f"no valid {label}/{slice_} message after {MAX_ATTEMPTS} tries"
                    )
                seen.add(key)
                records.append(
                    {"message": message, "label": label, "split": split, "slice": slice_}
                )
    records = shuffled(rng, records)
    return [{"id": f"c{i:04d}", **rec} for i, rec in enumerate(records, 1)]


def serialise(records: Sequence[dict[str, str]]) -> bytes:
    lines = (json.dumps(rec, sort_keys=True, ensure_ascii=True) for rec in records)
    return ("\n".join(lines) + "\n").encode("ascii")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate_dataset.py", description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    parser.add_argument("--out", required=True, help="output file")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.is_dir():
        print(f"error: --out is a directory: {args.out}", file=sys.stderr)
        return 1
    try:
        records = generate(args.seed)
        write_atomic(out, serialise(records))
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
