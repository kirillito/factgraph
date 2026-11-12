"""JSON data adapter: maps game data files to beats through a small mapping config.

One ``[[sources.json]]`` table per kind of record:

    [[sources.json]]
    files = "data/clues/*.json"     # glob or list of globs, relative to the config
    kind = "interactable"           # constant kind, or kind_field = "type"
    items = "interactables"         # dotted path to the record list; omit if the file is the list/record
    id = "id"                       # record field holding the ID (default "id")
    id_prefix = "clue."             # optional prefix added to every beat ID
    requires = "requires"           # field(s) holding a condition (several fields are combined with all)
    effects = "effects"             # field(s) holding effects
    tags = { location = "room" }    # beat tag -> record field
    static_tags = { chapter = "1" } # tags added to every beat from these files

Custom effect names are mapped with a top-level ``[effects]`` table, e.g.
``give_item = { set = "item.{}" }``.
"""

from __future__ import annotations

import glob
from pathlib import Path

from .. import jsonloc
from ..model import All, Beat, Finding, Source
from ..syntax import SyntaxProblem, parse_condition, parse_effects


def load_json_source(entry: dict, root: Path, config: dict):
    beats: list[Beat] = []
    findings: list[Finding] = []
    effect_map = {**config.get("effects", {}), **entry.get("effects_map", {})}

    for path in _expand(entry.get("files", []), root):
        rel = path.relative_to(root).as_posix()
        try:
            data = jsonloc.loads(path.read_text(encoding="utf-8"))
        except jsonloc.JSONLocError as exc:
            findings.append(Finding("adapter", f"invalid JSON: {exc}", Source(rel, exc.line)))
            continue
        records = _records(data, entry.get("items"))
        if records is None:
            findings.append(
                Finding("adapter", f"no record list at '{entry.get('items')}'", Source(rel, jsonloc.line_of(data, 1)))
            )
            continue
        for record in records:
            beat, problems = _beat(record, rel, entry, effect_map)
            findings.extend(problems)
            if beat is not None:
                beats.append(beat)
    return beats, findings


def _expand(patterns, root: Path) -> list[Path]:
    if isinstance(patterns, str):
        patterns = [patterns]
    found: list[Path] = []
    for pattern in patterns:
        for match in sorted(glob.glob(str(root / pattern), recursive=True)):
            path = Path(match)
            if path.is_file() and path not in found:
                found.append(path)
    return found


def _records(data, items_path):
    node = data
    if items_path:
        for part in str(items_path).split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
    if isinstance(node, dict):
        return [node]
    if isinstance(node, list):
        return node
    return None


def _fields(entry: dict, key: str, default: str) -> list[str]:
    value = entry.get(key, default)
    return [value] if isinstance(value, str) else list(value)


def _beat(record, rel: str, entry: dict, effect_map: dict):
    line = jsonloc.line_of(record, 1)
    source = Source(rel, line)
    if not isinstance(record, dict):
        return None, [Finding("adapter", "record is not an object", source)]
    id_field = entry.get("id", "id")
    raw_id = record.get(id_field)
    if raw_id is None:
        return None, [Finding("adapter", f"record has no '{id_field}' field", source)]
    beat_id = f"{entry.get('id_prefix', '')}{raw_id}"
    kind = str(record.get(entry["kind_field"], "")) if "kind_field" in entry else entry.get("kind", "record")

    problems: list[Finding] = []
    conditions = []
    for field in _fields(entry, "requires", "requires"):
        if field in record:
            try:
                conditions.append(parse_condition(record[field], rel, line))
            except SyntaxProblem as exc:
                problems.append(Finding("adapter", f"beat '{beat_id}': {exc}", exc.source))
    requires = conditions[0] if len(conditions) == 1 else All(tuple(conditions))

    effects = []
    for field in _fields(entry, "effects", "effects"):
        if field in record:
            try:
                effects.extend(parse_effects(record[field], rel, line, effect_map))
            except SyntaxProblem as exc:
                problems.append(Finding("adapter", f"beat '{beat_id}': {exc}", exc.source))

    tags = {k: str(v) for k, v in entry.get("static_tags", {}).items()}
    for tag, field in entry.get("tags", {}).items():
        if field in record and record[field] is not None:
            tags[tag] = str(record[field])
    return Beat(beat_id, kind, source, requires, effects, tags), problems
