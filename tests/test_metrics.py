"""Metric arithmetic, test-split scoring and rounding."""

from pathlib import Path

from _evalfixtures import (
    PROPOSAL,
    all_metrics,
    oracle,
    pick,
    scripted,
    standard_records,
    write_case,
)
from commit_kind.evaluate import Baseline, Record, compute_metrics, gate, load_config, q, run_eval
from commit_kind.labels import LABELS
from commit_kind.strategies import REGISTRY


def _rows(spec: list[tuple[str, str, str]]) -> tuple[list[Record], list[str]]:
    rows = [Record(f"r{i}", f"m{i}", t, "test", s) for i, (t, _, s) in enumerate(spec)]
    return rows, [p for _, p, _ in spec]


def test_perfect_predictions(tmp_path: Path) -> None:
    records = standard_records()
    config = load_config(write_case(tmp_path, records, classifier="oracle"))
    registry = {**REGISTRY, "oracle": oracle(records)}
    run = run_eval(config, registry)
    assert run.results["oracle"].metrics == all_metrics(1.0)
    assert run.results["oracle"].role == "classifier"


def test_hand_computed_confusion() -> None:
    p, m = "prefixed", "misleading"
    rows, preds = _rows(
        [
            ("feat", "feat", p),
            ("feat", "feat", p),
            ("feat", "fix", m),
            ("fix", "fix", p),
            ("fix", "fix", p),
            ("docs", "docs", p),
            ("docs", "chore", m),
            ("refactor", "refactor", p),
            ("refactor", "feat", m),
            ("test", "test", p),
            ("test", "test", p),
            ("chore", "chore", m),
        ]
    )
    # correct 9 of 12; misleading rows: 1 of 4 correct
    # P: feat 2/3, fix 2/3, docs 1, refactor 1, test 1, chore 1/2
    # R: feat 2/3, fix 1, docs 1/2, refactor 1/2, test 1, chore 1
    # F1: 2/3, 4/5, 2/3, 2/3, 1, 2/3 -> mean 0.744444...
    assert compute_metrics(rows, preds) == {
        "accuracy": 0.75,
        "macro_f1": 0.7444,
        "min_recall": 0.5,
        "misleading_accuracy": 0.25,
    }


def test_f1_zero_when_label_never_predicted() -> None:
    spec: list[tuple[str, str, str]] = []
    for label in LABELS:
        pred = "feat" if label == "docs" else label
        spec.append((label, pred, "misleading"))
        spec.append((label, pred, "plain"))
    rows, preds = _rows(spec)
    # docs: never predicted, F1 0. feat: P 2/4, R 1 -> 2/3. Four labels perfect.
    metrics = compute_metrics(rows, preds)
    assert metrics["macro_f1"] == 0.7778
    assert metrics["min_recall"] == 0.0
    assert metrics["accuracy"] == 0.8333


def test_scores_test_split_only(tmp_path: Path) -> None:
    records = standard_records()
    right_on_test = {r.message: (r.label if r.split == "test" else "chore") for r in records}
    config = load_config(write_case(tmp_path, records, classifier="probe"))
    run = run_eval(config, {**REGISTRY, "probe": scripted(right_on_test)})
    assert run.results["probe"].metrics == all_metrics(1.0)
    assert len(run.evaluated) == len(pick(records, "test", "feat")) * len(LABELS)
    assert {r.split for r in run.evaluated} == {"test"}
    dev_run = run_eval(config, {**REGISTRY, "probe": scripted(right_on_test)}, split="dev")
    assert dev_run.results["probe"].metrics["accuracy"] == 0.1667


def test_rounding_246_of_291() -> None:
    rows = [
        Record(f"r{i}", f"m{i}", LABELS[i % 6], "test", ("prefixed", "plain", "misleading")[i % 3])
        for i in range(291)
    ]
    preds = [r.label for r in rows]
    for i in range(45):  # 45 wrong rows, spread over the labels: 246 correct
        preds[i] = LABELS[(LABELS.index(rows[i].label) + 1) % 6]
    metrics = compute_metrics(rows, preds)
    assert metrics["accuracy"] == 0.8454
    assert 246 / 291 < 0.8454  # comparing unrounded values would flag a false regression
    baseline = Baseline(
        records=291,
        sha256="s",
        notes=(),
        split="test",
        strategies={"clf": {**metrics, "accuracy": 0.8454}},
        written_for_block="B4",
    )
    failures = gate({m: 0.0 for m in PROPOSAL}, {}, "clf", metrics, baseline, "s", ("B1",), "B4")
    assert [f for f in failures if f.kind == "below_baseline"] == []
    assert q(246 / 291) == 0.8454
