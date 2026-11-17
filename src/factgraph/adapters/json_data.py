"""JSON data adapter: maps game data files to beats through a small mapping config.

One ``[[sources.json]]`` table per kind of record:

    [[sources.json]]
    files = "data/clues/*.json"     # glob or list of globs, relative to the config
    kind = "interactable"           # constant kind, or kind_field = "type"
    items = "interactables"         # dotted path to the record list; omit if the file is the list/record
    keyed = true                    # items is an object of records keyed by ID (the key is the ID)
    optional = true                 # a file without items has no records (default: reported)
    id = "id"                       # record field holding the ID (default "id")
    id_prefix = "clue."             # optional prefix added to every beat ID
    requires = "requires"           # field(s) holding a condition (several fields are combined with all)
    effects = "effects"             # field(s) holding effects
    once = "once"                   # field holding a fact the beat needs unset and then sets (play once)
    tags = { location = "room" }    # beat tag -> record field

Every field name may be a dotted path into nested objects ("on_enter.once").
    static_tags = { chapter = "1" } # tags added to every beat from these files

``{file}`` in id_prefix and static_tags is the file's name without its extension.

Custom effect names are mapped with a top-level ``[effects]`` table, e.g.
``give_item = { set = "item.{}" }``, or ``play_sound = "ignore"``. Condition keys factgraph can't model
are listed in ``[conditions] opaque``.
"""

from __future__ import annotations

import glob
from pathlib import Path

from .. import jsonloc
from ..model import TRUE, All, Beat, Effect, FactTest, Finding, Not, Source
from ..syntax import SyntaxProblem, parse_condition, parse_effects


def load_json_source(entry: dict, root: Path, config: dict):
    beats: list[Beat] = []
    findings: list[Finding] = []
    effect_map = {**config.get("effects", {}), **entry.get("effects_map", {})}
    opaque = tuple(config.get("conditions", {}).get("opaque", []))
    keyed = bool(entry.get("keyed", False))

    for path in _expand(entry.get("files", []), root):
        rel = path.relative_to(root).as_posix()
        try:
            data = jsonloc.loads(path.read_text(encoding="utf-8"))
        except jsonloc.JSONLocError as exc:
            findings.append(Finding("adapter", f"invalid JSON: {exc}", Source(rel, exc.line)))
            continue
        if entry.get("optional") and entry.get("items") and _get(data, entry["items"]) is _MISSING:
            continue
        records = _records(data, entry.get("items"), keyed)
        if records is None:
            what = "keyed records" if keyed else "record list"
            findings.append(
                Finding("adapter", f"no {what} at '{entry.get('items')}'", Source(rel, jsonloc.line_of(data, 1)))
            )
            continue
        for key, record in records:
            beat, problems = _beat(record, key, rel, path.stem, entry, effect_map, opaque)
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


_MISSING = object()


def _get(record, path: str):
    """The value at a dotted field path, or _MISSING."""
    node = record
    for part in str(path).split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _records(data, items_path, keyed: bool):
    """(key, record) pairs; the key is None unless the records are keyed by ID."""
    node = _get(data, items_path) if items_path else data
    if keyed:
        return [(str(k), v) for k, v in node.items()] if isinstance(node, dict) else None
    if isinstance(node, dict):
        return [(None, node)]
    if isinstance(node, list):
        return [(None, item) for item in node]
    return None


def _fields(entry: dict, key: str, default: str) -> list[str]:
    value = entry.get(key, default)
    return [value] if isinstance(value, str) else list(value)


def _beat(record, key, rel: str, stem: str, entry: dict, effect_map: dict, opaque: tuple):
    line = jsonloc.line_of(record, 1)
    source = Source(rel, line)
    if not isinstance(record, dict):
        return None, [Finding("adapter", "record is not an object", source)]
    id_field = entry.get("id", "id")
    raw_id = key if key is not None else _get(record, id_field)
    if raw_id is _MISSING or raw_id is None:
        return None, [Finding("adapter", f"record has no '{id_field}' field", source)]
    beat_id = f"{entry.get('id_prefix', '').replace('{file}', stem)}{raw_id}"
    kind = str(record.get(entry["kind_field"], "")) if "kind_field" in entry else entry.get("kind", "record")

    problems: list[Finding] = []
    conditions = []
    for field in _fields(entry, "requires", "requires"):
        value = _get(record, field)
        if value is not _MISSING:
            try:
                conditions.append(parse_condition(value, rel, line, opaque))
            except SyntaxProblem as exc:
                problems.append(Finding("adapter", f"beat '{beat_id}': {exc}", exc.source))

    effects = []
    for field in _fields(entry, "effects", "effects"):
        value = _get(record, field)
        if value is not _MISSING:
            try:
                effects.extend(parse_effects(value, rel, line, effect_map))
            except SyntaxProblem as exc:
                problems.append(Finding("adapter", f"beat '{beat_id}': {exc}", exc.source))

    once = _get(record, entry["once"]) if "once" in entry else _MISSING
    if once is not _MISSING:
        once_source = Source(rel, jsonloc.line_of(once, line))
        if isinstance(once, str):
            conditions.append(Not(FactTest(str(once), source=once_source)))
            effects.append(Effect("set", str(once), True, once_source))
        else:
            problems.append(Finding("adapter", f"beat '{beat_id}': '{entry['once']}' needs a fact ID string", once_source))
    requires = TRUE if not conditions else conditions[0] if len(conditions) == 1 else All(tuple(conditions))

    tags = {k: str(v).replace("{file}", stem) for k, v in entry.get("static_tags", {}).items()}
    for tag, field in entry.get("tags", {}).items():
        value = _get(record, field)
        if value is not _MISSING and value is not None:
            tags[tag] = str(value)
    return Beat(beat_id, kind, source, requires, effects, tags), problems
