"""The core model: facts, conditions, effects, beats, goals and findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

Value = Union[bool, int, str]


@dataclass(frozen=True)
class Source:
    file: str
    line: int = 0

    def __str__(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


@dataclass
class Fact:
    id: str
    type: str = "bool"  # bool | int | string
    initial: Value | None = None
    values: list[Value] | None = None  # declared value set, if any
    source: Source | None = None

    def __post_init__(self):
        if self.initial is None:
            self.initial = {"bool": False, "int": 0, "string": ""}[self.type]


# --- Conditions -------------------------------------------------------------


@dataclass(frozen=True)
class All:
    items: tuple["Condition", ...]


@dataclass(frozen=True)
class Any_:
    items: tuple["Condition", ...]


@dataclass(frozen=True)
class Not:
    item: "Condition"


@dataclass(frozen=True)
class FactTest:
    """A test on one fact. ``op`` is None (truthy), "eq", "gt", "lt" or "in"."""

    fact: str
    op: str | None = None
    value: object = None
    source: Source | None = field(default=None, compare=False)


Condition = Union[All, Any_, Not, FactTest]

TRUE: Condition = All(())


def fact_tests(cond: Condition):
    """Every FactTest inside a condition."""
    if isinstance(cond, FactTest):
        yield cond
    elif isinstance(cond, Not):
        yield from fact_tests(cond.item)
    else:
        for item in cond.items:
            yield from fact_tests(item)


# --- Effects ----------------------------------------------------------------


@dataclass(frozen=True)
class Effect:
    """A normalized fact write: ``set`` a value or ``inc`` by an amount."""

    op: str  # set | inc
    fact: str
    value: Value = True
    source: Source | None = field(default=None, compare=False)


# --- Beats, goals, project ----------------------------------------------------


@dataclass
class Beat:
    id: str
    kind: str
    source: Source
    requires: Condition = TRUE
    effects: list[Effect] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Goal:
    id: str
    condition: Condition
    tags: dict[str, str] = field(default_factory=dict)
    source: Source | None = None


@dataclass
class Finding:
    check: str  # A1..A7, or "config"/"adapter"
    message: str
    source: Source | None = None
    severity: str = "error"  # error | warning | info

    def __str__(self) -> str:
        where = f"{self.source}: " if self.source else ""
        suffix = "" if self.severity == "error" else f" [{self.severity}]"
        return f"{where}{self.check} {self.message}{suffix}"


@dataclass
class Project:
    root: str = "."
    facts: dict[str, Fact] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    beats: list[Beat] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    write_only_allow: list[str] = field(default_factory=list)
    # Problems found while loading (unmapped syntax, bad config), reported with the rest.
    load_findings: list[Finding] = field(default_factory=list)

    def resolve(self, fact_id: str) -> str:
        """Follow the alias table to the current fact ID."""
        seen = set()
        while fact_id in self.aliases and fact_id not in seen:
            seen.add(fact_id)
            fact_id = self.aliases[fact_id]
        return fact_id
