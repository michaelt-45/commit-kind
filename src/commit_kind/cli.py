"""Command line interface."""

import argparse
import sys
from collections.abc import Sequence

from commit_kind import __version__, evaluate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="commit-kind")
    parser.add_argument("--version", action="version", version=f"commit-kind {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    p = sub.add_parser("eval", help="score strategies on the dataset")
    evaluate.configure_parser(p)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.command == "eval":
        return evaluate.run_from_args(args)
    return 0
