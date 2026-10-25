"""Gated eval: load and validate inputs, score strategies, apply the gate, render, write baselines.

Everything fails closed: a missing or invalid input is an InputError (exit 3), never a pass.
Every metric value goes through q() at storage, display and comparison.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from commit_kind.labels import LABELS
from commit_kind.strategies import CONTROL_NAMES, REGISTRY, StrategyContext, StrategyFactory

METRICS: tuple[str, ...] = ("accuracy", "macro_f1", "min_recall", "misleading_accuracy")
SPLITS: tuple[str, ...] = ("dev", "test")
GENERATE_HINT = "python3 scripts/generate_dataset.py --seed 20261025 --out data/commits.jsonl"
BLOCK_PATTERN = re.compile(r"^B\d+$")

Metrics = dict[str, float]


class InputError(Exception):
    """A missing or invalid config, dataset, baseline or strategy (exit code 3)."""


def q(x: float) -> float:
    return round(x, 4)


# --------------------------------------------------------------------------- data model


@dataclass(frozen=True)
class Record:
    id: str
    message: str
    label: str
    split: str
    slice: str


@dataclass(frozen=True)
class Config:
    path: Path
    baseline_ref: str
    classifier: str | None
    controls: tuple[str, ...]
    dataset_ref: str
    finished_blocks: tuple[str, ...]
    keywords: Mapping[str, tuple[str, ...]]
    random_seed: int
    require_classifier_from_block: str
    thresholds: Mapping[str, float]
    thresholds_status: str

    @property
    def dataset_path(self) -> Path:
        return self.path.parent / self.dataset_ref

    @property
    def baseline_path(self) -> Path:
        return self.path.parent / self.baseline_ref


@dataclass(frozen=True)
class Baseline:
    records: int
    sha256: str
    notes: tuple[tuple[str, str], ...]  # (block, reason)
    split: str
    strategies: Mapping[str, Mapping[str, float]]
    written_for_block: str


@dataclass(frozen=True)
class Failure:
    kind: str
    strategy: str
    metric: str | None
    value: float | None
    limit: float | None
    message: str


@dataclass(frozen=True)
class StrategyResult:
    role: str  # "control" or "classifier"
    metrics: Metrics
    predictions: tuple[str, ...]


@dataclass(frozen=True)
class EvalRun:
    split: str
    dataset_records: int
    dataset_sha256: str
    evaluated: tuple[Record, ...]
    results: Mapping[str, StrategyResult]  # controls in config order, then the classifier
    classifier: str | None


@dataclass(frozen=True)
class Report:
    run: EvalRun
    config: Config
    failures: tuple[Failure, ...] = field(default_factory=tuple)
    informational: bool = False

    @property
    def ok(self) -> bool:
        return not self.failures


# --------------------------------------------------------------------------- loading


def _fail(where: str, what: str) -> InputError:
    return InputError(f"{where}: {what}")


def _as_dict(obj: object, where: str) -> dict[str, object]:
    if not isinstance(obj, dict):
        raise _fail(where, "expected a JSON object")
    out: dict[str, object] = {}
    for key, value in obj.items():
        if not isinstance(key, str):
            raise _fail(where, "object keys must be strings")
        out[key] = value
    return out


def _exact_keys(d: Mapping[str, object], keys: Sequence[str], where: str) -> None:
    missing = sorted(set(keys) - set(d))
    unknown = sorted(set(d) - set(keys))
    if missing:
        raise _fail(where, f"missing key(s): {', '.join(missing)}")
    if unknown:
        raise _fail(where, f"unknown key(s): {', '.join(unknown)}")


def _str(obj: object, where: str) -> str:
    if not isinstance(obj, str):
        raise _fail(where, "expected a string")
    return obj


def _str_list(obj: object, where: str) -> tuple[str, ...]:
    if not isinstance(obj, list):
        raise _fail(where, "expected a list of strings")
    return tuple(_str(item, where) for item in obj)


def _number(obj: object, where: str) -> float:
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        raise _fail(where, "expected a number")
    return float(obj)


def _read_json(path: Path, what: str) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise InputError(f"{what} not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {what} {path}: {exc}") from None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}") from None


CONFIG_KEYS: tuple[str, ...] = (
    "baseline",
    "classifier",
    "controls",
    "dataset",
    "finished_blocks",
    "keyword_spam",
    "random_seed",
    "require_classifier_from_block",
    "thresholds",
    "thresholds_status",
)


def load_config(path: Path) -> Config:
    where = str(path)
    d = _as_dict(_read_json(path, "config"), where)
    _exact_keys(d, CONFIG_KEYS, where)
    classifier = None if d["classifier"] is None else _str(d["classifier"], f"{where}: classifier")
    controls = _str_list(d["controls"], f"{where}: controls")
    absent = [c for c in CONTROL_NAMES if c not in controls]
    if absent:
        raise _fail(
            where, f"controls must contain all of {', '.join(CONTROL_NAMES)}; missing {absent}"
        )
    if len(set(controls)) != len(controls) or set(controls) - set(CONTROL_NAMES):
        raise _fail(where, "controls must be exactly the three control names, once each")
    finished = _str_list(d["finished_blocks"], f"{where}: finished_blocks")
    for block in (*finished, _str(d["require_classifier_from_block"], where)):
        if not BLOCK_PATTERN.match(block):
            raise _fail(where, f"bad block name {block!r}")
    kw_raw = _as_dict(d["keyword_spam"], f"{where}: keyword_spam")
    _exact_keys(kw_raw, LABELS, f"{where}: keyword_spam")
    keywords = {
        label: _str_list(kw_raw[label], f"{where}: keyword_spam.{label}") for label in LABELS
    }
    seed = d["random_seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise _fail(where, "random_seed must be an integer")
    th_raw = _as_dict(d["thresholds"], f"{where}: thresholds")
    _exact_keys(th_raw, METRICS, f"{where}: thresholds")
    thresholds: dict[str, float] = {}
    for metric in METRICS:
        value = _number(th_raw[metric], f"{where}: thresholds.{metric}")
        if not 0 <= value <= 1:
            raise _fail(where, f"thresholds.{metric} must be in [0, 1]")
        thresholds[metric] = q(value)
    return Config(
        path=path,
        baseline_ref=_str(d["baseline"], f"{where}: baseline"),
        classifier=classifier,
        controls=controls,
        dataset_ref=_str(d["dataset"], f"{where}: dataset"),
        finished_blocks=finished,
        keywords=keywords,
        random_seed=seed,
        require_classifier_from_block=_str(d["require_classifier_from_block"], where),
        thresholds=thresholds,
        thresholds_status=_str(d["thresholds_status"], f"{where}: thresholds_status"),
    )


RECORD_KEYS: tuple[str, ...] = ("id", "label", "message", "slice", "split")


def load_dataset(path: Path, config_ref: str) -> tuple[tuple[Record, ...], str]:
    """Return the records in file order and the file's sha256."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise InputError(
            f"dataset not found: {path} (from {config_ref}); generate it with: {GENERATE_HINT}"
        ) from None
    except OSError as exc:
        raise InputError(f"cannot read dataset {path}: {exc}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path}: not valid UTF-8: {exc}") from None
    records: list[Record] = []
    seen: set[str] = set()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for number, line in enumerate(lines, start=1):
        where = f"{path}:{number}"
        try:
            obj: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError(f"{where}: invalid JSON: {exc.msg}") from None
        d = _as_dict(obj, where)
        _exact_keys(d, RECORD_KEYS, where)
        rec = Record(
            id=_str(d["id"], f"{where}: id"),
            message=_str(d["message"], f"{where}: message"),
            label=_str(d["label"], f"{where}: label"),
            split=_str(d["split"], f"{where}: split"),
            slice=_str(d["slice"], f"{where}: slice"),
        )
        if rec.label not in LABELS:
            raise _fail(where, f"label {rec.label!r} is not one of {', '.join(LABELS)}")
        if rec.split not in SPLITS:
            raise _fail(where, f"split {rec.split!r} is not dev or test")
        if rec.id in seen:
            raise _fail(where, f"duplicate id {rec.id!r}")
        seen.add(rec.id)
        records.append(rec)
    if not records:
        raise InputError(f"{path}: dataset is empty")
    return tuple(records), hashlib.sha256(raw).hexdigest()


def load_baseline(path: Path) -> Baseline:
    where = str(path)
    d = _as_dict(_read_json(path, "baseline"), where)
    _exact_keys(d, ("dataset", "notes", "split", "strategies", "written_for_block"), where)
    ds = _as_dict(d["dataset"], f"{where}: dataset")
    _exact_keys(ds, ("records", "sha256"), f"{where}: dataset")
    records = ds["records"]
    if isinstance(records, bool) or not isinstance(records, int):
        raise _fail(where, "dataset.records must be an integer")
    notes_raw = d["notes"]
    if not isinstance(notes_raw, list):
        raise _fail(where, "notes must be a list")
    notes: list[tuple[str, str]] = []
    for item in notes_raw:
        n = _as_dict(item, f"{where}: notes")
        _exact_keys(n, ("block", "reason"), f"{where}: notes")
        notes.append((_str(n["block"], where), _str(n["reason"], where)))
    strategies: dict[str, dict[str, float]] = {}
    for name, value in _as_dict(d["strategies"], f"{where}: strategies").items():
        m = _as_dict(value, f"{where}: strategies.{name}")
        _exact_keys(m, METRICS, f"{where}: strategies.{name}")
        strategies[name] = {k: q(_number(m[k], f"{where}: strategies.{name}.{k}")) for k in METRICS}
    return Baseline(
        records=records,
        sha256=_str(ds["sha256"], where),
        notes=tuple(notes),
        split=_str(d["split"], where),
        strategies=strategies,
        written_for_block=_str(d["written_for_block"], where),
    )


# --------------------------------------------------------------------------- metrics


def compute_metrics(rows: Sequence[Record], predictions: Sequence[str]) -> Metrics:
    """The four gated metrics for rows, each rounded with q()."""
    if len(rows) != len(predictions):
        raise InputError("internal: rows and predictions differ in length")
    support = {label: 0 for label in LABELS}
    tp = {label: 0 for label in LABELS}
    predicted = {label: 0 for label in LABELS}
    for rec, pred in zip(rows, predictions, strict=True):
        support[rec.label] += 1
        predicted[pred] += 1
        if pred == rec.label:
            tp[rec.label] += 1
    empty = [label for label in LABELS if support[label] == 0]
    if empty:
        raise InputError(f"split has no rows for label(s): {', '.join(empty)}")
    mis = [(r, p) for r, p in zip(rows, predictions, strict=True) if r.slice == "misleading"]
    if not mis:
        raise InputError("split has no rows in the misleading slice")
    f1s: list[float] = []
    recalls: list[float] = []
    for label in LABELS:
        precision = tp[label] / predicted[label] if predicted[label] else 0.0
        recall = tp[label] / support[label]
        recalls.append(recall)
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {
        "accuracy": q(sum(tp.values()) / len(rows)),
        "macro_f1": q(sum(f1s) / len(f1s)),
        "min_recall": q(min(recalls)),
        "misleading_accuracy": q(sum(1 for r, p in mis if r.label == p) / len(mis)),
    }


# --------------------------------------------------------------------------- running


def run_eval(
    config: Config,
    registry: Mapping[str, StrategyFactory] = REGISTRY,
    split: str = "test",
) -> EvalRun:
    """Score the controls and the configured classifier on one split."""
    if split not in SPLITS:
        raise InputError(f"unknown split {split!r}")
    if config.classifier is not None and (
        config.classifier in CONTROL_NAMES or config.classifier not in registry
    ):
        raise InputError(f"classifier {config.classifier!r} is a control or not in the registry")
    for name in config.controls:
        if name not in registry:
            raise InputError(f"control {name!r} is not in the registry")
    records, sha = load_dataset(config.dataset_path, config.dataset_ref)
    dev = [r for r in records if r.split == "dev"]
    if not dev:
        raise InputError("dataset has no dev rows")
    rows = tuple(r for r in records if r.split == split)
    ctx = StrategyContext(
        dev_messages=tuple(r.message for r in dev),
        dev_labels=tuple(r.label for r in dev),
        labels=LABELS,
        keywords=config.keywords,
        seed=config.random_seed,
    )
    names = [(n, "control") for n in config.controls]
    if config.classifier is not None:
        names.append((config.classifier, "classifier"))
    results: dict[str, StrategyResult] = {}
    for name, role in names:
        try:
            strategy = registry[name](ctx)
        except Exception as exc:
            raise InputError(
                f"strategy {name}: factory raised {type(exc).__name__}: {exc}"
            ) from None
        preds: list[str] = []
        for rec in rows:
            try:
                label = strategy.predict(rec.message)
            except Exception as exc:
                raise InputError(
                    f"strategy {name}: predict raised {type(exc).__name__} "
                    f"on record {rec.id}: {exc}"
                ) from None
            if label not in LABELS:
                raise InputError(
                    f"strategy {name}: invalid prediction {label!r} on record {rec.id}"
                )
            preds.append(label)
        results[name] = StrategyResult(role, compute_metrics(rows, preds), tuple(preds))
    return EvalRun(split, len(records), sha, rows, results, config.classifier)


# --------------------------------------------------------------------------- gate


def _f(x: float) -> str:
    return f"{x:.4f}"


def gate(
    thresholds: Mapping[str, float],
    controls: Mapping[str, Mapping[str, float]],
    classifier: str | None,
    classifier_metrics: Mapping[str, float] | None,
    baseline: Baseline | None,
    dataset_sha256: str,
    finished_blocks: Sequence[str],
    require_classifier_from_block: str,
) -> list[Failure]:
    """Pure gate. Runs every check and lists every failure. Comparisons use q() and >=."""
    failures: list[Failure] = []
    for metric in METRICS:
        limit = q(thresholds[metric])
        for name, metrics in controls.items():
            value = q(metrics[metric])
            if value >= limit:
                failures.append(
                    Failure(
                        "too_lenient",
                        name,
                        metric,
                        value,
                        limit,
                        f"metric {metric} too lenient: control {name} "
                        f"reaches {_f(value)} >= {_f(limit)}",
                    )
                )
    if classifier is None or classifier_metrics is None:
        if require_classifier_from_block in finished_blocks:
            failures.append(
                Failure(
                    "classifier_required",
                    "classifier",
                    None,
                    None,
                    None,
                    f"classifier required: block {require_classifier_from_block} is finished "
                    "but no classifier is configured",
                )
            )
        return failures
    for metric in METRICS:
        value = q(classifier_metrics[metric])
        limit = q(thresholds[metric])
        if value < limit:
            failures.append(
                Failure(
                    "below_threshold",
                    classifier,
                    metric,
                    value,
                    limit,
                    f"classifier {classifier} metric {metric} below threshold: "
                    f"{_f(value)} < {_f(limit)}",
                )
            )
    if baseline is not None:
        if baseline.sha256 != dataset_sha256:
            failures.append(
                Failure(
                    "dataset_mismatch",
                    "dataset",
                    None,
                    None,
                    None,
                    "baseline was written for a different dataset file (sha256 differs)",
                )
            )
        entry = baseline.strategies.get(classifier)
        if entry is None:
            failures.append(
                Failure(
                    "missing_baseline",
                    classifier,
                    None,
                    None,
                    None,
                    f"classifier {classifier} has no baseline entry; run --write-baseline",
                )
            )
        else:
            for metric in METRICS:
                value = q(classifier_metrics[metric])
                base = q(entry[metric])
                if value < base:
                    failures.append(
                        Failure(
                            "below_baseline",
                            classifier,
                            metric,
                            value,
                            base,
                            f"classifier {classifier} metric {metric} below baseline: "
                            f"{_f(value)} < {_f(base)}",
                        )
                    )
    return failures


def check_run(
    config: Config, run: EvalRun, baseline: Baseline | None, *, first_entry_ok: bool = False
) -> list[Failure]:
    """Apply gate() to a run. first_entry_ok drops missing_baseline (used when writing)."""
    controls = {n: r.metrics for n, r in run.results.items() if r.role == "control"}
    clf = run.results.get(run.classifier) if run.classifier else None
    failures = gate(
        config.thresholds,
        controls,
        run.classifier,
        clf.metrics if clf else None,
        baseline,
        run.dataset_sha256,
        config.finished_blocks,
        config.require_classifier_from_block,
    )
    if first_entry_ok:
        failures = [f for f in failures if f.kind != "missing_baseline"]
    return failures


# --------------------------------------------------------------------------- rendering


def _cell(value: float, limit: float) -> str:
    passed = q(value) >= q(limit)
    return f"{_f(value)} {'pass' if passed else 'fail'}"


def render_table(report: Report) -> str:
    run, config = report.run, report.config
    cols = ["strategy", "role", *METRICS]
    rows: list[list[str]] = [
        ["threshold", "gate", *(_f(config.thresholds[m]) for m in METRICS)],
    ]
    for name, res in run.results.items():
        rows.append(
            [name, res.role, *(_cell(res.metrics[m], config.thresholds[m]) for m in METRICS)]
        )
    widths = [max(len(cols[i]), *(len(r[i]) for r in rows)) for i in range(len(cols))]

    def line(cells: Sequence[str]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)).rstrip()

    out: list[str] = []
    if report.informational:
        out.append("informational: dev split, not gated")
    out.append(line(cols))
    out.extend(line(r) for r in rows)
    if run.classifier is None:
        out.append("classifier: none configured (controls only)")
    out.append("legend: controls must fail every metric; the classifier must pass every one")
    if not report.informational:
        if report.ok:
            out.append("eval passed")
        else:
            out.append("eval failed:")
            out.extend(f"  {f.kind}: {f.message}" for f in report.failures)
    return "\n".join(out) + "\n"


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_json(
    report: Report, errors: Mapping[str, Sequence[Mapping[str, str]]] | None = None
) -> str:
    run, config = report.run, report.config
    strategies = {
        name: {
            "role": res.role,
            "metrics": dict(res.metrics),
            "pass": {m: q(res.metrics[m]) >= q(config.thresholds[m]) for m in METRICS},
        }
        for name, res in run.results.items()
    }
    payload: dict[str, object] = {
        "split": run.split,
        "dataset": {
            "path": config.dataset_ref,
            "sha256": run.dataset_sha256,
            "records": run.dataset_records,
            "evaluated": len(run.evaluated),
        },
        "thresholds": dict(config.thresholds),
        "thresholds_status": config.thresholds_status,
        "classifier": run.classifier,
        "strategies": strategies,
        "failures": [
            {
                "kind": f.kind,
                "strategy": f.strategy,
                "metric": f.metric,
                "value": f.value,
                "limit": f.limit,
                "message": f.message,
            }
            for f in report.failures
        ],
        "ok": report.ok,
    }
    if errors is not None:
        payload["errors"] = {name: [dict(e) for e in rows] for name, rows in errors.items()}
    return canonical_json(payload)


# --------------------------------------------------------------------------- writers


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def baseline_to_dict(baseline: Baseline) -> dict[str, object]:
    return {
        "dataset": {"records": baseline.records, "sha256": baseline.sha256},
        "notes": [{"block": b, "reason": r} for b, r in baseline.notes],
        "split": baseline.split,
        "strategies": {n: dict(m) for n, m in baseline.strategies.items()},
        "written_for_block": baseline.written_for_block,
    }


def config_to_dict(config: Config) -> dict[str, object]:
    return {
        "baseline": config.baseline_ref,
        "classifier": config.classifier,
        "controls": list(config.controls),
        "dataset": config.dataset_ref,
        "finished_blocks": list(config.finished_blocks),
        "keyword_spam": {label: list(words) for label, words in config.keywords.items()},
        "random_seed": config.random_seed,
        "require_classifier_from_block": config.require_classifier_from_block,
        "thresholds": dict(config.thresholds),
        "thresholds_status": config.thresholds_status,
    }


def write_baseline_files(
    config: Config,
    run: EvalRun,
    previous: Baseline | None,
    block: str,
    reason: str | None,
) -> Baseline:
    """Write baseline.json, then append block to finished_blocks in the config. Atomic per file."""
    if not BLOCK_PATTERN.match(block):
        raise InputError(f"bad block name {block!r}")
    notes = list(previous.notes) if previous else []
    if reason:
        notes.append((block, reason))
    baseline = Baseline(
        records=run.dataset_records,
        sha256=run.dataset_sha256,
        notes=tuple(notes),
        split=run.split,
        strategies={n: dict(r.metrics) for n, r in run.results.items()},
        written_for_block=block,
    )
    finished = (
        config.finished_blocks
        if block in config.finished_blocks
        else (
            *config.finished_blocks,
            block,
        )
    )
    new_config = Config(
        path=config.path,
        baseline_ref=config.baseline_ref,
        classifier=config.classifier,
        controls=config.controls,
        dataset_ref=config.dataset_ref,
        finished_blocks=finished,
        keywords=config.keywords,
        random_seed=config.random_seed,
        require_classifier_from_block=config.require_classifier_from_block,
        thresholds=config.thresholds,
        thresholds_status=config.thresholds_status,
    )
    try:
        _atomic_write(config.baseline_path, canonical_json(baseline_to_dict(baseline)))
        _atomic_write(config.path, canonical_json(config_to_dict(new_config)))
    except OSError as exc:
        raise InputError(f"cannot write baseline or config: {exc}") from None
    return baseline


# --------------------------------------------------------------------------- command line


def configure_parser(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config", default="evals/config.json", help="eval config (default: %(default)s)"
    )
    p.add_argument("--json", action="store_true", help="print one JSON object instead of the table")
    p.add_argument("--split", choices=SPLITS, default="test", help="dev is informational only")
    p.add_argument("--show-errors", action="store_true", help="list dev misclassifications")
    p.add_argument("--write-baseline", action="store_true", help="rewrite the baseline")
    p.add_argument("--block", help="block name for --write-baseline, for example B4")
    p.add_argument("--reason", help="reason recorded when a baseline is written with a regression")


def _usage_error(message: str) -> int:
    print(f"commit-kind eval: error: {message}", file=sys.stderr)
    return 2


def _error_rows(run: EvalRun) -> dict[str, list[dict[str, str]]]:
    """Misclassified records per strategy: the classifier if configured, else the controls."""
    names = [run.classifier] if run.classifier else list(run.results)
    return {
        name: [
            {"id": rec.id, "expected": rec.label, "predicted": pred}
            for rec, pred in zip(run.evaluated, run.results[name].predictions, strict=True)
            if pred != rec.label
        ]
        for name in names
    }


def _render_errors(run: EvalRun, errors: Mapping[str, Sequence[Mapping[str, str]]]) -> str:
    by_id = {r.id: r for r in run.evaluated}
    out: list[str] = []
    for name, rows in errors.items():
        out.append(f"errors: {name} ({len(rows)} of {len(run.evaluated)} dev records)")
        for row in rows:
            first = by_id[row["id"]].message.split("\n", 1)[0][:70]
            out.append(f"  {row['id']} expected {row['expected']} got {row['predicted']}: {first}")
    return "\n".join(out) + "\n"


REFUSED_KINDS = ("too_lenient", "below_threshold", "classifier_required")
REASON_KINDS = ("below_baseline", "dataset_mismatch")


def run_from_args(args: argparse.Namespace) -> int:
    """Run the eval command. Exit codes: 0 passed, 1 gate failed, 2 usage, 3 input error."""
    if args.show_errors and args.split != "dev":
        return _usage_error("--show-errors requires --split dev")
    if args.write_baseline and args.split == "dev":
        return _usage_error("--write-baseline cannot be combined with --split dev")
    if args.write_baseline and not args.block:
        return _usage_error("--write-baseline requires --block <B>, for example --block B4")
    if (args.block or args.reason) and not args.write_baseline:
        return _usage_error("--block and --reason require --write-baseline")
    if args.block and not BLOCK_PATTERN.match(args.block):
        return _usage_error(f"bad block name {args.block!r} (expected B followed by digits)")
    try:
        return _run(args)
    except InputError as exc:
        print(f"eval: {exc}", file=sys.stderr)
        return 3


def _run(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    run = run_eval(config, REGISTRY, split=args.split)
    errors = _error_rows(run) if args.show_errors else None

    if args.split == "dev":
        report = Report(run, config, informational=True)
        if args.json:
            print(render_json(report, errors), end="")
        else:
            print(render_table(report), end="")
            if errors is not None:
                print(_render_errors(run, errors), end="")
        return 0

    write = bool(args.write_baseline)
    baseline: Baseline | None = None
    if config.baseline_path.exists() or not write:
        if not config.baseline_path.exists():
            raise InputError(
                f"baseline not found: {config.baseline_path}; run with --write-baseline"
            )
        baseline = load_baseline(config.baseline_path)
    failures = check_run(config, run, baseline, first_entry_ok=write)
    status = sys.stderr if args.json else sys.stdout

    accepted = False
    if write and not any(f.kind in REFUSED_KINDS for f in failures):
        needs_reason = [f for f in failures if f.kind in REASON_KINDS]
        accepted = bool(args.reason) or not needs_reason
        if accepted:
            failures = []
    report = Report(run, config, tuple(failures))
    print(render_json(report) if args.json else render_table(report), end="")
    if not write:
        return 0 if report.ok else 1
    if not accepted:
        hint = "" if any(f.kind in REFUSED_KINDS for f in failures) else " (give --reason)"
        print(f"baseline not written: gate failed{hint}", file=sys.stderr)
        return 1
    write_baseline_files(config, run, baseline, args.block, args.reason)
    print(f"baseline written for {args.block}: {config.baseline_ref}", file=status)
    return 0
