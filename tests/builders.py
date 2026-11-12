"""Build in-memory Projects from plain dicts in the core JSON syntax."""

from factgraph.model import Beat, Fact, Goal, Project, Source
from factgraph.syntax import parse_condition, parse_effects


def make_project(facts=None, beats=(), goals=None, aliases=None, write_only_allow=()):
    project = Project(aliases=dict(aliases or {}), write_only_allow=list(write_only_allow))
    for fact_id, decl in (facts or {}).items():
        project.facts[fact_id] = Fact(fact_id, decl.get("type", "bool"), decl.get("initial"), decl.get("values"))
    for n, b in enumerate(beats, 1):
        src = Source("beats.json", n)
        project.beats.append(
            Beat(
                b["id"],
                b.get("kind", "interactable"),
                src,
                parse_condition(b.get("requires"), src.file, n),
                parse_effects(b.get("effects"), src.file, n),
                dict(b.get("tags", {})),
            )
        )
    for goal_id, cond in (goals or {}).items():
        project.goals.append(Goal(goal_id, parse_condition(cond, "factgraph.toml")))
    return project


def summary(findings):
    """Findings as (check, message) pairs, sorted, for compact assertions."""
    return sorted((f.check, f.message) for f in findings)
