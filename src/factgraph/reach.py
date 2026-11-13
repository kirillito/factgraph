"""Reachability by a monotone fixed point over the values each fact may hold.

Starting from the initial values, every beat whose condition may be true fires and adds the values
its effects write. This repeats until nothing changes. Facts are treated independently and ``not``
is three-valued, so the result over-approximates every real play-through: a beat that never fires
here is certainly unreachable.

Ints are abstracted to the window of constants that conditions compare them with, plus one value
on each side standing for "anything beyond", which keeps the domain finite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evaluate import TOP, possible
from .model import Beat, Effect, Project, fact_tests
from .symbols import Symbols, build_symbols


@dataclass
class Origin:
    round: int
    beat: Beat | None  # None: the initial value


@dataclass
class Reach:
    project: Project
    fired: dict[str, int] = field(default_factory=dict)  # beat id -> first round it may fire
    values: dict[str, dict] = field(default_factory=dict)  # fact -> value -> Origin

    def may_fire(self, beat: Beat) -> bool:
        return beat.id in self.fired

    def value_sets(self) -> dict[str, set]:
        return {fact: set(vals) for fact, vals in self.values.items()}


def compute_reach(
    project: Project,
    symbols: Symbols | None = None,
    extra_initial: list[Effect] = (),
    exclude: set[str] = frozenset(),
) -> Reach:
    """Run the fixed point. ``extra_initial`` seeds additional values; ``exclude`` lists beats that never fire."""
    symbols = symbols or build_symbols(project)
    bounds = _int_bounds(project)
    reach = Reach(project)

    for fact in set(symbols.reads) | set(symbols.writes) | set(project.facts):
        declared = project.facts.get(fact)
        if declared is not None:
            initial = declared.initial
        elif fact in symbols.writes:
            initial = None  # unset until written
        else:
            initial = TOP  # read, never written or declared (A1): could be anything
        reach.values[fact] = {initial: Origin(0, None)}
    for effect in extra_initial:
        fact = project.resolve(effect.fact)
        for value in _apply(effect, set(reach.values.get(fact, {None: None})), bounds.get(fact)):
            reach.values.setdefault(fact, {}).setdefault(value, Origin(0, None))

    beats = [b for b in project.beats if b.id not in exclude]
    round_no = 0
    changed = True
    while changed:
        round_no += 1
        changed = False
        snapshot = reach.value_sets()
        new_values: list[tuple[str, object, Beat]] = []
        for beat in beats:
            if True not in possible(beat.requires, snapshot, project.resolve):
                continue
            if beat.id not in reach.fired:
                reach.fired[beat.id] = round_no
                changed = True
            for effect in beat.effects:
                fact = project.resolve(effect.fact)
                current = snapshot.get(fact, {None})
                if effect.op == "inc":
                    # Only values the beat's own condition allows (e.g. "inc while < 3").
                    current = {
                        v for v in current
                        if True in possible(beat.requires, {**snapshot, fact: {v}}, project.resolve)
                    }
                for value in _apply(effect, current, bounds.get(fact)):
                    new_values.append((fact, value, beat))
        for fact, value, beat in new_values:
            known = reach.values.setdefault(fact, {})
            if value not in known:
                known[value] = Origin(round_no, beat)
                changed = True
    return reach


def _apply(effect: Effect, current: set, bounds) -> set:
    if TOP in current:
        return {TOP}
    if effect.op == "set":
        return {effect.value}
    out = set()
    for value in current:
        base = 0 if value is None else value
        if not isinstance(base, int) or isinstance(base, bool):
            continue  # inc on a non-int: reported by A3, no effect here
        out |= _inc(base, effect.value, bounds)
    return out


def _inc(value: int, by: int, bounds) -> set:
    if bounds is None:
        return {value + by}
    lo, hi = bounds
    if value >= hi and by < 0:  # hi stands for "hi or more"
        return set(range(max(lo, hi + by), hi + 1))
    if value <= lo and by > 0:  # lo stands for "lo or less"
        return set(range(lo, min(hi, lo + by) + 1))
    return {min(hi, max(lo, value + by))}


def _int_bounds(project: Project) -> dict[str, tuple[int, int]]:
    """Per int fact: the window [min constant - 1, max constant + 1] that comparisons can tell apart."""
    consts: dict[str, set[int]] = {}

    def note(fact, value):
        if isinstance(value, int) and not isinstance(value, bool):
            consts.setdefault(project.resolve(fact), set()).add(value)

    conds = [b.requires for b in project.beats] + [g.condition for g in project.goals]
    for cond in conds:
        for test in fact_tests(cond):
            for v in test.value if test.op == "in" else (test.value,):
                note(test.fact, v)
    for beat in project.beats:
        for effect in beat.effects:
            if effect.op == "inc":
                consts.setdefault(project.resolve(effect.fact), set())
            elif effect.op == "set":
                note(effect.fact, effect.value)
    for fact_id, fact in project.facts.items():
        if fact.type == "int":
            note(fact_id, fact.initial)
            consts.setdefault(fact_id, set())
    bounds = {}
    for fact, values in consts.items():
        values = values | {0}
        bounds[fact] = (min(values) - 1, max(values) + 1)
    return bounds
