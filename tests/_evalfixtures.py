"""Fixture builders for the eval tests: configs, datasets and baselines live in tmp_path only."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from commit_kind.evaluate import METRICS, Record, canonical_json
from commit_kind.labels import LABELS
from commit_kind.strategies import Strategy, StrategyContext, StrategyFactory

PROPOSAL: dict[str, float] = {
    "accuracy": 0.85,
    "macro_f1": 0.85,
    "min_recall": 0.7,
    "misleading_accuracy": 0.7,
}

KEYWORDS: dict[str, tuple[str, ...]] = {
    "feat": ("add", "introduce"),
    "fix": ("fix", "repair"),
    "docs": ("readme", "document"),
    "refactor": ("rename", "extract"),
    "test": ("tests", "coverage"),
    "chore": ("bump", "deps"),
}

SLICE_BY_INDEX = ("prefixed",) * 4 + ("plain",) * 3 + ("misleading",) * 3


def standard_records(
    per_label: int = 10, message_for: Mapping[str, str] | None = None
) -> list[Record]:
    """60 dev then 60 test records: per label 4 prefixed, 3 plain, 3 misleading (neutral text)."""
    records: list[Record] = []
    n = 0
    for split, word in (("dev", "alpha"), ("test", "omega")):
        for li, label in enumerate(LABELS):
            for i in range(per_label):
                n += 1
                text = f"note {word} {li}{i:02d}"
                if message_for is not None:
                    text = f"{message_for[label]} {text}"
                records.append(Record(f"c{n:04d}", text, label, split, SLICE_BY_INDEX[i]))
    return records


def pick(
    records: Sequence[Record], split: str, label: str, slice_: str | None = None
) -> list[Record]:
    return [
        r
        for r in records
        if r.split == split and r.label == label and (slice_ is None or r.slice == slice_)
    ]


def dataset_text(records: Sequence[Record]) -> str:
    lines = [
        json.dumps(
            {"id": r.id, "message": r.message, "label": r.label, "split": r.split, "slice": r.slice}
        )
        for r in records
    ]
    return "\n".join(lines) + "\n"


def config_dict(
    thresholds: Mapping[str, float] = PROPOSAL,
    classifier: str | None = None,
    finished: Sequence[str] = ("B1", "B2"),
    keywords: Mapping[str, Sequence[str]] = KEYWORDS,
    controls: Sequence[str] = ("keyword_spam", "majority", "random"),
) -> dict[str, object]:
    return {
        "baseline": "baseline.json",
        "classifier": classifier,
        "controls": list(controls),
        "dataset": "commits.jsonl",
        "finished_blocks": list(finished),
        "keyword_spam": {k: list(v) for k, v in keywords.items()},
        "random_seed": 20261025,
        "require_classifier_from_block": "B4",
        "thresholds": dict(thresholds),
        "thresholds_status": "proposal, approval open",
    }


def baseline_dict(
    sha256: str,
    strategies: Mapping[str, Mapping[str, float]],
    records: int = 120,
    block: str = "B3",
) -> dict[str, object]:
    return {
        "dataset": {"records": records, "sha256": sha256},
        "notes": [],
        "split": "test",
        "strategies": {n: dict(m) for n, m in strategies.items()},
        "written_for_block": block,
    }


def write_case(
    tmp_path: Path,
    records: Sequence[Record] | None = None,
    thresholds: Mapping[str, float] = PROPOSAL,
    classifier: str | None = None,
    baseline: Mapping[str, object] | None = None,
    finished: Sequence[str] = ("B1", "B2"),
    keywords: Mapping[str, Sequence[str]] = KEYWORDS,
) -> Path:
    """Write commits.jsonl, config.json (and baseline.json if given) in tmp_path; return config."""
    rows = standard_records() if records is None else records
    (tmp_path / "commits.jsonl").write_text(dataset_text(rows), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(
        canonical_json(config_dict(thresholds, classifier, finished, keywords)), encoding="utf-8"
    )
    if baseline is not None:
        (tmp_path / "baseline.json").write_text(canonical_json(baseline), encoding="utf-8")
    return config


class _Scripted:
    def __init__(self, predictions: Mapping[str, str]) -> None:
        self._predictions = predictions

    def predict(self, message: str) -> str:
        return self._predictions[message]


def scripted(predictions: Mapping[str, str]) -> StrategyFactory:
    """A strategy keyed by message (it ignores the context)."""

    def factory(ctx: StrategyContext) -> Strategy:
        return _Scripted(predictions)

    return factory


def oracle(records: Sequence[Record]) -> StrategyFactory:
    return scripted({r.message: r.label for r in records})


def with_errors(records: Sequence[Record], wrong: Mapping[str, str]) -> StrategyFactory:
    """Oracle except for the given record ids, which get the given wrong label."""
    return scripted({r.message: wrong.get(r.id, r.label) for r in records})


def all_metrics(value: float) -> dict[str, float]:
    return {m: value for m in METRICS}
