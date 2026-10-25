"""Eval strategies: the plug-in interface and the three negative controls (fitted on dev only)."""

import random
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


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


class _Fn:
    def __init__(self, fn: Callable[[str], str]) -> None:
        self._fn = fn

    def predict(self, message: str) -> str:
        return self._fn(message)


def _majority(ctx: StrategyContext) -> Strategy:
    counts = Counter(ctx.dev_labels)
    label = max(ctx.labels, key=lambda lab: counts[lab])  # ties: first in label order
    return _Fn(lambda message: label)


def _keyword_spam(ctx: StrategyContext) -> Strategy:
    words = {lab: set(ctx.keywords.get(lab, ())) for lab in ctx.labels}

    def predict(message: str) -> str:
        tokens = re.findall(r"[a-z0-9]+", message.lower())
        hits = {lab: sum(t in words[lab] for t in tokens) for lab in ctx.labels}
        return max(ctx.labels, key=lambda lab: hits[lab])  # ties and zero hits: first label

    return _Fn(predict)


def _random(ctx: StrategyContext) -> Strategy:
    rng = random.Random(ctx.seed)
    return _Fn(lambda message: ctx.labels[rng.randrange(len(ctx.labels))])


CONTROL_NAMES: tuple[str, ...] = ("majority", "keyword_spam", "random")
REGISTRY: dict[str, Callable[[StrategyContext], Strategy]] = {
    "majority": _majority,
    "keyword_spam": _keyword_spam,
    "random": _random,
}
