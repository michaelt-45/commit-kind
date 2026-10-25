"""B2: the synthetic dataset and its generator (committed file, determinism, slices, controls)."""

import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "generate_dataset.py"
PREFIX = re.compile(r"^\s*[A-Za-z]+(\([^)]*\))?!?:\s")


def run(*args: str, hashseed: str = "0") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONHASHSEED": hashseed}
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_dataset", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def records() -> list[dict[str, str]]:
    text = (ROOT / "data" / "commits.jsonl").read_text(encoding="ascii")
    return [json.loads(line) for line in text.splitlines()]


def hits(gen: ModuleType, message: str) -> dict[str, int]:
    toks = re.findall(r"[a-z0-9]+", message.lower())
    words: dict[str, list[str]] = gen.CONTROL_KEYWORDS
    return {label: sum(toks.count(w) for w in ws) for label, ws in words.items()}


def test_committed_file_equals_fresh_generation_for_any_hash_seed(tmp_path: Path) -> None:
    committed = (ROOT / "data" / "commits.jsonl").read_bytes()
    for i, hashseed in enumerate(("1", "2")):
        out = tmp_path / f"{i}.jsonl"
        assert run("--out", str(out), hashseed=hashseed).returncode == 0
        assert out.read_bytes() == committed


def test_schema_ids_and_counts(gen: ModuleType, records: list[dict[str, str]]) -> None:
    assert [r["id"] for r in records] == [f"c{i:04d}" for i in range(1, 361)]
    assert all(set(r) == {"id", "message", "label", "split", "slice"} for r in records)
    cells = Counter((r["label"], r["slice"], r["split"]) for r in records)
    for label in gen.LABELS:
        for slice_, n in gen.SLICE_COUNTS.items():
            assert cells[(label, slice_, "dev")] == cells[(label, slice_, "test")] == n // 2


def test_slice_invariants(gen: ModuleType, records: list[dict[str, str]]) -> None:
    firsts = [" ".join(r["message"].split("\n")[0].lower().split()) for r in records]
    assert len(set(firsts)) == len(records)
    for r in records:
        lines = r["message"].split("\n")
        assert r["message"].isascii() and all(len(x) <= 72 and x == x.rstrip() for x in lines)
        counts = hits(gen, r["message"])
        others = max(v for k, v in counts.items() if k != r["label"])
        if r["slice"] == "prefixed":
            assert re.match(rf"{r['label']}(\([a-z0-9-]+\))?!?: \S", lines[0])
            assert ("!:" not in lines[0]) or r["label"] in ("feat", "fix", "refactor")
            continue
        assert not any(PREFIX.match(x) for x in lines)
        if r["slice"] == "plain":
            assert others == 0
        else:
            assert others > counts[r["label"]]


def test_every_template_appears_in_dev(gen: ModuleType, records: list[dict[str, str]]) -> None:
    dev = [r["message"].split("\n")[0] for r in records if r["split"] == "dev"]
    for label, kinds in gen.parse_templates().items():
        for kind, templates in kinds.items():
            for tpl in templates:
                rx = re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(tpl)) + "$", re.I)
                assert any(rx.search(m) for m in dev), (label, kind, tpl)


def test_no_personal_data(records: list[dict[str, str]]) -> None:
    pattern = re.compile(r"@|https?:|www\.|/Users/|/home/|Signed-off-by|Co-authored-by", re.I)
    assert not [r["id"] for r in records if pattern.search(r["message"])]


def test_keyword_spam_fails_on_test_split(gen: ModuleType, records: list[dict[str, str]]) -> None:
    test = [r for r in records if r["split"] == "test"]
    ok: Counter[str] = Counter()
    for r in test:
        counts = hits(gen, r["message"])
        pred = max(gen.LABELS, key=lambda label: counts[label])  # ties: first label, as in B3
        ok[r["label"]] += pred == r["label"]
        if r["slice"] == "misleading":
            assert pred != r["label"]
    per_label = Counter(r["label"] for r in test)
    assert sum(ok.values()) / len(test) <= 0.6667
    assert min(ok[label] / per_label[label] for label in gen.LABELS) <= 0.6667


def test_error_paths(tmp_path: Path) -> None:
    bad_out = run("--out", str(tmp_path))
    assert bad_out.returncode == 1 and "is a directory" in bad_out.stderr
    bad_seed = run("--seed", "abc", "--out", str(tmp_path / "x.jsonl"))
    assert bad_seed.returncode == 2 and not (tmp_path / "x.jsonl").exists()


def test_check_script_lints_scripts() -> None:
    lines = (ROOT / "scripts" / "check.sh").read_text().splitlines()
    steps = [x for x in lines if re.search(r"run_step (ruff-check|ruff-format|mypy)", x)]
    assert len(steps) == 3 and all("src tests scripts" in x for x in steps)
