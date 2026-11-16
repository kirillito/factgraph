"""A7: coverage. Which reachable beats do the game's automated tests never fire?

The game's tests write the IDs of the beats they fire into a trace folder. Any file under it, at any
depth, is read:

- ``*.jsonl``: one JSON object per line with a ``"beat"`` key (other keys are ignored);
- anything else: one beat ID per line; blank lines and lines starting with ``#`` are skipped.

Beats that A4 already reports as unreachable are left out of the coverage list. IDs in a trace that
match no beat are flagged, since they usually mean an ID changed in content but not in the game.
"""

from __future__ import annotations

import json
from pathlib import Path

from .checks import suggest
from .model import Finding, Project, Source
from .reach import Reach


class TraceError(Exception):
    pass


def coverage(project: Project, reach: Reach, trace_dir: str) -> list[Finding]:
    folder = Path(trace_dir)
    if not folder.is_dir():
        raise TraceError(f"trace folder not found: {trace_dir}")
    beat_ids = [b.id for b in project.beats]
    known = set(beat_ids)
    fired: set[str] = set()
    findings = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        for line_no, beat_id in _read_trace(path):
            if beat_id in known:
                fired.add(beat_id)
                continue
            hint = suggest(beat_id, beat_ids)
            findings.append(Finding(
                "A7",
                f"trace names unknown beat '{beat_id}'" + (f" (did you mean {hint}?)" if hint else ""),
                Source(_display(path, project.root), line_no),
                "warning",
            ))
    reachable = [b for b in project.beats if reach.may_fire(b)]
    missed = [b for b in reachable if b.id not in fired]
    findings.insert(0, Finding(
        "A7", f"coverage: {len(reachable) - len(missed)} of {len(reachable)} reachable beats fired by tests",
        severity="info",
    ))
    findings += [Finding("A7", f"beat '{b.id}' is never fired by a test", b.source, "info") for b in missed]
    return findings


def _read_trace(path: Path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    jsonl = path.suffix == ".jsonl"
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not jsonl:
            yield n, line
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and isinstance(record.get("beat"), str):
            yield n, record["beat"]


def _display(path: Path, root: str) -> str:
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()
