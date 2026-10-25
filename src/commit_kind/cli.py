"""Command line interface."""

import argparse
import sys
from collections.abc import Sequence

from commit_kind import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="commit-kind")
    parser.add_argument("--version", action="version", version=f"commit-kind {__version__}")
    parser.add_subparsers(dest="command", metavar="<command>")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    return 0
