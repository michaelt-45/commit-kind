"""The rule table: data only. Order matters; see classifier.py for how it is read."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str  # prefix | verb | ambiguous (label is the default) | object | fallback
    label: str
    words: tuple[str, ...]  # lowercase; a word ending in "/" matches as a path prefix


RULES: tuple[Rule, ...] = (
    # Conventional Commit types. perf is a code change that neither fixes nor adds;
    # style/build/ci are upkeep; a revert fixes or adds nothing.
    Rule("prefix.feat", "prefix", "feat", ("feat",)),
    Rule("prefix.fix", "prefix", "fix", ("fix",)),
    Rule("prefix.docs", "prefix", "docs", ("docs",)),
    Rule("prefix.refactor", "prefix", "refactor", ("refactor", "perf")),
    Rule("prefix.test", "prefix", "test", ("test",)),
    Rule("prefix.chore", "prefix", "chore", ("chore", "style", "build", "ci", "revert")),
    # Verbs that name the change by themselves.
    Rule(
        "verb.fix",
        "verb",
        "fix",
        ("prevent", "handle", "avoid", "guard against", "stop", "restore"),
    ),
    Rule(
        "verb.refactor",
        "verb",
        "refactor",
        (
            *("extract", "extracted", "inline", "split", "consolidate", "deduplicate"),
            *("rename", "renamed", "move", "moved", "simplify"),
            *("refactor", "refactored", "restructure", "reorganize", "optimize", "speed up"),
        ),
    ),
    Rule(
        "verb.chore",
        "verb",
        "chore",
        ("bump", "bumped", "pin", "regenerate", "tidy", "clean up", "cleanup"),
    ),
    Rule(
        "verb.docs",
        "verb",
        "docs",
        ("document", "clarify", "explain", "describe", "reword"),
    ),
    Rule("verb.test", "verb", "test", ("cover", "parametrize", "mock", "assert")),
    Rule(
        "verb.feat",
        "verb",
        "feat",
        ("introduce", "support", "allow", "enable", "expose", "provide", "implement"),
    ),
    # Verbs that need their object; the label is the default.
    Rule("ambiguous.add", "ambiguous", "feat", ("add", "adds", "added")),
    Rule("ambiguous.extend", "ambiguous", "feat", ("extend",)),
    Rule("ambiguous.fix", "ambiguous", "fix", ("fix", "fixed", "fixes", "correct")),
    Rule("ambiguous.remove", "ambiguous", "refactor", ("remove", "delete", "drop")),
    Rule("ambiguous.update", "ambiguous", "chore", ("update", "updated")),
    Rule("ambiguous.upgrade", "ambiguous", "chore", ("upgrade",)),
    Rule("ambiguous.write", "ambiguous", "docs", ("write", "wrote")),
    # Objects, in priority order: capabilities come last.
    Rule(
        "object.chore",
        "object",
        "chore",
        (
            *("dependency", "dependencies", "workflow", "lint", "pyproject.toml"),
            *("makefile", ".gitignore", "ci"),
        ),
    ),
    Rule(
        "object.test",
        "object",
        "test",
        ("test", "tests", "fixture", "fixtures", "coverage", "spec", "tests/"),
    ),
    Rule(
        "object.docs",
        "object",
        "docs",
        (
            *("readme", "docstring", "example", "changelog", "section", "notes", "intro"),
            *("guide", "description", "typo", "wording", "docs/"),
            *("spelling", "docs", "documentation", "docstrings", "examples"),
        ),
    ),
    Rule(
        "object.fix",
        "object",
        "fix",
        (
            *("crash", "hang", "leak", "race", "deadlock", "loop", "off-by-one"),
            *("error", "bug", "check"),
        ),
    ),
    Rule(
        "object.feat",
        "object",
        "feat",
        (
            "option",
            "flag",
            "subcommand",
            "setting",
            "mode",
            "format",
            "hook",
            "export",
            "iterator",
            "output",
        ),
    ),
    Rule("fallback", "fallback", "chore", ()),
)

# The object phrase of a summary ends at the first of these.
BOUNDARY_WORDS: tuple[str, ...] = (
    *("for", "to", "in", "on", "of", "from", "with", "after", "ahead", "following"),
    *("during", "per", "that", "when", "so", "by", "before", "into", "out", "since"),
)
