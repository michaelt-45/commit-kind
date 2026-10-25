"""The pure gate: one failing and one passing case per metric and per failure kind."""

import pytest

from _evalfixtures import PROPOSAL, all_metrics
from commit_kind.evaluate import METRICS, Baseline, Failure, gate

SHA = "a" * 64
LOW = 0.0001


def run_gate(
    controls: dict[str, dict[str, float]] | None = None,
    classifier: str | None = None,
    metrics: dict[str, float] | None = None,
    baseline: Baseline | None = None,
    sha: str = SHA,
    finished: tuple[str, ...] = ("B1", "B2"),
) -> list[Failure]:
    return gate(PROPOSAL, controls or {}, classifier, metrics, baseline, sha, finished, "B4")


def make_baseline(strategies: dict[str, dict[str, float]], sha: str = SHA) -> Baseline:
    return Baseline(
        records=120,
        sha256=sha,
        notes=(),
        split="test",
        strategies=strategies,
        written_for_block="B3",
    )


@pytest.mark.parametrize("metric", METRICS)
def test_below_threshold_per_metric(metric: str) -> None:
    ok = dict(PROPOSAL)
    assert run_gate(classifier="clf", metrics=ok) == []  # boundary inclusive
    bad = {**ok, metric: PROPOSAL[metric] - LOW}
    failures = run_gate(classifier="clf", metrics=bad)
    assert [(f.kind, f.metric) for f in failures] == [("below_threshold", metric)]


@pytest.mark.parametrize("metric", METRICS)
def test_too_lenient_per_metric(metric: str) -> None:
    below = {m: PROPOSAL[m] - LOW for m in METRICS}
    leaky = {**below, metric: PROPOSAL[metric]}  # exactly at the threshold
    failures = run_gate(controls={"majority": below, "keyword_spam": leaky, "random": below})
    assert [(f.kind, f.metric, f.strategy) for f in failures] == [
        ("too_lenient", metric, "keyword_spam")
    ]
    assert failures[0].message.startswith(f"metric {metric} too lenient: control keyword_spam")
    assert run_gate(controls={"majority": below, "keyword_spam": below, "random": below}) == []


def test_below_baseline() -> None:
    entry = {**all_metrics(0.95)}
    base = make_baseline({"clf": entry})
    worse = run_gate(classifier="clf", metrics=all_metrics(0.9), baseline=base)
    assert {(f.kind, f.metric) for f in worse} == {("below_baseline", m) for m in METRICS}
    assert run_gate(classifier="clf", metrics=all_metrics(0.95), baseline=base) == []


def test_missing_baseline_entry_fails_closed() -> None:
    base = make_baseline({"other": all_metrics(0.9)})
    failures = run_gate(classifier="clf", metrics=all_metrics(0.9), baseline=base)
    assert [f.kind for f in failures] == ["missing_baseline"]


def test_dataset_mismatch() -> None:
    base = make_baseline({"clf": all_metrics(0.9)}, sha="b" * 64)
    failures = run_gate(classifier="clf", metrics=all_metrics(0.9), baseline=base)
    assert [f.kind for f in failures] == ["dataset_mismatch"]


def test_classifier_required_after_block() -> None:
    failures = run_gate(finished=("B1", "B2", "B4"))
    assert [f.kind for f in failures] == ["classifier_required"]
    assert run_gate(finished=("B1", "B2", "B3")) == []


def test_all_failures_reported() -> None:
    bad = {**all_metrics(0.5)}
    lenient = all_metrics(0.95)
    base = make_baseline({"clf": all_metrics(0.9)}, sha="b" * 64)
    failures = run_gate(
        controls={"majority": lenient}, classifier="clf", metrics=bad, baseline=base
    )
    kinds = {f.kind for f in failures}
    assert kinds == {"too_lenient", "below_threshold", "below_baseline", "dataset_mismatch"}
    assert len(failures) == 4 + 4 + 4 + 1


def test_classifier_checks_skipped_without_baseline() -> None:
    assert run_gate(classifier="clf", metrics=all_metrics(0.9), baseline=None) == []
