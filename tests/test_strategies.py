"""The three negative controls and the registry."""

import pytest

from commit_kind.labels import LABELS
from commit_kind.strategies import CONTROL_NAMES, REGISTRY, StrategyContext, StrategyFactory

KEYWORDS: dict[str, tuple[str, ...]] = {
    "feat": ("add", "new"),
    "fix": ("fix", "bug"),
    "docs": ("readme", "docs"),
    "refactor": ("rename", "extract"),
    "test": ("tests", "coverage"),
    "chore": ("bump", "deps"),
}


def ctx(
    dev_labels: tuple[str, ...] = ("docs", "docs", "fix"),
    seed: int = 7,
    keywords: dict[str, tuple[str, ...]] | None = None,
) -> StrategyContext:
    return StrategyContext(
        dev_messages=tuple(f"m{i}" for i in range(len(dev_labels))),
        dev_labels=dev_labels,
        labels=LABELS,
        keywords=KEYWORDS if keywords is None else keywords,
        seed=seed,
    )


def test_majority_uses_dev_only() -> None:
    seen: list[StrategyContext] = []
    real: StrategyFactory = REGISTRY["majority"]

    def spy(c: StrategyContext) -> object:
        seen.append(c)
        return real(c)

    dev = ("docs",) * 5 + ("fix",) * 2
    strategy = real(ctx(dev_labels=dev))
    assert strategy.predict("anything about fix") == "docs"
    spy(ctx(dev_labels=dev))
    # The context carries the dev split and nothing else.
    assert set(seen[0].__dataclass_fields__) == {
        "dev_messages",
        "dev_labels",
        "labels",
        "keywords",
        "seed",
    }
    assert seen[0].dev_labels == dev


def test_majority_tie_breaks_by_label_order() -> None:
    balanced = tuple(LABELS) * 3
    assert REGISTRY["majority"](ctx(dev_labels=balanced)).predict("x") == "feat"
    two_way = ("test", "chore", "test", "chore")
    assert REGISTRY["majority"](ctx(dev_labels=two_way)).predict("x") == "test"


def test_keyword_spam_counts_tokens_with_repetition() -> None:
    s = REGISTRY["keyword_spam"](ctx())
    assert s.predict("fix the fix docs") == "fix"
    assert s.predict("Docs docs: Fix") == "docs"
    # exact tokens only: "fixture" and "debugging" are not hits
    assert s.predict("fixture debugging readme") == "docs"
    assert s.predict("fixture bugfix") == "feat"


def test_keyword_spam_ties_and_zero_hits() -> None:
    s = REGISTRY["keyword_spam"](ctx())
    assert s.predict("bump readme fix") == "fix"  # tie of three: first in LABELS order
    assert s.predict("nothing relevant here") == "feat"  # zero hits: first label
    assert s.predict("") == "feat"


def test_random_is_seeded() -> None:
    def run(seed: int) -> list[str]:
        s = REGISTRY["random"](ctx(seed=seed))
        return [s.predict(f"m{i}") for i in range(200)]

    first = run(1)
    assert first == run(1)
    assert first != run(2)
    assert set(first) <= set(LABELS)
    assert set(first) == set(LABELS)  # 200 draws cover all six labels


def test_registry_contains_all_controls() -> None:
    assert CONTROL_NAMES == ("majority", "keyword_spam", "random")
    for name in CONTROL_NAMES:
        assert name in REGISTRY


def test_labels_fixed() -> None:
    assert LABELS == ("feat", "fix", "docs", "refactor", "test", "chore")


@pytest.mark.parametrize("name", CONTROL_NAMES)
def test_controls_return_labels(name: str) -> None:
    s = REGISTRY[name](ctx())
    assert s.predict("some message") in LABELS
