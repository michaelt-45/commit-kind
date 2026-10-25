"""Fixture builder: config, dataset and baseline in tmp_path only (never the live files)."""

import json
from pathlib import Path

import pytest

from commit_kind.labels import LABELS
from commit_kind.strategies import REGISTRY, Strategy, StrategyContext

THRESHOLDS = {"accuracy": 0.85, "macro_f1": 0.85, "min_recall": 0.7, "misleading_accuracy": 0.7}
PERFECT = dict.fromkeys(THRESHOLDS, 1.0)


def make_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    friendly: bool = False,
    wrong: dict[tuple[str, int], str] | None = None,
    thresholds: dict[str, float] | None = None,
    classifier: bool = True,
    baseline: dict[str, float] | None = PERFECT,
) -> Path:
    """Test split: 10 per label (i >= 7 misleading), dev: 2 per label. Returns the config path.

    friendly: messages contain their own label, so keyword_spam is perfect.
    wrong: {(label, i): predicted label} overrides for the scripted "oracle" classifier.
    """
    recs, answers = [], {}
    for split, per_label in (("dev", 2), ("test", 10)):
        for li, lab in enumerate(LABELS):
            for i in range(per_label):
                msg = f"{lab + ' ' if friendly else ''}m{li}{split[0]}{i}"
                sl = "misleading" if i >= 7 or (split == "dev" and i == 1) else "plain"
                recs.append({"id": msg, "message": msg, "label": lab, "split": split, "slice": sl})
                answers[msg] = (wrong or {}).get((lab, i), lab) if split == "test" else lab
    (tmp_path / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))

    class Oracle:
        def predict(self, message: str) -> str:
            return answers[message]

    def factory(ctx: StrategyContext) -> Strategy:
        return Oracle()

    monkeypatch.setitem(REGISTRY, "oracle", factory)
    cfg = {
        "baseline": "baseline.json",
        "classifier": "oracle" if classifier else None,
        "controls": ["keyword_spam", "majority", "random"],
        "dataset": "data.jsonl",
        "finished_blocks": ["B1"],
        "keyword_spam": {lab: [lab] for lab in LABELS},
        "random_seed": 7,
        "thresholds": thresholds or THRESHOLDS,
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    if baseline is not None:
        data = {"strategies": {"oracle": baseline}, "written_for_block": "B1"}
        (tmp_path / "baseline.json").write_text(json.dumps(data))
    return tmp_path / "config.json"
