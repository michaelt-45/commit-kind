"""Eval strategies: the plug-in interface and the three negative controls.

A strategy sees only the message it predicts. Fitting data is the dev split, never test.
"""

import random
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

_TOKEN = re.compile(r"[a-z0-9]+")


class Strategy(Protocol):
    def predict(self, message: str) -> str:
        """Return one of LABELS."""
        ...


@dataclass(frozen=True)
class StrategyContext:
    dev_messages: tuple[str, ...]  # dev split only, never test
    dev_labels: tuple[str, ...]
    labels: tuple[str, ...]
    keywords: Mapping[str, tuple[str, ...]]  # from config
    seed: int


StrategyFactory = Callable[[StrategyContext], Strategy]

CONTROL_NAMES: tuple[str, ...] = ("majority", "keyword_spam", "random")


class _Majority:
    def __init__(self, label: str) -> None:
        self._label = label

    def predict(self, message: str) -> str:
        return self._label


def _majority(ctx: StrategyContext) -> Strategy:
    counts = Counter(ctx.dev_labels)
    # max() keeps the first maximum, so ties go to the first label in ctx.labels order.
    return _Majority(max(ctx.labels, key=lambda label: counts[label]))


class _KeywordSpam:
    def __init__(self, labels: tuple[str, ...], keywords: Mapping[str, tuple[str, ...]]) -> None:
        self._labels = labels
        self._keywords = {label: frozenset(keywords.get(label, ())) for label in labels}

    def predict(self, message: str) -> str:
        tokens = _TOKEN.findall(message.lower())
        hits = {
            label: sum(1 for t in tokens if t in self._keywords[label]) for label in self._labels
        }
        return max(self._labels, key=lambda label: hits[label])


def _keyword_spam(ctx: StrategyContext) -> Strategy:
    return _KeywordSpam(ctx.labels, ctx.keywords)


class _Random:
    def __init__(self, labels: tuple[str, ...], seed: int) -> None:
        self._labels = labels
        self._rng = random.Random(seed)

    def predict(self, message: str) -> str:
        return self._labels[self._rng.randrange(len(self._labels))]


def _random(ctx: StrategyContext) -> Strategy:
    return _Random(ctx.labels, ctx.seed)


REGISTRY: dict[str, StrategyFactory] = {
    "majority": _majority,
    "keyword_spam": _keyword_spam,
    "random": _random,
}
