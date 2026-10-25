"""Gated eval: score strategies on the test split, apply the gate, write baselines.

Fails closed: a missing or invalid input is an InputError (exit 3), never a pass.
Every metric goes through q() at storage, display and comparison.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from commit_kind.labels import LABELS
from commit_kind.strategies import CONTROL_NAMES, REGISTRY, StrategyContext

METRICS = ("accuracy", "macro_f1", "min_recall", "misleading_accuracy")
GENERATE_HINT = "python3 scripts/generate_dataset.py --seed 20261025 --out data/commits.jsonl"
CONFIG_KEYS = {"baseline", "classifier", "controls", "dataset", "finished_blocks"} | {
    "keyword_spam",
    "random_seed",
    "thresholds",
}


class InputError(Exception):
    """A missing or invalid config, dataset, baseline or strategy (exit code 3)."""


def q(x: float) -> float:
    return round(x, 4)


def _read_json(path: Path, what: str) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise InputError(f"{what} not found: {path}") from None
    except ValueError as e:
        raise InputError(f"{what} is not valid JSON: {path}: {e}") from None
    if not isinstance(obj, dict):
        raise InputError(f"{what} must be a JSON object: {path}")
    return obj


def _write_json(path: Path, obj: object) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def load_config(path: Path) -> dict[str, Any]:
    cfg = _read_json(path, "config")
    missing = sorted(CONFIG_KEYS - set(cfg))
    if missing:
        raise InputError(f"config {path}: missing keys: {', '.join(missing)}")
    t = cfg["thresholds"]
    if not isinstance(t, dict) or set(t) != set(METRICS):
        raise InputError(f"config {path}: thresholds must have exactly {', '.join(METRICS)}")
    if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in t.values()):
        raise InputError(f"config {path}: thresholds must be numbers in [0, 1]")
    if not set(CONTROL_NAMES) <= set(cfg["controls"]):
        raise InputError(f"config {path}: controls must include {', '.join(CONTROL_NAMES)}")
    name = cfg["classifier"]
    if name is not None and (name in CONTROL_NAMES or name not in REGISTRY):
        raise InputError(f"config {path}: classifier {name!r} is not a known non-control strategy")
    return cfg


def load_dataset(path: Path, config_path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise InputError(
            f"dataset not found: {path} (from {config_path}); generate it with: {GENERATE_HINT}"
        )
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            r = json.loads(line)
            ok = isinstance(r, dict) and all(isinstance(r.get(k), str) for k in KEYS)
            ok = ok and r["label"] in LABELS and r["split"] in ("dev", "test")
        except ValueError:
            ok = False
        if not ok:
            raise InputError(f"dataset {path} line {n}: invalid record")
        rows.append(r)
    return rows


KEYS = ("id", "message", "label", "split", "slice")


def metrics(gold: Sequence[str], pred: Sequence[str], slices: Sequence[str]) -> dict[str, float]:
    f1s, recalls = [], []
    for lab in LABELS:
        tp = sum(g == p == lab for g, p in zip(gold, pred, strict=True))
        support, predicted = gold.count(lab), list(pred).count(lab)
        if support == 0:
            raise InputError(f"split has no records labelled {lab}")
        r, pr = tp / support, tp / predicted if predicted else 0.0
        recalls.append(r)
        f1s.append(2 * pr * r / (pr + r) if pr + r else 0.0)
    mis = [g == p for g, p, s in zip(gold, pred, slices, strict=True) if s == "misleading"]
    if not mis:
        raise InputError("split has no misleading records")
    return {
        "accuracy": q(sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)),
        "macro_f1": q(sum(f1s) / len(LABELS)),
        "min_recall": q(min(recalls)),
        "misleading_accuracy": q(sum(mis) / len(mis)),
    }


def score(
    cfg: dict[str, Any], rows: list[dict[str, str]], split: str
) -> tuple[dict[str, dict[str, float]], dict[str, list[str]]]:
    """Metrics and predictions per strategy on the given split; fitting uses dev only."""
    dev = [r for r in rows if r["split"] == "dev"]
    ctx = StrategyContext(
        dev_messages=tuple(r["message"] for r in dev),
        dev_labels=tuple(r["label"] for r in dev),
        labels=LABELS,
        keywords={k: tuple(v) for k, v in cfg["keyword_spam"].items()},
        seed=cfg["random_seed"],
    )
    target = [r for r in rows if r["split"] == split]
    names = list(CONTROL_NAMES) + ([cfg["classifier"]] if cfg["classifier"] else [])
    results, preds = {}, {}
    for name in names:
        strategy = REGISTRY[name](ctx)
        out = []
        for r in target:
            try:
                p = strategy.predict(r["message"])
            except Exception as e:
                raise InputError(f"strategy {name} raised on {r['id']}: {e}") from None
            if p not in LABELS:
                raise InputError(f"strategy {name} returned {p!r} on {r['id']}")
            out.append(p)
        preds[name] = out
        results[name] = metrics([r["label"] for r in target], out, [r["slice"] for r in target])
    return results, preds


def gate(
    cfg: dict[str, Any],
    results: dict[str, dict[str, float]],
    base: dict[str, dict[str, float]] | None,
) -> list[str]:
    """All failures (empty list = pass). base=None skips the baseline check (writing)."""
    t = {m: q(cfg["thresholds"][m]) for m in METRICS}
    fails = [
        f"too lenient: {m} (control {c} reaches {q(results[c][m])} >= {t[m]})"
        for c in CONTROL_NAMES
        for m in METRICS
        if q(results[c][m]) >= t[m]
    ]
    name = cfg["classifier"]
    if name:
        fails += [
            f"classifier {name} below threshold: {m} {q(results[name][m])} < {t[m]}"
            for m in METRICS
            if q(results[name][m]) < t[m]
        ]
        if base is not None and name not in base:
            fails.append(f"classifier {name} has no baseline entry")
        elif base is not None:
            fails += [
                f"classifier {name} below baseline: {m} {q(results[name][m])} < {q(base[name][m])}"
                for m in METRICS
                if q(results[name][m]) < q(base[name][m])
            ]
    return fails


def render(cfg: dict[str, Any], results: dict[str, dict[str, float]], informational: bool) -> str:
    t = {m: q(cfg["thresholds"][m]) for m in METRICS}
    lines = ["informational: dev split, not gated"] if informational else []
    lines.append(f"{'strategy':<14}" + "".join(f"{m:>22}" for m in METRICS))
    lines.append(f"{'threshold':<14}" + "".join(f"{t[m]:>22.4f}" for m in METRICS))
    for name, res in results.items():
        cells = (f"{q(res[m]):.4f} {'pass' if q(res[m]) >= t[m] else 'fail'}" for m in METRICS)
        lines.append(f"{name:<14}" + "".join(f"{c:>22}" for c in cells))
    if not cfg["classifier"]:
        lines.append("classifier: none configured (controls only)")
    lines.append("controls must fail every metric; the classifier must pass every one")
    return "\n".join(lines)


def configure_parser(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="evals/config.json")
    p.add_argument("--json", action="store_true")
    p.add_argument("--split", choices=("test", "dev"), default="test")
    p.add_argument("--show-errors", action="store_true")
    p.add_argument("--write-baseline", action="store_true")
    p.add_argument("--block", metavar="B<n>")


def run_from_args(args: argparse.Namespace) -> int:
    dev = args.split == "dev"
    bad = (
        (args.show_errors and (not dev or args.json), "--show-errors needs --split dev, no --json"),
        (args.write_baseline and dev, "--write-baseline cannot be used with --split dev"),
        (args.write_baseline != (args.block is not None), "--block goes with --write-baseline"),
        (args.block is not None and not re.fullmatch(r"B\d+", args.block), "--block must be B<n>"),
    )
    for cond, msg in bad:
        if cond:
            print(f"eval: error: {msg}", file=sys.stderr)
            return 2
    try:
        return _run(args)
    except InputError as e:
        print(f"eval: {e}", file=sys.stderr)
        return 3


def _run(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    rows = load_dataset(path.parent / cfg["dataset"], path)
    results, preds = score(cfg, rows, args.split)
    if args.split == "dev":
        print(render(cfg, results, True))
        name = cfg["classifier"]
        target = [r for r in rows if r["split"] == "dev"]
        if args.show_errors and name:
            for r, p in zip(target, preds[name], strict=True):
                if p != r["label"]:
                    print(
                        f"{r['id']}: expected {r['label']}, got {p}: {r['message'].splitlines()[0]}"
                    )
        return 0
    baseline_path = path.parent / cfg["baseline"]
    baseline = None
    if not args.write_baseline:
        entries = _read_json(baseline_path, "baseline (create it with --write-baseline)")
        baseline = entries.get("strategies")
        if not isinstance(baseline, dict) or not all(
            isinstance(e, dict) and all(isinstance(e.get(m), (int, float)) for m in METRICS)
            for e in baseline.values()
        ):
            raise InputError(f"baseline {baseline_path}: invalid strategies")
    fails = gate(cfg, results, baseline)
    if args.json:
        ok = not fails
        print(json.dumps({"ok": ok, "failures": fails, "strategies": results}, sort_keys=True))
    else:
        print(render(cfg, results, False))
        print("\n".join(["eval failed:", *fails]) if fails else "eval passed")
    if fails:
        return 1
    if args.write_baseline:
        cfg["finished_blocks"] = sorted({*cfg["finished_blocks"], args.block})
        _write_json(baseline_path, {"strategies": results, "written_for_block": args.block})
        _write_json(path, cfg)
        print(f"baseline written for {args.block}")
    return 0
