"""End-to-end tests of `commit-kind eval` on fixture files in tmp_path (real metric computation)."""

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from _evalfixtures import (
    KEYWORDS,
    PROPOSAL,
    all_metrics,
    baseline_dict,
    dataset_text,
    oracle,
    pick,
    scripted,
    standard_records,
    with_errors,
    write_case,
)
from commit_kind.cli import main
from commit_kind.evaluate import METRICS, Record, canonical_json
from commit_kind.labels import LABELS
from commit_kind.strategies import REGISTRY, StrategyFactory

ROOT = Path(__file__).resolve().parents[1]


def run_cli(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    rc = main(["eval", *args])
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def sha_of(records: list[Record]) -> str:
    return hashlib.sha256(dataset_text(records).encode("utf-8")).hexdigest()


def controls_case(
    tmp_path: Path,
    records: list[Record] | None = None,
    thresholds: Mapping[str, float] = PROPOSAL,
    finished: Sequence[str] = ("B1", "B2"),
) -> Path:
    rows = standard_records() if records is None else records
    baseline = baseline_dict(sha_of(rows), {})
    return write_case(tmp_path, rows, thresholds=thresholds, baseline=baseline, finished=finished)


def classifier_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    records: list[Record],
    factory: StrategyFactory,
    base: Mapping[str, float] | None = None,
) -> Path:
    monkeypatch.setitem(REGISTRY, "scripted", factory)
    baseline = baseline_dict(sha_of(records), {"scripted": dict(base or all_metrics(0.0))})
    return write_case(tmp_path, records, classifier="scripted", baseline=baseline)


def failures_of(out: str) -> set[tuple[str, str | None]]:
    data = json.loads(out)
    return {(f["kind"], f["metric"]) for f in data["failures"]}


# ---------------------------------------------------------------- controls only (pre-B4 state)


def test_controls_only_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path)
    rc, out, err = run_cli(capsys, "--config", str(config))
    assert rc == 0, out + err
    assert "controls only" in out
    assert "eval passed" in out
    for name in ("majority", "keyword_spam", "random"):
        assert name in out


def test_default_config_path_is_relative_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "evals").mkdir()
    controls_case(tmp_path / "evals")
    monkeypatch.chdir(tmp_path)
    rc, out, _ = run_cli(capsys)
    assert rc == 0
    assert "eval passed" in out


# ------------------------------------------------ one failing and one passing fixture per metric


def make_wrong(
    records: list[Record], moves: list[tuple[str, str, str | None, int, str]]
) -> dict[str, str]:
    """moves: (true label, wrong label, slice or None, count, split=test) -> {record id: label}."""
    wrong: dict[str, str] = {}
    for label, to, slice_, count, _ in moves:
        for rec in pick(records, "test", label, slice_)[:count]:
            wrong[rec.id] = to
    return wrong


def test_fx_accuracy_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    # 10 wrong: two per label for five labels, on prefixed and plain rows -> accuracy 0.8333
    wrong = make_wrong(records, [(label, "chore", "prefixed", 2, "test") for label in LABELS[:5]])
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    assert ("below_threshold", "accuracy") in failures_of(out)
    assert json.loads(out)["strategies"]["scripted"]["metrics"]["accuracy"] == 0.8333


def test_fx_macro_f1_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    wrong = make_wrong(
        records, [("feat", "chore", None, 6, "test"), ("docs", "chore", None, 4, "test")]
    )
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    assert ("below_threshold", "macro_f1") in failures_of(out)
    assert json.loads(out)["strategies"]["scripted"]["metrics"]["macro_f1"] < 0.85


def test_fx_min_recall_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    wrong = make_wrong(records, [("chore", "fix", "prefixed", 4, "test")])
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    assert failures_of(out) == {("below_threshold", "min_recall")}
    metrics = json.loads(out)["strategies"]["scripted"]["metrics"]
    assert metrics["min_recall"] == 0.6
    assert metrics["accuracy"] == 0.9333
    assert metrics["misleading_accuracy"] == 1.0


def test_fx_misleading_low(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    # 6 of 18 misleading rows wrong, one per label, each moved to the next label
    wrong = make_wrong(
        records,
        [(label, LABELS[(i + 1) % 6], "misleading", 1, "test") for i, label in enumerate(LABELS)],
    )
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    assert failures_of(out) == {("below_threshold", "misleading_accuracy")}
    metrics = json.loads(out)["strategies"]["scripted"]["metrics"]
    assert metrics["misleading_accuracy"] == 0.6667
    assert metrics["accuracy"] == 0.9
    assert metrics["min_recall"] == 0.9


def test_oracle_passes_every_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    config = classifier_case(tmp_path, monkeypatch, records, oracle(records))
    rc, out, err = run_cli(capsys, "--config", str(config))
    assert rc == 0, out + err
    assert "eval passed" in out


def test_fx_keyword_friendly_makes_keyword_spam_too_lenient(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records(message_for={label: KEYWORDS[label][0] for label in LABELS})
    config = controls_case(tmp_path, records)
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    data = json.loads(out)
    lenient = [f for f in data["failures"] if f["kind"] == "too_lenient"]
    assert {f["strategy"] for f in lenient} == {"keyword_spam"}
    assert {f["metric"] for f in lenient} == set(METRICS)
    assert data["strategies"]["keyword_spam"]["metrics"]["accuracy"] == 1.0
    assert data["ok"] is False


def test_fx_lenient_thresholds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path, thresholds={m: 0.10 for m in METRICS})
    rc, out, _ = run_cli(capsys, "--config", str(config))
    assert rc == 1
    assert "metric accuracy too lenient: control majority reaches 0.1667 >= 0.1000" in out
    assert "metric misleading_accuracy too lenient: control majority reaches 0.1667" in out


def test_classifier_required_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path, finished=("B1", "B2", "B4"))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 1
    assert ("classifier_required", None) in failures_of(out)


# ---------------------------------------------------------------- input errors (exit 3)


def test_missing_dataset_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path)
    (tmp_path / "commits.jsonl").unlink()
    rc, out, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert out == ""
    assert "dataset not found" in err
    assert "generate_dataset.py" in err


def test_missing_config_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, _, err = run_cli(capsys, "--config", str(tmp_path / "nope.json"))
    assert rc == 3
    assert "config not found" in err


def test_missing_baseline_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = write_case(tmp_path)
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "baseline not found" in err


def test_invalid_json_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "invalid JSON" in err


def edit_config(config: Path, change: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(config.read_text(encoding="utf-8"))
    change(data)
    config.write_text(canonical_json(data), encoding="utf-8")


def test_unknown_config_key_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path)
    edit_config(config, lambda c: c.update(thresholds_typo=1))
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "thresholds_typo" in err


def test_missing_control_in_config_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = controls_case(tmp_path)
    edit_config(config, lambda c: c["controls"].remove("random"))
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "random" in err


def test_threshold_out_of_range_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path)
    edit_config(config, lambda c: c["thresholds"].update(accuracy=1.5))
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "accuracy" in err


def test_schema_violation_exit_3_names_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = controls_case(tmp_path)
    data = tmp_path / "commits.jsonl"
    lines = data.read_text(encoding="utf-8").split("\n")
    lines[2] = lines[2].replace('"label": "feat"', '"label": "bogus"')
    data.write_text("\n".join(lines), encoding="utf-8")
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "commits.jsonl:3" in err
    assert "bogus" in err


def test_no_misleading_rows_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    records = [
        Record(r.id, r.message, r.label, r.split, "plain" if r.split == "test" else r.slice)
        if r.slice == "misleading"
        else r
        for r in standard_records()
    ]
    config = controls_case(tmp_path, records)
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "misleading" in err


def test_label_without_support_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    records = [r for r in standard_records() if not (r.split == "test" and r.label == "docs")]
    config = controls_case(tmp_path, records)
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "docs" in err


def test_invalid_prediction_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    bogus = scripted({r.message: "bogus" for r in records})
    config = classifier_case(tmp_path, monkeypatch, records, bogus)
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "scripted" in err
    assert "c0061" in err  # first test record


def test_predict_raises_exit_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    config = classifier_case(tmp_path, monkeypatch, records, scripted({}))
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert "scripted" in err
    assert "c0061" in err
    assert "KeyError" in err


@pytest.mark.parametrize("name", ["majority", "not_registered"])
def test_bad_classifier_name_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    records = standard_records()
    config = write_case(
        tmp_path, records, classifier=name, baseline=baseline_dict(sha_of(records), {})
    )
    rc, _, err = run_cli(capsys, "--config", str(config))
    assert rc == 3
    assert name in err


# ---------------------------------------------------------------- usage errors (exit 2)


def test_show_errors_requires_dev(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path)
    rc, out, err = run_cli(capsys, "--config", str(config), "--show-errors")
    assert rc == 2
    assert out == ""
    assert "--split dev" in err


def test_write_baseline_with_dev_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = controls_case(tmp_path)
    before = config.read_bytes()
    rc, _, _ = run_cli(
        capsys, "--config", str(config), "--split", "dev", "--write-baseline", "--block", "B3"
    )
    assert rc == 2
    assert config.read_bytes() == before


@pytest.mark.parametrize(
    "args",
    [
        ["--block", "B3"],
        ["--reason", "why"],
        ["--write-baseline"],
        ["--write-baseline", "--block", "three"],
    ],
)
def test_flag_combinations_are_usage_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    config = controls_case(tmp_path)
    rc, _, _ = run_cli(capsys, "--config", str(config), *args)
    assert rc == 2


def test_unknown_split_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["eval", "--split", "train"])
    assert info.value.code == 2
    capsys.readouterr()


# ---------------------------------------------------------------- dev view


def test_dev_split_is_informational(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = controls_case(tmp_path, thresholds={m: 0.10 for m in METRICS})
    (tmp_path / "baseline.json").unlink()  # a dev run compares nothing and needs no baseline
    rc, out, _ = run_cli(capsys, "--config", str(config), "--split", "dev")
    assert rc == 0
    assert "informational: dev split, not gated" in out
    assert "eval failed" not in out


def test_show_errors_lists_dev_records_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    dev_ids = {r.id for r in records if r.split == "dev"}
    wrong = {r.id: "chore" for r in records if r.label == "feat"}  # dev and test rows wrong
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--split", "dev", "--show-errors")
    assert rc == 0
    listed = re.findall(r"^  (c\d{4}) expected", out, flags=re.M)
    assert len(listed) == 10
    assert set(listed) <= dev_ids


# ---------------------------------------------------------------- output


def test_json_output_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    config = classifier_case(tmp_path, monkeypatch, records, oracle(records))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    data = json.loads(out)
    assert rc == 0
    assert out == canonical_json(data)
    assert set(data) == {
        "split",
        "dataset",
        "thresholds",
        "thresholds_status",
        "classifier",
        "strategies",
        "failures",
        "ok",
    }
    assert set(data["dataset"]) == {"path", "sha256", "records", "evaluated"}
    assert data["dataset"]["records"] == 120
    assert data["dataset"]["evaluated"] == 60
    assert data["classifier"] == "scripted"
    assert set(data["strategies"]) == {"keyword_spam", "majority", "random", "scripted"}
    assert set(data["strategies"]["majority"]) == {"role", "metrics", "pass"}
    assert data["ok"] is True
    assert data["failures"] == []
    (tmp_path / "bad").mkdir()
    bad = controls_case(tmp_path / "bad", thresholds={m: 0.10 for m in METRICS})
    rc2, out2, _ = run_cli(capsys, "--config", str(bad), "--json")
    data2 = json.loads(out2)
    assert rc2 == 1
    assert data2["ok"] is False
    assert set(data2["failures"][0]) == {"kind", "strategy", "metric", "value", "limit", "message"}


def test_values_rounded_in_json_and_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    wrong = make_wrong(records, [("fix", "docs", None, 3, "test")])
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, out, _ = run_cli(capsys, "--config", str(config), "--json")
    assert rc == 0
    assert re.findall(r"\d+\.\d{5,}", out) == []
    rc, _, _ = run_cli(capsys, "--config", str(config), "--write-baseline", "--block", "B4")
    assert rc == 0
    text = (tmp_path / "baseline.json").read_text(encoding="utf-8")
    assert re.findall(r"\d+\.\d{5,}", text) == []
    for entry in json.loads(text)["strategies"].values():
        for value in entry.values():
            assert value == round(value, 4)


# ---------------------------------------------------------------- baseline writing


def test_write_baseline_first_time_and_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    config = write_case(tmp_path, records)
    args = ("--config", str(config), "--write-baseline", "--block", "B3")
    rc, out, err = run_cli(capsys, *args, "--reason", "initial baseline, controls only")
    assert rc == 0, out + err
    baseline_path = tmp_path / "baseline.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline_path.read_text(encoding="utf-8") == canonical_json(data)
    assert data["written_for_block"] == "B3"
    assert data["split"] == "test"
    assert data["dataset"] == {"records": 120, "sha256": sha_of(records)}
    assert data["notes"] == [{"block": "B3", "reason": "initial baseline, controls only"}]
    assert set(data["strategies"]) == {"keyword_spam", "majority", "random"}
    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["finished_blocks"] == ["B1", "B2", "B3"]
    assert config.read_text(encoding="utf-8") == canonical_json(saved)
    # idempotent: a second write appends nothing to finished_blocks and no note
    rc, _, _ = run_cli(capsys, *args)
    assert rc == 0
    assert json.loads(config.read_text(encoding="utf-8"))["finished_blocks"] == ["B1", "B2", "B3"]
    assert len(json.loads(baseline_path.read_text(encoding="utf-8"))["notes"]) == 1
    rc, out, _ = run_cli(capsys, "--config", str(config))
    assert rc == 0
    assert "eval passed" in out


def test_write_baseline_refuses_on_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = write_case(tmp_path, thresholds={m: 0.10 for m in METRICS})
    before = config.read_bytes()
    rc, out, err = run_cli(capsys, "--config", str(config), "--write-baseline", "--block", "B3")
    assert rc == 1
    assert "too lenient" in out
    assert "baseline not written" in err
    assert config.read_bytes() == before
    assert not (tmp_path / "baseline.json").exists()


def test_write_baseline_regression_needs_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    wrong = make_wrong(
        records, [("feat", "fix", "prefixed", 1, "test"), ("docs", "fix", "prefixed", 1, "test")]
    )
    config = classifier_case(
        tmp_path, monkeypatch, records, with_errors(records, wrong), base=all_metrics(1.0)
    )
    baseline_path = tmp_path / "baseline.json"
    before = (config.read_bytes(), baseline_path.read_bytes())
    args = ("--config", str(config), "--write-baseline", "--block", "B4")
    rc, out, err = run_cli(capsys, *args)
    assert rc == 1
    assert "below_baseline" in out
    assert "--reason" in err
    assert (config.read_bytes(), baseline_path.read_bytes()) == before
    rc, out, err = run_cli(capsys, *args, "--reason", "rule merge costs two prefixed rows")
    assert rc == 0, out + err
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert data["notes"] == [{"block": "B4", "reason": "rule merge costs two prefixed rows"}]
    assert data["strategies"]["scripted"]["accuracy"] == 0.9667
    assert json.loads(config.read_text(encoding="utf-8"))["finished_blocks"] == ["B1", "B2", "B4"]
    rc, _, _ = run_cli(capsys, "--config", str(config))
    assert rc == 0


def test_write_baseline_refuses_below_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    records = standard_records()
    wrong = make_wrong(records, [("chore", "fix", "prefixed", 4, "test")])
    config = classifier_case(tmp_path, monkeypatch, records, with_errors(records, wrong))
    rc, _, err = run_cli(
        capsys, "--config", str(config), "--write-baseline", "--block", "B4", "--reason", "x"
    )
    assert rc == 1
    assert "baseline not written" in err


# ---------------------------------------------------------------- process level


def test_module_entry_eval_subprocess(tmp_path: Path) -> None:
    config = controls_case(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "commit_kind", "eval", "--config", str(config)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "eval passed" in proc.stdout


def test_eval_modules_stdlib_only() -> None:
    allowed = {
        "argparse",
        "hashlib",
        "json",
        "os",
        "random",
        "re",
        "sys",
        "tempfile",
        "collections",
        "dataclasses",
        "pathlib",
        "typing",
        "commit_kind",
    }
    for name in ("evaluate.py", "strategies.py", "labels.py"):
        tree = ast.parse((ROOT / "src" / "commit_kind" / name).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported <= allowed, (name, imported - allowed)
        assert not imported & {"socket", "urllib", "http"}


def test_registry_is_untouched_by_tests() -> None:
    assert "scripted" not in REGISTRY
