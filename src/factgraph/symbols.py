"""Symbol table: where each fact is read and written, after alias resolution."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .model import Beat, Effect, FactTest, Project, Source, fact_tests


@dataclass
class Read:
    fact: str
    test: FactTest
    beat: Beat | None  # None for a goal
    source: Source | None


@dataclass
class Write:
    fact: str
    effect: Effect
    beat: Beat
    source: Source | None


@dataclass
class Symbols:
    reads: dict[str, list[Read]] = field(default_factory=lambda: defaultdict(list))
    writes: dict[str, list[Write]] = field(default_factory=lambda: defaultdict(list))


def build_symbols(project: Project) -> Symbols:
    symbols = Symbols()
    for beat in project.beats:
        for test in fact_tests(beat.requires):
            fact = project.resolve(test.fact)
            symbols.reads[fact].append(Read(fact, test, beat, test.source or beat.source))
        for effect in beat.effects:
            fact = project.resolve(effect.fact)
            symbols.writes[fact].append(Write(fact, effect, beat, effect.source or beat.source))
    for goal in project.goals:
        for test in fact_tests(goal.condition):
            fact = project.resolve(test.fact)
            symbols.reads[fact].append(Read(fact, test, None, test.source or goal.source))
    return symbols
