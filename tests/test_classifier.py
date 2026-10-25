import time

import pytest

from commit_kind import Classification, EmptyMessageError, classify
from commit_kind.rules import RULES
from commit_kind.strategies import REGISTRY, StrategyContext

CASES = [
    ("feat: add x", "feat", "prefix.feat", "feat:"),
    ("fix: handle empty input", "fix", "prefix.fix", "fix:"),
    ("docs(readme): tweak", "docs", "prefix.docs", "docs(readme):"),
    ("refactor!: tidy up", "refactor", "prefix.refactor", "refactor!:"),
    ("test: more", "test", "prefix.test", "test:"),
    ("chore: stuff", "chore", "prefix.chore", "chore:"),
    ("Prevent a crash on start", "fix", "verb.fix", "Prevent"),
    ("Guard against a stale cache", "fix", "verb.fix", "Guard against"),
    ("Extract the loader into a helper", "refactor", "verb.refactor", "Extract"),
    ("Speed up the parser", "refactor", "verb.refactor", "Speed up"),
    ("Restructure the loader", "refactor", "verb.refactor", "Restructure"),
    ("Bump the pinned version", "chore", "verb.chore", "Bump"),
    ("Clean up the helpers", "chore", "verb.chore", "Clean up"),
    ("Clarify the retry policy", "docs", "verb.docs", "Clarify"),
    ("Correct the spelling in the comments", "docs", "object.docs", "Correct the spelling"),
    ("Cover the parser with checks", "test", "verb.test", "Cover"),
    ("Mock the clock in the worker tests", "test", "verb.test", "Mock"),
    ("Support JSON output", "feat", "verb.feat", "Support"),
    ("Implement retry with backoff", "feat", "verb.feat", "Implement"),
    ("Add a thing", "feat", "ambiguous.add", "Add"),
    ("Extend the thing", "feat", "ambiguous.extend", "Extend"),
    ("Fix the thing", "fix", "ambiguous.fix", "Fix"),
    ("Fixes #123", "fix", "ambiguous.fix", "Fixes"),
    ("Remove unused imports", "refactor", "ambiguous.remove", "Remove"),
    ("Update the parser", "chore", "ambiguous.update", "Update"),
    ("Upgrade the parser", "chore", "ambiguous.upgrade", "Upgrade"),
    ("Write the parser", "docs", "ambiguous.write", "Write"),
    ("Update dependencies", "chore", "object.chore", "Update dependencies"),
    ("Add a ci step", "chore", "object.chore", "Add a ci"),
    ("Add a regression test for the crash fix", "test", "object.test", "Add a regression test"),
    ("Update tests/helpers.py", "test", "object.test", "Update tests/helpers.py"),
    ("Typo in README", "docs", "object.docs", "Typo"),
    ("Update the docs", "docs", "object.docs", "Update the docs"),
    (
        "Fix typo and broken wording in the README",
        "docs",
        "object.docs",
        "Fix typo and broken wording",
    ),
    ("Resolve the hang", "fix", "object.fix", "Resolve the hang"),
    ("Add a resume mode to report the crash", "feat", "object.feat", "Add a resume mode"),
    ("Ändere die Ausgabe", "chore", "fallback", ""),
]


@pytest.mark.parametrize(("message", "label", "rule", "evidence"), CASES)
def test_rules(message: str, label: str, rule: str, evidence: str) -> None:
    assert classify(message) == Classification(label, rule, evidence)


def test_every_rule_tested() -> None:
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))
    assert {c[2] for c in CASES} == set(ids)


@pytest.mark.parametrize(
    ("message", "label", "rule"),
    [
        ("docs: fix a crash", "docs", "prefix.docs"),
        ("Update parser", "chore", "ambiguous.update"),
        ("fix: 修复崩溃", "fix", "prefix.fix"),
        ("perf: faster", "refactor", "prefix.refactor"),
        ("ci: pin", "chore", "prefix.chore"),
        ("wip: add a --json option", "feat", "object.feat"),
        ("wip:", "chore", "fallback"),
        ("\n\n  fix: skip blank lines\nfeat: body", "fix", "prefix.fix"),
        ("fix:nospace is not a prefix", "chore", "fallback"),
    ],
)
def test_ordering_and_edge_cases(message: str, label: str, rule: str) -> None:
    result = classify(message)
    assert (result.label, result.rule) == (label, rule)


def test_prefix_grammar_keeps_evidence_as_written() -> None:
    assert classify("FIX(Parser)!: x").evidence == "FIX(Parser)!:"


@pytest.mark.parametrize("message", ["", "  \n\t", "\n\n"])
def test_empty_message_raises(message: str) -> None:
    with pytest.raises(EmptyMessageError, match="empty commit message"):
        classify(message)


@pytest.mark.parametrize(
    ("message", "label"),
    [("fix: " + "a" * 100_000, "fix"), ("Add " + "word " * 50_000 + "option", "feat")],
)
def test_very_long_message_is_fast(message: str, label: str) -> None:
    start = time.perf_counter()
    assert classify(message).label == label
    assert time.perf_counter() - start < 3


def test_evidence_is_a_substring_and_result_is_frozen() -> None:
    for message, _, _, _ in CASES:
        result = classify(message)
        assert result.evidence == "" or result.evidence in message
    with pytest.raises(AttributeError):
        classify("fix: x").label = "feat"  # type: ignore[misc]


def test_registry_entry_predicts_the_label() -> None:
    ctx = StrategyContext((), (), (), {}, 0)
    strategy = REGISTRY["rules"](ctx)
    assert strategy.predict("fix: handle empty input") == "fix"
    with pytest.raises(EmptyMessageError):
        strategy.predict("")
