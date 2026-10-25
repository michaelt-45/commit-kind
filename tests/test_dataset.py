import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "commits.jsonl"
GENERATOR = ROOT / "scripts" / "generate_dataset.py"

LABELS = ("feat", "fix", "docs", "refactor", "test", "chore")
SLICE_COUNTS = {"prefixed": 22, "plain": 18, "misleading": 20}
KEYS = {"id", "message", "label", "split", "slice"}
TOKEN = re.compile(r"[a-z0-9]+")
PREFIX_LIKE = re.compile(r"^\s*[A-Za-z]+(\([^)]*\))?!?:\s", re.IGNORECASE)
PREFIXED = re.compile(r"^(feat|fix|docs|refactor|test|chore)(\([a-z0-9-]+\))?!?: \S")
PREFIX_STRIP = re.compile(r"^[a-z]+(\([^)]*\))?!?: ")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|org|net|io|dev)\b")

Record = dict[str, str]


def load_records() -> list[Record]:
    lines = DATA.read_text(encoding="ascii").split("\n")
    assert lines[-1] == ""
    return [cast("Record", json.loads(line)) for line in lines[:-1]]


def load_keywords() -> dict[str, tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("generate_dataset", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast("dict[str, tuple[str, ...]]", module.CONTROL_KEYWORDS)


def load_heldout_tokens() -> list[str]:
    spec = importlib.util.spec_from_file_location("generate_dataset", GENERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    heldout = cast("dict[str, list[dict[str, str]]]", module.HELDOUT)
    return [token for entries in heldout.values() for e in entries for token in e["tokens"].split()]


KEYWORDS = load_keywords()
RECORDS = load_records()


def hits(message: str) -> dict[str, int]:
    tokens = TOKEN.findall(message.lower())
    return {label: sum(1 for t in tokens if t in words) for label, words in KEYWORDS.items()}


def of_slice(name: str) -> list[Record]:
    return [r for r in RECORDS if r["slice"] == name]


def test_file_format() -> None:
    raw = DATA.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r" not in raw
    text = raw.decode("ascii")
    for line in text.split("\n")[:-1]:
        assert line == json.dumps(json.loads(line), sort_keys=True, ensure_ascii=True)


def test_schema() -> None:
    ids = []
    for record in RECORDS:
        assert set(record) == KEYS
        assert all(isinstance(value, str) for value in record.values())
        assert record["label"] in LABELS
        assert record["split"] in ("dev", "test")
        assert record["slice"] in SLICE_COUNTS
        assert re.fullmatch(r"c\d{4}", record["id"])
        ids.append(record["id"])
    assert ids == [f"c{i:04d}" for i in range(1, 361)]


def test_counts() -> None:
    assert len(RECORDS) == 360
    by_label = Counter(r["label"] for r in RECORDS)
    assert all(by_label[label] == 60 for label in LABELS)
    for label in LABELS:
        by_slice = Counter(r["slice"] for r in RECORDS if r["label"] == label)
        assert dict(by_slice) == SLICE_COUNTS


def test_split_balance() -> None:
    for label in LABELS:
        splits = Counter(r["split"] for r in RECORDS if r["label"] == label)
        assert splits == {"dev": 30, "test": 30}
        for name, count in SLICE_COUNTS.items():
            sub = Counter(r["split"] for r in RECORDS if r["label"] == label and r["slice"] == name)
            assert sub == {"dev": count // 2, "test": count // 2}


def test_slice_shares() -> None:
    test_split = [r for r in RECORDS if r["split"] == "test"]
    for name in SLICE_COUNTS:
        assert len(of_slice(name)) >= 0.2 * len(RECORDS)
        assert sum(1 for r in test_split if r["slice"] == name) >= 0.2 * len(test_split)


def test_prefixed_have_matching_prefix() -> None:
    for record in of_slice("prefixed"):
        summary = record["message"].split("\n", 1)[0]
        match = PREFIXED.match(summary)
        assert match is not None, summary
        assert match.group(1) == record["label"]


def test_breaking_footer_needs_bang() -> None:
    for record in of_slice("prefixed"):
        summary = record["message"].split("\n", 1)[0]
        if "BREAKING CHANGE:" in record["message"]:
            assert summary.split(":", 1)[0].endswith("!")


def test_unprefixed_slices_have_no_prefix() -> None:
    for record in of_slice("plain") + of_slice("misleading"):
        for line in record["message"].split("\n"):
            assert not PREFIX_LIKE.match(line), line


def test_plain_has_no_foreign_keywords() -> None:
    for record in of_slice("plain"):
        counts = hits(record["message"])
        foreign = {k: v for k, v in counts.items() if k != record["label"] and v}
        assert not foreign, (record["message"], foreign)


def test_misleading_decoy_dominates() -> None:
    for record in of_slice("misleading"):
        counts = hits(record["message"])
        own = counts[record["label"]]
        other = max(v for k, v in counts.items() if k != record["label"])
        assert other > own, record["message"]
    # Each true label has at least 3 distinct decoys.
    for label in LABELS:
        decoys: set[str] = set()
        for record in of_slice("misleading"):
            if record["label"] == label:
                counts = hits(record["message"])
                top = max(v for k, v in counts.items() if k != label)
                decoys.update(k for k, v in counts.items() if k != label and v == top)
        assert len(decoys) >= 3, label


def keyword_spam(message: str) -> str:
    counts = hits(message)
    best = max(counts.values())
    winners = [label for label in LABELS if counts[label] == best]
    return winners[0] if best > 0 and len(winners) == 1 else "feat"


def test_keyword_spam_control_fails_on_test_split() -> None:
    test_split = [r for r in RECORDS if r["split"] == "test"]
    misleading = [r for r in test_split if r["slice"] == "misleading"]
    correct = sum(1 for r in misleading if keyword_spam(r["message"]) == r["label"])
    assert correct == 0
    for label in LABELS:
        rows = [r for r in test_split if r["label"] == label]
        recall = sum(1 for r in rows if keyword_spam(r["message"]) == label) / len(rows)
        assert recall <= 20 / 30 + 1e-9, (label, recall)
    accuracy = sum(1 for r in test_split if keyword_spam(r["message"]) == r["label"]) / len(
        test_split
    )
    assert accuracy <= 20 / 30 + 1e-9


def test_majority_bound() -> None:
    dev = Counter(r["label"] for r in RECORDS if r["split"] == "dev")
    assert len(set(dev.values())) == 1
    test_split = [r for r in RECORDS if r["split"] == "test"]
    # Any single label predicted for every test row is right for exactly 30 of 180.
    for label in LABELS:
        assert sum(1 for r in test_split if r["label"] == label) == 30
    assert len(test_split) == 180


def test_no_personal_data() -> None:
    for record in RECORDS:
        message = record["message"]
        assert not EMAIL.search(message)
        assert not URL.search(message)
        lowered = message.lower()
        for forbidden in ("@", "signed-off-by", "co-authored-by", "/users/", "/home/"):
            assert forbidden not in lowered


def test_summaries_unique() -> None:
    keys = [" ".join(r["message"].split("\n", 1)[0].lower().split()) for r in RECORDS]
    assert len(keys) == len(set(keys))
    stripped = [" ".join(PREFIX_STRIP.sub("", k).split()) for k in keys]
    assert len(stripped) == len(set(stripped))


def test_line_lengths() -> None:
    for record in RECORDS:
        for line in record["message"].split("\n"):
            assert len(line) <= 72, line
            assert line == line.rstrip(), line
        assert "\t" not in record["message"]


def test_heldout_tokens_only_in_test() -> None:
    tokens = load_heldout_tokens()
    assert tokens
    dev_tokens = {
        t for r in RECORDS if r["split"] == "dev" for t in TOKEN.findall(r["message"].lower())
    }
    test_tokens = {
        t for r in RECORDS if r["split"] == "test" for t in TOKEN.findall(r["message"].lower())
    }
    for token in tokens:
        assert token in test_tokens, token
        assert token not in dev_tokens, token
    assert test_tokens - dev_tokens
    heldout_records = [
        r
        for r in RECORDS
        if r["split"] == "test" and any(t in TOKEN.findall(r["message"].lower()) for t in tokens)
    ]
    assert len(heldout_records) == 24
    assert all(r["slice"] != "prefixed" for r in heldout_records)
