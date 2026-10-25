"""Command line interface."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from commit_kind import __version__, evaluate
from commit_kind.classifier import Classification, EmptyMessageError, classify
from commit_kind.rules import RULES

KIND_TEXT = {
    "prefix": 'the Conventional Commit prefix "{}" matched',
    "verb": 'the leading verb "{}" matched',
    "ambiguous": 'the verb phrase "{}" matched',
    "object": 'the object word in "{}" matched',
    "fallback": "no rule matched, so the fallback applies",
}


def explain(c: Classification) -> str:
    kind = {r.id: r.kind for r in RULES}.get(c.rule)
    text = (
        KIND_TEXT[kind].format(c.evidence) if kind in KIND_TEXT else f'rule "{c.evidence}" matched'
    )
    return f"{c.label} because {text} (rule {c.rule})"


def _classify(args: argparse.Namespace) -> int:
    message = (
        sys.stdin.buffer.read().decode("utf-8", "replace") if args.message == "-" else args.message
    )
    try:
        c = classify(message)
    except EmptyMessageError as exc:
        print(f"classify: error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(asdict(c), sort_keys=True)
        if args.json
        else explain(c)
        if args.explain
        else c.label
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="commit-kind")
    parser.add_argument("--version", action="version", version=f"commit-kind {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    p = sub.add_parser("eval", help="score strategies on the dataset")
    evaluate.configure_parser(p)
    p = sub.add_parser("classify", help="classify one commit message")
    p.add_argument("message", help='the message, or "-" to read all of stdin')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="print label, rule and evidence as JSON")
    mode.add_argument("--explain", action="store_true", help="print one line saying why")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.command == "eval":
        return evaluate.run_from_args(args)
    return _classify(args)
