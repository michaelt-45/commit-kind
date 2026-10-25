"""Eval tests: strategies, metrics, gate and CLI on tmp_path fixtures."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _evalfixtures import THRESHOLDS, make_case
from commit_kind import evaluate
from commit_kind.cli import main
from commit_kind.labels import LABELS
from commit_kind.strategies import REGISTRY, StrategyContext


def ctx(dev: tuple[str, ...], msgs: tuple[str, ...] = (), seed: int = 1) -> StrategyContext:
    kw = {"fix": ("fix",), "docs": ("docs",)}
    return StrategyContext(msgs or ("x",) * len(dev), dev, LABELS, kw, seed)


def test_majority_uses_dev_and_breaks_ties_by_label_order() -> None:
    assert REGISTRY["majority"](ctx(("docs", "docs", "fix"))).predict("m") == "docs"
    assert REGISTRY["majority"](ctx(("fix", "docs"))).predict("m") == "fix"


def test_keyword_spam_counts_tokens_with_repetition() -> None:
    s = REGISTRY["keyword_spam"](ctx(()))
    assert s.predict("Fix the fix docs") == "fix"
    assert s.predict("fixture") == "feat"  # exact tokens; zero hits -> first label
    assert s.predict("fix docs") == "fix"  # tie -> first in LABELS order


def test_random_is_seeded() -> None:
    def seq(seed: int) -> list[str]:
        s = REGISTRY["random"](ctx((), seed=seed))
        return [s.predict("m") for _ in range(30)]

    assert seq(1) == seq(1) != seq(2)
    assert set(seq(1)) <= set(LABELS)


def test_metrics_hand_computed() -> None:
    gold = ["feat", "feat", "fix", "docs", "refactor", "test", "chore"]
    pred = ["feat", "fix", "fix", "docs", "refactor", "test", "feat"]
    m = evaluate.metrics(gold, pred, ["misleading"] + ["plain"] * 6)
    assert m["accuracy"] == round(5 / 7, 4)
    assert m["min_recall"] == 0.0  # chore never recovered
    assert m["misleading_accuracy"] == 1.0
    assert m["macro_f1"] == round((0.5 + 2 / 3 + 1 + 1 + 1 + 0) / 6, 4)


def ok(v: float) -> dict[str, float]:
    return {**THRESHOLDS, "accuracy": v}


@pytest.mark.parametrize("metric", sorted(THRESHOLDS))
def test_gate_boundary_per_metric(metric: str) -> None:
    ctrl = {c: dict.fromkeys(THRESHOLDS, 0.0) for c in ("majority", "keyword_spam", "random")}
    clf = dict(THRESHOLDS)
    cfg: dict[str, object] = {"classifier": "x", "thresholds": THRESHOLDS}
    base = {"x": dict(THRESHOLDS)}
    assert evaluate.gate(cfg, {**ctrl, "x": clf}, base) == []  # at threshold passes
    below = evaluate.gate(cfg, {**ctrl, "x": {**clf, metric: THRESHOLDS[metric] - 0.0001}}, base)
    assert any(f"below threshold: {metric}" in f for f in below)
    lenient = {**ctrl, "random": {**ctrl["random"], metric: THRESHOLDS[metric]}, "x": clf}
    assert any(f"too lenient: {metric}" in f for f in evaluate.gate(cfg, lenient, base))


def test_gate_baseline_and_rounding_246_of_291() -> None:
    assert 246 / 291 < 0.8454  # unrounded comparison would flag a false regression
    zero = dict.fromkeys(THRESHOLDS, 0.0)
    ctrl = {"majority": zero, "keyword_spam": zero, "random": zero}
    cfg: dict[str, object] = {"classifier": "x", "thresholds": dict.fromkeys(THRESHOLDS, 0.5)}
    raw = {**THRESHOLDS, "accuracy": 246 / 291}
    assert evaluate.gate(cfg, {**ctrl, "x": raw}, {"x": ok(0.8454)}) == []
    assert any(
        "below baseline" in f for f in evaluate.gate(cfg, {**ctrl, "x": raw}, {"x": ok(0.9)})
    )
    assert any("no baseline entry" in f for f in evaluate.gate(cfg, {**ctrl, "x": raw}, {}))
    assert evaluate.gate(cfg, {**ctrl, "x": raw}, None) == []  # writing: no baseline check


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    rc = main(["eval", *args])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_controls_only_and_classifier_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, classifier=False)
    rc, out, _ = run(capsys, "--config", str(cfg))
    assert rc == 0 and "controls only" in out and "eval passed" in out
    cfg = make_case(tmp_path, monkeypatch)
    rc, out, _ = run(capsys, "--config", str(cfg), "--json")
    data = json.loads(out)
    assert rc == 0 and data["ok"] and data["strategies"]["oracle"]["accuracy"] == 1.0


def spread(rows: list[tuple[str, int]], to: str = "chore") -> dict[tuple[str, int], str]:
    return {r: to for r in rows}


# (wrong predictions, threshold overrides, metric that must fail). Overrides keep the others lax.
LAX = {"accuracy": 0.3, "macro_f1": 0.3, "min_recall": 0.3, "misleading_accuracy": 0.3}
FAILING = {
    "accuracy": (spread([(lab, i) for lab in LABELS[:5] for i in (0, 1)]), {"accuracy": 0.85}),
    "macro_f1": (spread([(lab, i) for lab in LABELS[:3] for i in (0, 1, 2)]), {"macro_f1": 0.9}),
    "min_recall": (spread([("feat", i) for i in range(4)]), {"min_recall": 0.7}),
    "misleading_accuracy": (
        spread([(lab, i) for lab in LABELS[:3] for i in (7, 8)]),
        {"misleading_accuracy": 0.7},
    ),
}


@pytest.mark.parametrize("metric", sorted(FAILING))
def test_classifier_failing_each_metric(
    metric: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    wrong, override = FAILING[metric]
    cfg = make_case(tmp_path, monkeypatch, wrong=wrong, thresholds={**LAX, **override})
    rc, out, _ = run(capsys, "--config", str(cfg))
    assert rc == 1 and f"below threshold: {metric}" in out


def test_friendly_fixture_makes_keyword_spam_too_lenient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, friendly=True)
    rc, out, _ = run(capsys, "--config", str(cfg))
    assert rc == 1 and out.count("too lenient") == 4 and "control keyword_spam" in out


def test_below_baseline_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, wrong={("feat", 0): "fix"}, thresholds=LAX)
    rc, out, _ = run(capsys, "--config", str(cfg))
    assert rc == 1 and "below baseline: accuracy" in out and "below threshold" not in out


def test_write_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, baseline=None, wrong={("feat", 0): "fix"})
    rc, _, _ = run(capsys, "--config", str(cfg), "--write-baseline", "--block", "B3")
    assert rc == 0  # missing baseline file and missing classifier entry are fine here
    written = json.loads((tmp_path / "baseline.json").read_text())
    assert written["written_for_block"] == "B3" and set(written["strategies"]) >= {"oracle"}
    assert json.loads(cfg.read_text())["finished_blocks"] == ["B1", "B3"]
    assert main(["eval", "--config", str(cfg)]) == 0  # the new baseline gates the next run


def test_write_baseline_refuses_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, friendly=True, baseline=None)
    before = cfg.read_text()
    rc, _, _ = run(capsys, "--config", str(cfg), "--write-baseline", "--block", "B3")
    assert rc == 1 and cfg.read_text() == before and not (tmp_path / "baseline.json").exists()


def test_dev_split_is_informational(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, friendly=True, wrong={("feat", 0): "fix"})
    rc, out, _ = run(capsys, "--config", str(cfg), "--split", "dev")
    assert rc == 0 and "informational" in out  # controls would fail the gate; dev does not gate


@pytest.mark.parametrize(
    "args",
    [["--show-errors"], ["--write-baseline", "--split", "dev", "--block", "B3"], ["--block", "B3"],
     ["--write-baseline"], ["--show-errors", "--split", "dev", "--json"]],
)  # fmt: skip
def test_usage_errors_exit_2(
    args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    cfg = make_case(tmp_path, monkeypatch)
    assert run(capsys, "--config", str(cfg), *args)[0] == 2


def test_input_errors_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch)
    good = cfg.read_text()
    arg = ["--config", str(cfg)]
    (tmp_path / "baseline.json").write_text("{nope")
    assert run(capsys, *arg)[0] == 3  # bad baseline JSON
    (tmp_path / "baseline.json").unlink()
    assert run(capsys, *arg)[0] == 3  # missing baseline
    (tmp_path / "data.jsonl").unlink()
    rc, _, err = run(capsys, *arg)
    assert rc == 3 and "dataset not found" in err and "generate_dataset.py" in err
    cfg.write_text(good.replace('"thresholds"', '"thresholdz"'))
    assert run(capsys, *arg)[0] == 3  # missing key
    cfg.write_text(good.replace('"classifier": "oracle"', '"classifier": "majority"'))
    assert run(capsys, *arg)[0] == 3  # a control as classifier
    cfg.unlink()
    assert run(capsys, *arg)[0] == 3  # missing config


def test_bad_strategy_output_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = make_case(tmp_path, monkeypatch, wrong={("feat", 0): "nonsense"})
    rc, _, err = run(capsys, "--config", str(cfg))
    assert rc == 3 and "oracle" in err and "m0t0" in err


def test_module_entry_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = make_case(tmp_path, monkeypatch, classifier=False)
    env = {**os.environ, "PYTHONPATH": "src"}
    cmd = [sys.executable, "-m", "commit_kind", "eval", "--config", str(cfg)]
    done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0 and "eval passed" in done.stdout
