"""A6: softlocks, found by a bounded explicit search over the facts a goal depends on.

For each goal the project is sliced backwards first: the facts the goal reads, the beats that write
them, the facts those beats read, and so on. Everything else cannot affect the goal and is dropped,
which keeps the state space small. A breadth-first search then fires the sliced beats from the
initial state (a beat may fire whenever its condition holds, any number of times) and stops expanding
a state once the goal holds there.

A state from which no goal state can be reached is a softlock. Each beat that leads from a state where
the goal is still reachable into one where it is not is reported once, with the shortest path of
beats to it: that beat is the point of no return.

Facts nothing declares or writes may hold any value, so a test on them may go either way; ints use
the same window abstraction as the reachability analysis. When the search hits ``max_states`` the
unexplored states are assumed to reach the goal and a warning says the search stopped early.
"""

from __future__ import annotations

from collections import deque

from .evaluate import TOP, possible
from .model import Beat, Finding, Goal, Project, fact_tests
from .reach import apply_effect, int_bounds
from .symbols import Symbols, build_symbols

DEFAULT_MAX_STATES = 100_000


def softlocks(project: Project, symbols: Symbols | None = None, max_states: int = DEFAULT_MAX_STATES) -> list[Finding]:
    symbols = symbols or build_symbols(project)
    bounds = int_bounds(project)
    findings = []
    for goal in project.goals:
        findings += _search(project, symbols, bounds, goal, max_states)
    return findings


def _slice(project: Project, goal: Goal) -> tuple[list[str], list[Beat]]:
    """The facts that can affect the goal, and the beats that write them."""
    facts = {project.resolve(t.fact) for t in fact_tests(goal.condition)}
    chosen: set[int] = set()  # indexes into project.beats, so source order is kept
    changed = True
    while changed:
        changed = False
        for n, beat in enumerate(project.beats):
            if n in chosen or not any(project.resolve(e.fact) in facts for e in beat.effects):
                continue
            chosen.add(n)
            changed = True
            facts |= {project.resolve(t.fact) for t in fact_tests(beat.requires)}
    return sorted(facts), [b for n, b in enumerate(project.beats) if n in chosen]


def _search(project: Project, symbols: Symbols, bounds, goal: Goal, max_states: int) -> list[Finding]:
    facts, beats = _slice(project, goal)
    index = {fact: i for i, fact in enumerate(facts)}

    def initial(fact):
        declared = project.facts.get(fact)
        if declared is not None:
            return declared.initial
        return None if fact in symbols.writes else TOP

    def holds(cond, state) -> bool:
        return True in possible(cond, {f: {state[i]} for f, i in index.items()}, project.resolve)

    def successors(state, beat):
        states = [state]
        for effect in beat.effects:
            i = index.get(project.resolve(effect.fact))
            if i is None:
                continue  # a fact the goal does not depend on
            states = [
                s[:i] + (value,) + s[i + 1:]
                for s in states
                for value in apply_effect(effect, {s[i]}, bounds.get(facts[i]))
            ]
        return [s for s in dict.fromkeys(states) if s != state]

    start = tuple(initial(f) for f in facts)
    depth = {start: 0}
    parent: dict[tuple, tuple[tuple, Beat]] = {}
    edges: dict[tuple, list[tuple[Beat, tuple]]] = {}  # expanded states only
    goal_states = set()
    queue = deque([start])
    truncated = False
    while queue and not truncated:
        state = queue[0]
        if holds(goal.condition, state):
            goal_states.add(queue.popleft())
            continue
        out = []
        for beat in beats:
            if not holds(beat.requires, state):
                continue
            for nxt in successors(state, beat):
                if nxt not in depth:
                    if len(depth) >= max_states:
                        truncated = True
                        break
                    depth[nxt] = depth[state] + 1
                    parent[nxt] = (state, beat)
                    queue.append(nxt)
                out.append((beat, nxt))
            if truncated:
                break
        if not truncated:
            edges[queue.popleft()] = out

    # Live states can still reach the goal; unexpanded ones are assumed to.
    preds: dict[tuple, list[tuple]] = {}
    for state, out in edges.items():
        for _, nxt in out:
            preds.setdefault(nxt, []).append(state)
    live = goal_states | set(queue)
    work = list(live)
    while work:
        for prev in preds.get(work.pop(), []):
            if prev not in live:
                live.add(prev)
                work.append(prev)

    if start not in live:
        return [Finding("A6", f"goal '{goal.id}' can never be reached", goal.source)]
    sealing: dict[str, tuple[int, tuple, Beat]] = {}
    for state, out in edges.items():
        if state not in live:
            continue
        for beat, nxt in out:
            if nxt not in live and (beat.id not in sealing or depth[state] < sealing[beat.id][0]):
                sealing[beat.id] = (depth[state], state, beat)
    findings = []
    order = {beat.id: n for n, beat in enumerate(beats)}
    for _, state, beat in sorted(sealing.values(), key=lambda s: (s[0], order[s[2].id])):
        path = _path(parent, state) + [beat.id]
        findings.append(Finding(
            "A6",
            f"softlock: after {' -> '.join(path)}, goal '{goal.id}' can no longer be reached",
            beat.source,
        ))
    if truncated:
        findings.append(Finding(
            "A6",
            f"softlock search for goal '{goal.id}' stopped after {max_states} states;"
            " states beyond them were not checked (raise --max-states)",
            goal.source,
            "warning",
        ))
    return findings


def _path(parent, state) -> list[str]:
    path = []
    while state in parent:
        state, beat = parent[state]
        path.append(beat.id)
    return path[::-1]
