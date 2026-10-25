#!/usr/bin/env python3
"""Generate the synthetic commit-message dataset (standard library only).

The output is seeded and byte-reproducible. Randomness comes only from
``random.Random.randrange`` through the helpers in ``Rng``; there are no sets
iterated anywhere, so the output does not depend on the hash seed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import tempfile
from collections.abc import Sequence
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

# Keyword contract shared with the eval. Tokens come from
# re.findall(r"[a-z0-9]+", message.lower()); a hit is a token equal to an entry.
CONTROL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "feat": (
        "feat",
        "feature",
        "add",
        "adds",
        "added",
        "new",
        "support",
        "implement",
        "introduce",
        "allow",
        "enable",
    ),
    "fix": (
        "fix",
        "fixes",
        "fixed",
        "bug",
        "bugfix",
        "crash",
        "error",
        "issue",
        "broken",
        "resolve",
        "typo",
        "regression",
    ),
    "docs": (
        "docs",
        "doc",
        "documentation",
        "readme",
        "comment",
        "comments",
        "docstring",
        "guide",
        "changelog",
        "example",
        "examples",
    ),
    "refactor": (
        "refactor",
        "refactoring",
        "rename",
        "renamed",
        "move",
        "moved",
        "extract",
        "simplify",
        "cleanup",
        "restructure",
    ),
    "test": (
        "test",
        "tests",
        "testing",
        "spec",
        "coverage",
        "fixture",
        "fixtures",
        "mock",
        "assert",
        "pytest",
    ),
    "chore": (
        "chore",
        "bump",
        "upgrade",
        "dependency",
        "dependencies",
        "deps",
        "ci",
        "build",
        "release",
        "version",
        "lint",
    ),
}

# ---------------------------------------------------------------------------
# Shared vocabulary (tuples only, never sets)
# ---------------------------------------------------------------------------

MODS = (
    "parser",
    "scheduler",
    "cache layer",
    "exporter",
    "config loader",
    "report writer",
    "retry policy",
    "tokenizer",
    "queue worker",
    "session store",
    "formatter",
    "importer",
    "validator",
    "router",
    "planner",
    "indexer",
    "log writer",
    "metrics collector",
    "archive reader",
    "batch runner",
    "template engine",
    "rate limiter",
    "job runner",
    "auth middleware",
    "upload handler",
    "search index",
    "diff engine",
    "path resolver",
    "event bus",
    "state machine",
)
SNAKES = (
    "parser",
    "scheduler",
    "cache",
    "exporter",
    "loader",
    "writer",
    "retry",
    "tokenizer",
    "worker",
    "store",
    "formatter",
    "importer",
    "validator",
    "router",
    "planner",
    "indexer",
)
FILES = tuple(f"src/{name}.py" for name in SNAKES)
CAPS = (
    "dry-run",
    "verbose",
    "quiet",
    "strict",
    "json",
    "summary",
    "watch",
    "limit",
    "dedupe",
    "color",
    "interactive",
    "parallel",
    "offline",
    "resume",
)
OPT_FORMS = (
    "a --{x} option",
    "a --{x} flag",
    "a {x} subcommand",
    "a {x} setting",
    "a {x} mode",
    "a {x} hook",
)
OPTS = tuple(form.replace("{x}", cap) for cap in CAPS for form in OPT_FORMS)
FMTS = ("JSON", "CSV", "YAML", "TSV", "Markdown", "NDJSON", "plain-text", "HTML")
ACTS = (
    "skip empty entries",
    "run in the background",
    "read from standard input",
    "limit its output",
    "use a custom delimiter",
    "write to a chosen directory",
    "batch its writes",
    "resume a partial run",
)
THINGS = (
    "the item count",
    "a progress hook",
    "per-stage timings",
    "the token stream",
    "a streaming iterator",
    "the raw record count",
)
FAILS = (
    "a crash",
    "a hang",
    "a memory leak",
    "a race condition",
    "an off-by-one error",
    "a wrong exit code",
    "a missing check",
    "an infinite loop",
    "a deadlock",
    "a stale cache entry",
)
BADS = (
    "an empty input",
    "a very long line",
    "a missing field",
    "duplicate keys",
    "a truncated file",
    "a zero value",
    "a negative offset",
    "a trailing comma",
    "a blank header",
)
CONDS = (
    "empty batches",
    "a cold start",
    "slow disks",
    "repeated calls",
    "large inputs",
    "nested groups",
)
GERUNDS = (
    "dropping the last record",
    "retrying forever",
    "ignoring the timeout",
    "writing partial files",
    "reading stale entries",
    "skipping blank lines",
)
FIXTHINGS = (
    "the default timeout",
    "the line ordering",
    "the trailing newline",
    "the exit status",
    "the original casing",
    "the sort order",
)
TOPICS = (
    "installation steps",
    "configuration keys",
    "retry behaviour",
    "output formats",
    "command-line options",
    "logging levels",
    "default values",
    "exit codes",
    "limits and defaults",
)
DOCNAMES = ("usage", "config", "exporter", "retries", "faq", "output", "architecture", "install")
SECTS = (
    "install section",
    "usage section",
    "options table",
    "quickstart",
    "troubleshooting section",
)
PIECES = (
    "the retry loop",
    "the path normalisation",
    "the header parsing",
    "the sorting logic",
    "the field lookup",
    "the option handling",
    "the batching code",
    "the output formatting",
)
RTHINGS = (
    "the helper functions",
    "the internal state variables",
    "the config keys",
    "the private attributes",
)
AXES = ("input sizes", "output formats", "locale settings", "line endings", "worker counts")
EDGES = ("boundary values", "empty-input paths", "retry limits", "ordering rules", "rounding rules")
DEPS = (
    "fastcodec",
    "yamlish",
    "pathkit",
    "retrylib",
    "jsonmend",
    "clipkit",
    "lockstep",
    "dateparse",
    "strutil",
    "tablefmt",
)
GENS = (
    "the lock file",
    "the generated schema stubs",
    "the lookup tables",
    "the icon sprites",
    "the sample data tables",
    "the shell completion files",
)
TOOLS = (
    ".gitignore",
    "the Makefile",
    "the pre-commit hooks",
    "the CI workflow",
    "the lint settings in pyproject.toml",
    "the editor config",
    "the dependency groups",
)
PYVERS = ("Python 3.12", "Python 3.13", "the supported Python range")
TASKS = (
    "cleaning caches",
    "formatting the sources",
    "checking the lock file",
    "starting a dev shell",
)
SCOPES = (
    "parser",
    "cli",
    "cache",
    "exporter",
    "config",
    "report",
    "retry",
    "tokenizer",
    "queue",
    "session",
    "formatter",
    "importer",
    "validator",
    "router",
    "planner",
    "indexer",
)

POOLS: dict[str, tuple[str, ...]] = {
    "mod": MODS,
    "snake": SNAKES,
    "file": FILES,
    "opt": OPTS,
    "fmt": FMTS,
    "act": ACTS,
    "thing": THINGS,
    "fail": FAILS,
    "bad": BADS,
    "cond": CONDS,
    "gerund": GERUNDS,
    "fixthing": FIXTHINGS,
    "topic": TOPICS,
    "doc": DOCNAMES,
    "sect": SECTS,
    "piece": PIECES,
    "rthing": RTHINGS,
    "axis": AXES,
    "edge": EDGES,
    "dep": DEPS,
    "gen": GENS,
    "tool": TOOLS,
    "pyver": PYVERS,
    "task": TASKS,
}

# ---------------------------------------------------------------------------
# Templates. PLAIN: full summaries (also the text of prefixed messages).
# SHORT: compact leading phrases for the misleading slice (a decoy tail follows).
# ---------------------------------------------------------------------------

PLAIN: dict[str, tuple[str, ...]] = {
    "feat": (
        "Add {opt} to the {mod}",
        "Introduce {opt} for the {mod}",
        "Support {fmt} output in the {mod}",
        "Allow the {mod} to {act}",
        "Enable {opt} on the {mod}",
        "Expose {thing} from the {mod}",
        "Provide {opt} for the {mod}",
        "Extend the {mod} with {opt}",
        "Added {fmt} export to the {mod}",
    ),
    "fix": (
        "Prevent {fail} when the {mod} gets {bad}",
        "Handle {bad} in the {mod}",
        "Avoid {fail} in the {mod} on {cond}",
        "Guard against {bad} in {file}",
        "Stop the {mod} from {gerund}",
        "Restore {fixthing} in the {mod}",
        "Fix {fail} in the {mod}",
        "Fixed {fail} in the {mod} on {cond}",
        "Fix {fail} when the {mod} gets {bad}",
    ),
    "docs": (
        "Document the {topic} of the {mod}",
        "Clarify the {topic} in the README",
        "Explain how the {mod} handles {bad}",
        "Describe the {topic} in docs/{doc}.md",
        "Reword the {topic} section of the guide",
        "Update the README section on the {mod}",
        "Write a docstring for the {mod} class",
        "Update the usage example for the {mod}",
        "Updated the {topic} section in docs/{doc}.md",
        "Extend the changelog entry for the {mod}",
    ),
    "refactor": (
        "Extract {piece} from the {mod} into a helper",
        "Inline {piece} in the {mod}",
        "Split {file} into smaller modules",
        "Consolidate duplicate helpers in {file}",
        "Deduplicate {piece} between the {mod} and the {mod2}",
        "Rename {rthing} in {file} for clarity",
        "Move {piece} out of the {mod}",
        "Simplify {piece} in the {mod}",
        "Extracted {piece} from the {mod}",
        "Consolidate {piece} into one function",
    ),
    "test": (
        "Cover {bad} in the {mod} with a test",
        "Cover the {mod} {edge} with tests",
        "Parametrize the {mod} tests over {axis}",
        "Write tests for the {mod}",
        "Write test cases for {bad} in the {mod}",
        "Extend tests/test_{snake}.py with more edge cases",
        "Update the {mod} fixtures to match the current schema",
        "Wrote tests for {bad} in the {mod}",
        "Write tests for the {mod} on {cond}",
    ),
    "chore": (
        "Bump {dep} to {ver}",
        "Pin {dep} to {ver} in pyproject.toml",
        "Regenerate {gen}",
        "Tidy {tool}",
        "Update {tool} for {pyver}",
        "Upgrade {dep} to {ver}",
        "Write a Makefile target for {task}",
        "Bumped {dep} to {ver}",
        "Update the {dep} dependency to {ver}",
    ),
}

SHORT: dict[str, tuple[str, ...]] = {
    "feat": (
        "Add {opt}",
        "Introduce {opt}",
        "Support {fmt} output",
        "Enable {opt}",
        "Expose {thing}",
        "Provide {opt}",
        "Added {opt}",
    ),
    "fix": (
        "Prevent {fail}",
        "Handle {bad}",
        "Guard against {bad}",
        "Fix {fail}",
        "Avoid {fail}",
        "Stop {gerund}",
        "Restore {fixthing}",
        "Fixed {fail}",
    ),
    "docs": (
        "Document the {topic}",
        "Clarify the {topic}",
        "Explain the {topic}",
        "Describe the {topic}",
        "Reword the {topic} section",
        "Update the README intro",
        "Updated the {topic} docs",
    ),
    "refactor": (
        "Extract {piece}",
        "Inline {piece}",
        "Simplify {piece}",
        "Deduplicate {piece}",
        "Rename {rthing}",
        "Consolidate {piece}",
        "Extracted {piece}",
    ),
    "test": (
        "Cover {bad}",
        "Write tests for the {mod}",
        "Parametrize the {mod} tests",
        "Write test cases for {bad}",
        "Extend the {mod} tests",
        "Update the {mod} fixtures",
        "Wrote tests for {bad}",
    ),
    "chore": (
        "Bump {dep} to {ver}",
        "Pin {dep} to {ver}",
        "Regenerate {gen}",
        "Tidy {tool}",
        "Update {tool}",
        "Upgrade {dep}",
        "Bumped {dep} to {ver}",
    ),
}

# Decoy tails per decoy label. Each reads after a leading phrase and also after "Done ".
TAILS: dict[str, tuple[str, ...]] = {
    "feat": (
        "for the new feature that adds JSON support",
        "ahead of the new feature to enable batching",
        "after the new feature added support for it",
        "for the feature we introduce and enable next",
        "for the new feature to implement later",
    ),
    "fix": (
        "after the crash and error fixes in the {mod}",
        "following the bug, crash and error reports",
        "to resolve the issue and the regression",
        "after the typo fixes and the bug reports",
        "for the broken bugfix in the {mod}",
    ),
    "docs": (
        "as described in the README, guide and docs",
        "after the changelog and documentation examples",
        "per the docstring and comment examples",
        "for the README and the docs guide",
        "following the guide, README and changelog",
    ),
    "refactor": (
        "after the refactor that moved and renamed the {mod}",
        "during the cleanup, rename and restructure",
        "following the refactoring, rename and move",
        "after the refactor, cleanup and restructure",
        "to simplify and extract the shared code",
    ),
    "test": (
        "after the pytest, mock and coverage changes",
        "to match the updated fixtures, mock and spec",
        "since the tests and fixtures assert the old output",
        "ahead of the pytest coverage and testing run",
        "for the spec and the test fixtures",
    ),
    "chore": (
        "for the release build and the version bump",
        "for the CI lint and build step",
        "ahead of the dependency upgrade and release",
        "after the deps bump and the version change",
        "for the chore that handles the CI deps",
    ),
}

# Misleading summaries whose own words carry the decoy (key: true label, decoy label).
SPECIALS: dict[tuple[str, str], tuple[str, ...]] = {
    ("docs", "fix"): (
        "Fix typo and broken wording in the README {sect}",
        "Fix typo and broken error wording in the {mod} docstring",
    ),
    ("docs", "test"): ("Update the README test and coverage notes for the {mod}",),
    ("docs", "chore"): ("Update the README build and release notes for the {mod}",),
    ("docs", "feat"): (
        "Reword the new feature description in the README",
        "Reword the new feature notes for the {mod} in the README",
    ),
    ("docs", "refactor"): (
        "Reword the move and rename notes in the README",
        "Reword the refactor notes for the {mod}",
    ),
    ("test", "fix"): (
        "Add a regression test for the crash fix in the {mod}",
        "Write a regression test for the bug and error in the {mod}",
    ),
    ("test", "feat"): (
        "Add tests for the new feature flag support in the {mod}",
        "Add tests for the new {opt}",
    ),
    ("test", "chore"): (
        "Update the CI test fixtures after the dependency upgrade",
        "Update the {mod} tests for the new CI build",
    ),
    ("test", "docs"): (
        "Write tests for the README and docs examples in the {mod}",
        "Write tests that check the README example for the {mod}",
    ),
    ("test", "refactor"): ("Update the tests after the refactor and rename in the {mod}",),
    ("feat", "chore"): (
        "Introduce {opt} for the release and build commands",
        "Add {opt} to print the version and release info",
    ),
    ("feat", "fix"): ("Add {opt} to report the crash and error state",),
    ("feat", "docs"): ("Add {opt} that prints the README and guide text",),
    ("feat", "test"): ("Add {opt} to run the spec and fixtures",),
    ("feat", "refactor"): ("Introduce {opt} and rename the move helpers",),
    ("fix", "chore"): (
        "Prevent the release build from hanging on a missing version file",
        "Handle a missing version in the release build of the {mod}",
    ),
    ("fix", "test"): ("Handle a missing fixture file in the {mod} spec",),
    ("fix", "docs"): ("Stop the {mod} from ignoring the README comment settings",),
    ("fix", "feat"): ("Prevent the new feature flag from hanging the {mod}",),
    ("fix", "refactor"): ("Handle the moved and renamed paths in the {mod}",),
    ("refactor", "fix"): (
        "Extract the error and crash handling into a helper",
        "Extract the error and crash handling from the {mod}",
    ),
    ("refactor", "test"): ("Extract the test helpers from the {mod} spec",),
    ("refactor", "docs"): ("Extract the README and guide snippets into a helper",),
    ("refactor", "chore"): ("Extract the version and build logic from the {mod}",),
    ("refactor", "feat"): ("Split the new feature code out of the {mod}",),
    ("chore", "test"): ("Regenerate the lock file after the pytest and coverage changes",),
    ("chore", "fix"): ("Pin {dep} to {ver} after the crash and regression",),
    ("chore", "docs"): (
        "Tidy the README and changelog",
        "Tidy the README, changelog and docs index",
    ),
    ("chore", "feat"): ("Bump {dep} to {ver} for the new feature support",),
    ("chore", "refactor"): ("Regenerate the lock file after the refactor and rename",),
}

BODIES: dict[str, tuple[str, ...]] = {
    "feat": (
        "This makes the behaviour configurable from the command line.",
        "The default stays the same, so existing callers are unaffected.",
        "Requested by several users of the batch workflow.",
        "The option is off unless it is switched on explicitly.",
        "Output stays stable when the option is not used.",
        "Keeps the public interface small and easy to extend.",
        "Works together with the existing output settings.",
        "Disabled by default to keep today's behaviour.",
    ),
    "fix": (
        "The problem showed up on inputs that were empty or very large.",
        "It only happened on the second call, never on the first.",
        "The old code assumed the value was always set.",
        "Found while running the batch job against a large archive.",
        "Behaviour for well-formed input is unchanged.",
        "The failure was easy to reproduce with a truncated file.",
        "Callers now get a clear message instead of a stack trace.",
        "Seen twice in long runs before it was tracked down.",
    ),
    "docs": (
        "The old text did not match what the code actually does.",
        "Readers kept asking about this, so it is now written down.",
        "Wording follows the style used in the rest of the guide.",
        "No code changes in this commit.",
        "Short and to the point, with one concrete case per section.",
        "Links between the sections were tightened up.",
        "Terminology is now consistent across the pages.",
    ),
    "refactor": (
        "No behaviour change intended.",
        "The same logic now lives in one place instead of three.",
        "Makes the next change in this area much smaller.",
        "Names now say what the code does, not how it got here.",
        "Public interfaces are untouched.",
        "The helpers are small enough to read in one go.",
        "Control flow is flatter, with fewer nested branches.",
    ),
    "test": (
        "These cases run in well under a second.",
        "Each case states its expectation in one line.",
        "Inputs are small and built inline, with no files on disk.",
        "Covers the paths that were only exercised by accident before.",
        "No network or clock access, so the runs are repeatable.",
        "Names describe the situation under check.",
    ),
    "chore": (
        "Routine maintenance, no change to behaviour.",
        "Keeps the tooling in line with the supported Python range.",
        "Nothing in the public interface is touched.",
        "Done as a separate commit so it is easy to revert.",
        "Checked locally before committing.",
        "Part of the regular upkeep of the project.",
    ),
}

BREAKING = (
    "the default output format is now JSON",
    "the --strict mode is on by default",
    "callers must pass the config path explicitly",
    "the old retry settings are no longer read",
)

# Held-out vocabulary: only test records use these. "tokens" are distinctive
# (found in no shared pool, template or filler). "slot" is the index within the
# test half of the (label, slice) group. Roles: "secondary" = a shared
# unambiguous verb carries the label; "primary" = the held-out noun decides.
HELDOUT: dict[str, list[dict[str, str]]] = {
    "feat": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Provide a lockfree fast path for the {mod}",
            "tokens": "lockfree",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Add a plugin slot to the {mod}",
            "tokens": "plugin slot",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Expose per-shard counters from the {mod}",
            "tokens": "shard counters",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Allow the {mod} to coalesce writes",
            "tokens": "coalesce",
        },
    ],
    "fix": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Prevent a torn read in the {mod}",
            "tokens": "torn",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Fix a livelock in the {mod}",
            "tokens": "livelock",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Handle a poisoned lock in the {mod}",
            "tokens": "poisoned",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Guard against clock skew in the {mod}",
            "tokens": "skew",
        },
    ],
    "docs": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Document the glossary used by the {mod}",
            "tokens": "glossary",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Write a runbook for the {mod}",
            "tokens": "runbook",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Clarify the migration notes for the {mod}",
            "tokens": "migration",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Explain the pagination limits of the {mod}",
            "tokens": "pagination",
        },
    ],
    "refactor": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Deduplicate the marshalling code in the {mod}",
            "tokens": "marshalling",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Untangle the callback chain in the {mod}",
            "tokens": "untangle callback",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Consolidate the retry shims in the {mod}",
            "tokens": "shims",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Simplify the visitor plumbing in the {mod}",
            "tokens": "visitor plumbing",
        },
    ],
    "test": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Cover the leap year cases in the {mod}",
            "tokens": "leap",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Extend the snapshot cases for the {mod}",
            "tokens": "snapshot",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Parametrize the {mod} tests over timezones",
            "tokens": "timezones",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Cover the bidi handling in the {mod}",
            "tokens": "bidi",
        },
    ],
    "chore": [
        {
            "role": "secondary",
            "slice": "plain",
            "slot": "0",
            "template": "Tidy the devcontainer setup",
            "tokens": "devcontainer",
        },
        {
            "role": "primary",
            "slice": "plain",
            "slot": "1",
            "template": "Update the Dockerfile base image",
            "tokens": "dockerfile",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "0",
            "template": "Bump the bundled sqlite to {ver}",
            "tokens": "sqlite",
        },
        {
            "role": "secondary",
            "slice": "misleading",
            "slot": "1",
            "template": "Pin the nightly cron schedule",
            "tokens": "nightly cron",
        },
    ],
}

PLACEHOLDER = re.compile(r"\{([a-z0-9]+)\}")
TOKEN = re.compile(r"[a-z0-9]+")
PREFIX_LIKE = re.compile(r"^\s*[A-Za-z]+(\([^)]*\))?!?:\s")
PREFIX_STRIP = re.compile(r"^[a-z]+(\([^)]*\))?!?: ")
PREFIXED_SUMMARY = re.compile(r"^(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?!?: \S")
FORBIDDEN = ("@", "http", "www.", "signed-off-by", "co-authored-by", "/users/", "/home/")


class Rng:
    """Deterministic helpers built on randrange only."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def below(self, n: int) -> int:
        return self._rng.randrange(n)

    def pick(self, seq: Sequence[T]) -> T:
        return seq[self.below(len(seq))]

    def chance(self, num: int, den: int) -> bool:
        return self.below(den) < num

    def shuffle(self, items: list[T]) -> None:
        """Fisher-Yates, in place."""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]


def fill(rng: Rng, template: str) -> str:
    """Replace each {name} with a pool value; a trailing 2 forces a different value."""
    chosen: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "ver":
            value = f"{rng.below(5)}.{rng.below(15)}.{rng.below(10)}"
        elif name == "n":
            value = str(1 + rng.below(999))
        else:
            base = name.rstrip("2")
            value = rng.pick(POOLS[base])
            while name != base and value == chosen.get(base):
                value = rng.pick(POOLS[base])
        chosen[name] = value
        return value

    return PLACEHOLDER.sub(repl, template)


def keyword_hits(message: str) -> dict[str, int]:
    tokens = TOKEN.findall(message.lower())
    return {
        label: sum(1 for token in tokens if token in words)
        for label, words in CONTROL_KEYWORDS.items()
    }


def check_contract() -> None:
    if tuple(CONTROL_KEYWORDS) != LABELS:
        raise RuntimeError("keyword contract does not cover exactly the labels")
    seen: dict[str, str] = {}
    for label, words in CONTROL_KEYWORDS.items():
        for word in words:
            if word in seen:
                raise RuntimeError(f"keyword {word!r} is in both {seen[word]} and {label}")
            seen[word] = label
    if sum(SLICE_COUNTS.values()) != PER_LABEL:
        raise RuntimeError("slice counts do not add up to PER_LABEL")


def summary_key(message: str) -> str:
    first = message.split("\n", 1)[0]
    return " ".join(PREFIX_STRIP.sub("", first).lower().split())


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def body_lines(rng: Rng, label: str) -> list[str]:
    """About 30 % of messages get 1-3 sentences, one per line."""
    if not rng.chance(3, 10):
        return []
    pool = list(BODIES[label])
    lines: list[str] = []
    for _ in range(1 + rng.below(3)):
        lines.append(pool.pop(rng.below(len(pool))))
    return lines


def join_message(summary: str, body: Sequence[str], footer: Sequence[str]) -> str:
    parts = [summary]
    if body:
        parts.append("\n".join(body))
    if footer:
        parts.append("\n".join(footer))
    return "\n\n".join(parts)


def build_prefixed(rng: Rng, label: str) -> str:
    text = fill(rng, rng.pick(PLAIN[label]))
    if rng.chance(7, 10):
        text = lower_first(text)
    scope = f"({rng.pick(SCOPES)})" if rng.chance(1, 2) else ""
    bang = rng.chance(1, 10)
    summary = f"{label}{scope}{'!' if bang else ''}: {text}"
    body = body_lines(rng, label)
    footer: list[str] = []
    if bang and rng.chance(7, 10):
        footer = [f"BREAKING CHANGE: {rng.pick(BREAKING)}"]
    elif rng.chance(1, 5):
        footer = [rng.pick(("Refs: #{n}", "Closes #{n}")).replace("{n}", fill(rng, "{n}"))]
    return join_message(summary, body, footer)


def build_plain(rng: Rng, label: str, held: dict[str, str] | None) -> str:
    template = held["template"] if held else rng.pick(PLAIN[label])
    return join_message(fill(rng, template), body_lines(rng, label), [])


def attach_tail(lead: str, tail: str) -> tuple[str, list[str]]:
    """Put the tail on the summary line if it fits, else in a body sentence."""
    if len(lead) + 1 + len(tail) <= MAX_LINE:
        return f"{lead} {tail}", []
    return lead, [f"Done {tail}."]


def build_misleading(rng: Rng, label: str, index: int, held: dict[str, str] | None) -> str:
    others = [name for name in LABELS if name != label]
    decoy = others[(index + LABELS.index(label)) % len(others)]
    specials = SPECIALS.get((label, decoy), ())
    extra: list[str] = []
    if held is None and specials and rng.chance(2, 5):
        summary = fill(rng, rng.pick(specials))
    else:
        template = held["template"] if held else rng.pick(SHORT[label])
        lead = fill(rng, template)
        tail = fill(rng, rng.pick(TAILS[decoy]))
        summary, extra = attach_tail(lead, tail)
    return join_message(summary, extra + body_lines(rng, label), [])


def hygiene_ok(message: str) -> bool:
    if not message.isascii() or "\r" in message or "\t" in message:
        return False
    lowered = message.lower()
    if any(bad in lowered for bad in FORBIDDEN):
        return False
    return all(len(line) <= MAX_LINE and line == line.rstrip() for line in message.split("\n"))


def slice_ok(label: str, slice_name: str, message: str) -> bool:
    lines = message.split("\n")
    if slice_name == "prefixed":
        match = PREFIXED_SUMMARY.match(lines[0])
        return match is not None and match.group(1) == label
    if any(PREFIX_LIKE.match(line) for line in lines):
        return False
    hits = keyword_hits(message)
    foreign = [count for name, count in hits.items() if name != label]
    if slice_name == "plain":
        return max(foreign) == 0
    return max(foreign) > hits[label]


def build_unique(
    rng: Rng,
    seen: dict[str, bool],
    label: str,
    slice_name: str,
    index: int,
    held: dict[str, str] | None,
) -> str:
    for _ in range(MAX_ATTEMPTS):
        if slice_name == "prefixed":
            message = build_prefixed(rng, label)
        elif slice_name == "plain":
            message = build_plain(rng, label, held)
        else:
            message = build_misleading(rng, label, index, held)
        key = summary_key(message)
        if key in seen or not hygiene_ok(message) or not slice_ok(label, slice_name, message):
            continue
        seen[key] = True
        return message
    raise RuntimeError(f"no valid message for {label}/{slice_name} #{index} after retries")


def heldout_for(label: str, slice_name: str, split: str, slot: int) -> dict[str, str] | None:
    if split != "test":
        return None
    for entry in HELDOUT[label]:
        if entry["slice"] == slice_name and int(entry["slot"]) == slot:
            return entry
    return None


def validate(records: Sequence[dict[str, str]]) -> None:
    """Global self-check; raises RuntimeError on any violation."""
    if len(records) != PER_LABEL * len(LABELS):
        raise RuntimeError("wrong record count")
    for position, record in enumerate(records, start=1):
        if record["id"] != f"c{position:04d}":
            raise RuntimeError("ids are not contiguous")
    for label in LABELS:
        for slice_name in SLICES:
            for split in ("dev", "test"):
                n = sum(
                    1
                    for r in records
                    if r["label"] == label and r["slice"] == slice_name and r["split"] == split
                )
                if n != SLICE_COUNTS[slice_name] // 2:
                    raise RuntimeError(f"unbalanced group {label}/{slice_name}/{split}: {n}")
    keys: dict[str, bool] = {}
    for record in records:
        key = summary_key(record["message"])
        if key in keys:
            raise RuntimeError("duplicate summary")
        keys[key] = True
    for label in LABELS:
        for entry in HELDOUT[label]:
            for token in entry["tokens"].split():
                holders = [r for r in records if token in TOKEN.findall(r["message"].lower())]
                if len(holders) != 1 or holders[0]["split"] != "test":
                    raise RuntimeError(f"held-out token {token!r} leaks")
                if holders[0]["label"] != label or holders[0]["slice"] != entry["slice"]:
                    raise RuntimeError(f"held-out token {token!r} is in the wrong record")


def generate(seed: int) -> list[dict[str, str]]:
    check_contract()
    rng = Rng(seed)
    seen: dict[str, bool] = {}
    records: list[dict[str, str]] = []
    for label in LABELS:
        for slice_name in SLICES:
            count = SLICE_COUNTS[slice_name]
            half = count // 2
            for index in range(count):
                split = "dev" if index < half else "test"
                held = heldout_for(label, slice_name, split, index - half)
                message = build_unique(rng, seen, label, slice_name, index, held)
                records.append(
                    {
                        "id": "",
                        "message": message,
                        "label": label,
                        "split": split,
                        "slice": slice_name,
                    }
                )
    rng.shuffle(records)
    for position, record in enumerate(records, start=1):
        record["id"] = f"c{position:04d}"
    validate(records)
    return records


def serialise(records: Sequence[dict[str, str]]) -> bytes:
    lines = [json.dumps(record, sort_keys=True, ensure_ascii=True) for record in records]
    return ("\n".join(lines) + "\n").encode("ascii")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".commits-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_dataset.py",
        description="Write the synthetic commit-message dataset as JSON lines.",
    )
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
