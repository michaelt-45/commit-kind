"""The rule engine: summary line -> prefix -> verb and object -> fallback."""

import re
from dataclasses import dataclass

from commit_kind.rules import BOUNDARY_WORDS, RULES, Rule

_PREFIX = re.compile(r"([A-Za-z]+)(?:\([^()\r\n]*\))?!?:(?=\s|$)")
_PUNCT = ".,;:!?\"'()[]`"


class EmptyMessageError(ValueError):
    """Raised for a message with no non-blank line."""


@dataclass(frozen=True)
class Classification:
    label: str
    rule: str
    evidence: str


def _rules(kind: str) -> list[Rule]:
    return [r for r in RULES if r.kind == kind]


def _hit(rule: Rule, token: str) -> bool:
    return any(token.startswith(w) if w.endswith("/") else token == w for w in rule.words)


def _objects(tokens: list[tuple[str, int, int]]) -> tuple[Rule, int] | None:
    """Best object rule among the tokens before the first boundary word."""
    phrase = []
    for tok in tokens:
        if tok[0] in BOUNDARY_WORDS:
            break
        phrase.append(tok)
    for rule in _rules("object"):
        hits = [t for t in phrase if _hit(rule, t[0])]
        if hits:
            return rule, hits[-1][2]
    return None


def classify(message: str) -> Classification:
    summary = next((ln.strip() for ln in message.splitlines() if ln.strip()), "")
    if not summary:
        raise EmptyMessageError("empty commit message")
    match = _PREFIX.match(summary)
    if match:
        for rule in _rules("prefix"):
            if match.group(1).lower() in rule.words:
                return Classification(rule.label, rule.id, match.group(0))
        summary = summary[match.end() :].strip()  # unknown type: classify the rest
    tokens = [
        (m.group().strip(_PUNCT).lower(), m.start(), m.end()) for m in re.finditer(r"\S+", summary)
    ]
    for rule in _rules("verb") + _rules("ambiguous"):
        for word in rule.words:
            n = len(word.split())
            if " ".join(t[0] for t in tokens[:n]) != word:
                continue
            found = _objects(tokens[n:]) if rule.kind == "ambiguous" else None
            end = tokens[n - 1][2]
            if found:
                rule, end = found
            return Classification(rule.label, rule.id, summary[tokens[0][1] : end])
    found = _objects(tokens)
    if found:
        return Classification(found[0].label, found[0].id, summary[: found[1]])
    fallback = _rules("fallback")[0]
    return Classification(fallback.label, fallback.id, "")
