"""Answers for ``why`` and ``who``, written for people and coding agents alike."""

from __future__ import annotations

from .checks import show_value, suggest
from .evaluate import TOP, test_value
from .model import All, Beat, Condition, FactTest, Not, Project
from .reach import Reach, compute_reach
from .symbols import build_symbols


def find_beat(project: Project, beat_id: str) -> Beat | None:
    return next((b for b in project.beats if b.id == beat_id), None)


# --- why --------------------------------------------------------------------------


def why(project: Project, beat_id: str) -> tuple[int, list[str]]:
    beat = find_beat(project, beat_id)
    if beat is None:
        hint = suggest(beat_id, [b.id for b in project.beats])
        return 2, [f"no beat '{beat_id}'" + (f" (did you mean {hint}?)" if hint else "")]
    symbols = build_symbols(project)
    reach = compute_reach(project, symbols)
    if reach.may_fire(beat):
        return 0, _path(project, reach, beat)
    lines = [f"'{beat.id}' is unreachable ({beat.source}):"]
    for reason in _blockers(project, reach, symbols, beat.requires, True):
        lines.append(f"  {reason}")
    return 1, lines


def _path(project: Project, reach: Reach, target: Beat) -> list[str]:
    """Beats that produce the values the target needs, transitively, in firing order."""
    chosen: dict[str, Beat] = {}
    needed_by_beat: dict[str, list[tuple[str, object]]] = {}
    queue = list(_support(project, reach, target.requires, True) or [])
    seen_atoms = set()
    while queue:
        fact, value = queue.pop()
        if (fact, value) in seen_atoms:
            continue
        seen_atoms.add((fact, value))
        origin = reach.values.get(fact, {}).get(value)
        if origin is None or origin.beat is None:
            continue
        producer = origin.beat
        needed_by_beat.setdefault(producer.id, []).append((fact, value))
        if producer.id not in chosen:
            chosen[producer.id] = producer
            queue += _support(project, reach, producer.requires, True) or []
    order = sorted(chosen.values(), key=lambda b: (reach.fired[b.id], project.beats.index(b)))
    lines = [f"'{target.id}' is reachable. One path (facts are treated independently; confirm it in-game):"]
    for n, beat in enumerate(order + [target], 1):
        line = f"  {n}. {beat.source}: {beat.id} ({beat.kind})"
        atoms = needed_by_beat.get(beat.id, []) if beat is not target else []
        if atoms:
            line += " sets " + ", ".join(f"{f} = {show_value(v)}" for f, v in sorted(atoms, key=str))
        lines.append(line)
    return lines


def _support(project: Project, reach: Reach, cond: Condition, positive: bool):
    """Fact values that make ``cond`` (or its negation) true, preferring the earliest; None if impossible."""
    if isinstance(cond, FactTest):
        fact = project.resolve(cond.fact)
        options = [
            (origin.round, value)
            for value, origin in reach.values.get(fact, {}).items()
            if value is TOP or test_value(value, cond.op, cond.value) == positive
        ]
        if not options:
            return None
        _, value = min(options, key=lambda o: o[0])
        return [] if value is TOP else [(fact, value)]
    if isinstance(cond, Not):
        return _support(project, reach, cond.item, not positive)
    conjunctive = isinstance(cond, All) == positive
    parts = [_support(project, reach, item, positive) for item in cond.items]
    if conjunctive:
        if any(p is None for p in parts):
            return None
        return [atom for p in parts for atom in p]
    viable = [p for p in parts if p is not None]
    if not viable:
        return None
    return min(viable, key=lambda p: max((_round(reach, a) for a in p), default=0))


def _round(reach: Reach, atom) -> int:
    fact, value = atom
    return reach.values[fact][value].round


def _blockers(project: Project, reach: Reach, symbols, cond: Condition, positive: bool) -> list[str]:
    """Human-readable reasons why ``cond`` (or its negation) can never hold."""
    if _support(project, reach, cond, positive) is not None:
        return []
    if isinstance(cond, FactTest):
        fact = project.resolve(cond.fact)
        values = [v for v in reach.values.get(fact, {}) if v is not TOP]
        can_be = " or ".join(show_value(v) for v in values) if values else "unset"
        writers = [
            w.beat.id + ("" if reach.may_fire(w.beat) else " [unreachable]")
            for w in symbols.writes.get(fact, [])
        ]
        written_by = ", ".join(dict.fromkeys(writers)) or "nothing"
        return [f"needs '{fact}' {_describe(cond, positive)}, but it can only be {can_be} (written by: {written_by})"]
    if isinstance(cond, Not):
        return _blockers(project, reach, symbols, cond.item, not positive)
    reasons = []
    for item in cond.items:
        reasons += _blockers(project, reach, symbols, item, positive)
    return reasons


def _describe(test: FactTest, positive: bool) -> str:
    if test.op is None:
        return "to be set" if positive else "to be unset"
    if test.op == "eq":
        return f"{'=' if positive else '!='} {show_value(test.value)}"
    if test.op == "in":
        values = ", ".join(show_value(v) for v in test.value)
        return f"{'in' if positive else 'not in'} [{values}]"
    if test.op == "gt":
        return f"> {test.value}" if positive else f"<= {test.value}"
    return f"< {test.value}" if positive else f">= {test.value}"


# --- who --------------------------------------------------------------------------


def who(project: Project, fact_id: str) -> tuple[int, list[str]]:
    symbols = build_symbols(project)
    fact = project.resolve(fact_id)
    known = set(project.facts) | set(symbols.reads) | set(symbols.writes)
    if fact not in known:
        hint = suggest(fact, sorted(known))
        return 2, [f"no fact '{fact_id}' is declared, read or written" + (f" (did you mean {hint}?)" if hint else "")]
    lines = []
    if fact != fact_id:
        lines.append(f"'{fact_id}' is an alias of '{fact}'")
    declared = project.facts.get(fact)
    if declared is not None:
        extra = f", values {', '.join(show_value(v) for v in declared.values)}" if declared.values is not None else ""
        lines.append(f"{declared.source or 'config'}: declared {declared.type}, initial {show_value(declared.initial)}{extra}")
    entries = []
    for write in symbols.writes.get(fact, []):
        effect = write.effect
        what = f"set {show_value(effect.value)}" if effect.op == "set" else f"inc {effect.value}"
        entries.append((write.source, f"written by {write.beat.id} ({write.beat.kind}): {what}"))
    for read in symbols.reads.get(fact, []):
        who_reads = f"{read.beat.id} ({read.beat.kind})" if read.beat else "a goal"
        entries.append((read.source, f"read by {who_reads}: {_describe(read.test, True)}"))
    entries.sort(key=lambda e: (e[0].file, e[0].line) if e[0] else ("", 0))
    lines += [f"{source}: {text}" for source, text in entries]
    return 0, lines
