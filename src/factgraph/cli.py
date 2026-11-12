"""Command line: ``factgraph check | graph | why | who``."""

from __future__ import annotations

import argparse
import sys

from .checks import check
from .config import ConfigError, load_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factgraph", description="Story-flow linter for narrative games.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="report flag and reachability errors (exit 1 on errors)")
    p_check.add_argument("--config", default="factgraph.toml")

    args = parser.parse_args(argv)
    try:
        project = load_project(args.config)
    except ConfigError as exc:
        print(f"factgraph: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        return _check(project)
    return 2


def _check(project) -> int:
    findings = check(project)
    findings.sort(key=lambda f: (f.source.file if f.source else "", f.source.line if f.source else 0, f.check))
    for finding in findings:
        print(finding)
    return 1 if any(f.severity == "error" for f in findings) else 0
