"""Command line: ``factgraph check | graph | why | who``."""

from __future__ import annotations

import argparse
import sys

from . import explain, graph
from .checks import check
from .config import ConfigError, load_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factgraph", description="Story-flow linter for narrative games.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="report flag and reachability errors (exit 1 on errors)")
    p_check.add_argument("--config", default="factgraph.toml")

    p_why = sub.add_parser("why", help="the shortest path of beats that makes a beat reachable, or why it can't be")
    p_why.add_argument("beat")
    p_why.add_argument("--config", default="factgraph.toml")

    p_who = sub.add_parser("who", help="every beat that reads or writes a fact, with file:line")
    p_who.add_argument("fact")
    p_who.add_argument("--config", default="factgraph.toml")

    p_graph = sub.add_parser("graph", help="flow graph of beats, facts and goals")
    p_graph.add_argument("--chapter", help="only beats tagged with this chapter")
    p_graph.add_argument("--focus", help="only the neighbourhood of this fact, beat or goal")
    p_graph.add_argument("--depth", type=int, default=2, help="edges to follow from --focus each way (default 2)")
    p_graph.add_argument("--group-by", default="location", help="beat tag to cluster by (default location)")
    p_graph.add_argument("--format", choices=["mermaid", "dot"], default="mermaid")
    p_graph.add_argument("--config", default="factgraph.toml")

    args = parser.parse_args(argv)
    try:
        project = load_project(args.config)
    except ConfigError as exc:
        print(f"factgraph: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        return _check(project)
    if args.command == "why":
        return _print(*explain.why(project, args.beat))
    if args.command == "graph":
        try:
            g = graph.build_graph(project, args.chapter, args.focus, args.depth, args.group_by)
        except graph.GraphError as exc:
            return _print(2, [str(exc)])
        return _print(0, [graph.to_mermaid(g) if args.format == "mermaid" else graph.to_dot(g)])
    if args.command == "who":
        return _print(*explain.who(project, args.fact))
    return 2


def _print(code: int, lines: list[str]) -> int:
    for line in lines:
        print(line)
    return code


def _check(project) -> int:
    findings = check(project)
    findings.sort(key=lambda f: (f.source.file if f.source else "", f.source.line if f.source else 0, f.check))
    for finding in findings:
        print(finding)
    return 1 if any(f.severity == "error" for f in findings) else 0
