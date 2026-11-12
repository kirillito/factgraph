"""Static checks over a Project. ``check(project)`` runs them all and returns findings."""

from __future__ import annotations

from fnmatch import fnmatchcase

from .model import Finding, Project
from .symbols import Symbols, build_symbols


def check(project: Project) -> list[Finding]:
    symbols = build_symbols(project)
    findings = list(project.load_findings)
    findings += undefined_facts(project, symbols)
    findings += write_only_facts(project, symbols)
    findings += type_misuse(project, symbols)
    return findings


def type_of(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def show_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f"'{value}'"
    return str(value)


def type_misuse(project: Project, symbols: Symbols) -> list[Finding]:
    """A3: comparisons and writes that don't fit a declared fact's type or value set."""
    findings = []
    for fact_id, reads in symbols.reads.items():
        fact = project.facts.get(fact_id)
        if fact is None:
            continue
        for read in reads:
            for message in _condition_misuse(fact, read.test.op, read.test.value):
                findings.append(Finding("A3", message, read.source))
    for fact_id, writes in symbols.writes.items():
        fact = project.facts.get(fact_id)
        if fact is None:
            continue
        for write in writes:
            for message in _effect_misuse(fact, write.effect):
                findings.append(Finding("A3", message, write.source))
    return findings


def _effect_misuse(fact, effect):
    if effect.op == "inc":
        if fact.type != "int":
            yield f"'{fact.id}' incremented but is {fact.type}"
        return
    yield from _value_misuse(fact, effect.value, "set to")


def _condition_misuse(fact, op, value):
    name = f"'{fact.id}'"
    if op is None:
        return
    if op in ("gt", "lt"):
        if fact.type != "int":
            yield f"{name} compared with '{op}' but is {fact.type}"
        elif type_of(value) != "int":
            yield f"{name} compared with '{op}' {type_of(value)} {show_value(value)} but is int"
        return
    for v in value if op == "in" else (value,):
        yield from _value_misuse(fact, v, "compared with")


def _value_misuse(fact, value, verb: str):
    name = f"'{fact.id}'"
    if type_of(value) != fact.type:
        yield f"{name} {verb} {type_of(value)} {show_value(value)} but is {fact.type}"
    elif fact.values is not None and value not in fact.values:
        yield f"{name} {verb} value {show_value(value)} outside its declared values"


def write_only_facts(project: Project, symbols: Symbols) -> list[Finding]:
    """A2: a fact that is written but never read (unless allow-listed)."""
    findings = []
    for fact, writes in symbols.writes.items():
        if fact in symbols.reads or any(fnmatchcase(fact, pat) for pat in project.write_only_allow):
            continue
        findings.append(Finding("A2", f"write-only fact '{fact}'", writes[0].source, "warning"))
    return findings


def undefined_facts(project: Project, symbols: Symbols) -> list[Finding]:
    """A1: a fact that is read but never written and never declared."""
    known = sorted(set(project.facts) | set(symbols.writes))
    findings = []
    for fact, reads in symbols.reads.items():
        if fact in project.facts or fact in symbols.writes:
            continue
        hint = suggest(fact, known)
        message = f"undefined fact '{fact}'" + (f" (did you mean {hint}?)" if hint else "")
        for read in reads:
            findings.append(Finding("A1", message, read.source))
    return findings


def suggest(name: str, candidates: list[str], limit: int = 3) -> str:
    """The nearest candidates by edit distance, formatted for a message ('' if none are close)."""
    budget = max(2, len(name) // 5)
    scored = sorted((edit_distance(name, c), c) for c in candidates if c != name)
    close = [c for d, c in scored if d <= budget]
    if not close:
        return ""
    best = edit_distance(name, close[0])
    close = [c for c in close if edit_distance(name, c) == best][:limit]
    return " or ".join(f"'{c}'" for c in close)


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
