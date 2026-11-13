"""Flow graphs for humans: beats, the facts they read and write, and goals (Mermaid or DOT).

Beats are boxes, facts are rounded, goals are hexagons. An edge beat -> fact is a write, an edge
fact -> beat or fact -> goal is a read; reads under ``not`` are dotted. Beats that touch no fact are
left out, dialogue lines with the same gate in the same cue are folded into one node, and beats
without the grouping tag are clustered by their dialogue file, so a chapter stays readable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .checks import show_value
from .model import Beat, Condition, FactTest, Not, Project
from .reach import compute_reach


@dataclass
class Node:
    id: str  # internal key: "beat:<id>", "fact:<id>" or "goal:<id>"
    label: str
    kind: str  # beat | fact | goal
    sublabel: str = ""
    cls: str = ""
    group: str = ""


@dataclass
class Edge:
    src: str
    dst: str
    label: str = ""
    negated: bool = False


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)


class GraphError(Exception):
    pass


def build_graph(
    project: Project,
    chapter: str | None = None,
    focus: str | None = None,
    depth: int = 2,
    group_by: str = "location",
) -> Graph:
    reach = compute_reach(project)
    beats = [b for b in project.beats if chapter is None or b.tags.get("chapter") == chapter]
    goals = [g for g in project.goals if chapter is None or g.tags.get("chapter") in (None, chapter)]

    graph = Graph()
    write_edges, read_edges, goal_edges = [], [], []
    for beat, merged in _merge_dialogue(beats):
        key = f"beat:{beat.id}"
        writes = [
            Edge(key, f"fact:{project.resolve(e.fact)}", _write_label(e)) for e in beat.effects
        ]
        reads = [
            Edge(f"fact:{project.resolve(t.fact)}", key, _read_label(t, positive), not positive)
            for t, positive in _tests(beat.requires)
        ]
        if not writes and not reads:
            continue
        cls = "beat" if reach.may_fire(beat) else "unreachable"
        label = beat.id + (f" (+{merged} lines)" if merged else "")
        group = beat.tags.get(group_by) or beat.tags.get("file", "").rsplit("/", 1)[-1]
        graph.nodes[key] = Node(key, label, "beat", beat.kind, cls, group)
        write_edges += writes
        read_edges += reads
    for goal in goals:
        key = f"goal:{goal.id}"
        graph.nodes[key] = Node(key, goal.id, "goal", cls="goal")
        goal_edges += [
            Edge(f"fact:{project.resolve(t.fact)}", key, _read_label(t, positive), not positive)
            for t, positive in _tests(goal.condition)
        ]
    edges = _dedupe(write_edges + read_edges + goal_edges)
    for fact in sorted({e.dst for e in edges if e.dst.startswith("fact:")} | {e.src for e in edges if e.src.startswith("fact:")}):
        graph.nodes[fact] = Node(fact, fact.removeprefix("fact:"), "fact", cls="fact")
    # Keep beats first, then facts, then goals.
    order = {"beat": 0, "fact": 1, "goal": 2}
    graph.nodes = dict(sorted(graph.nodes.items(), key=lambda kv: order[kv[1].kind]))
    graph.edges = edges

    if focus is not None:
        graph = _focus(graph, project, focus, depth)
    return graph


# --- building helpers ---------------------------------------------------------------


DIALOGUE_KINDS = ("dialogue_line", "choice", "dialogue_effect")


def _merge_dialogue(beats: list[Beat]) -> list[tuple[Beat, int]]:
    """Fold effect-free dialogue lines into the first dialogue beat with the same file, cue and gate.

    Returns (beat, number of lines folded into it).
    """
    anchor: dict[tuple, Beat] = {}
    extra: dict[str, int] = {}
    out: list[Beat] = []
    for beat in beats:
        if beat.kind not in DIALOGUE_KINDS:
            out.append(beat)
            continue
        key = (beat.tags.get("file"), beat.tags.get("cue"), beat.requires)
        if key in anchor and beat.kind == "dialogue_line" and not beat.effects:
            extra[anchor[key].id] = extra.get(anchor[key].id, 0) + 1
            continue
        anchor.setdefault(key, beat)
        out.append(beat)
    return [(beat, extra.get(beat.id, 0)) for beat in out]


def _tests(cond: Condition, positive: bool = True):
    """(FactTest, polarity) for each test in a condition; polarity flips under ``not``."""
    if isinstance(cond, FactTest):
        yield cond, positive
    elif isinstance(cond, Not):
        yield from _tests(cond.item, not positive)
    else:
        for item in cond.items:
            yield from _tests(item, positive)


def _write_label(effect) -> str:
    if effect.op == "inc":
        return f"+{effect.value}" if effect.value >= 0 else str(effect.value)
    return "" if effect.value is True else f"= {show_value(effect.value)}"


def _read_label(test: FactTest, positive: bool) -> str:
    if test.op is None:
        return "" if positive else "not"
    if test.op == "eq":
        return f"{'=' if positive else '!='} {show_value(test.value)}"
    if test.op == "in":
        values = ", ".join(show_value(v) for v in test.value)
        return f"{'in' if positive else 'not in'} {values}"
    if test.op == "gt":
        return f"> {test.value}" if positive else f"<= {test.value}"
    return f"< {test.value}" if positive else f">= {test.value}"


def _dedupe(edges: list[Edge]) -> list[Edge]:
    seen, out = set(), []
    for e in edges:
        key = (e.src, e.dst, e.label, e.negated)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _focus(graph: Graph, project: Project, focus: str, depth: int) -> Graph:
    starts = [k for k in (f"beat:{focus}", f"fact:{project.resolve(focus)}", f"goal:{focus}") if k in graph.nodes]
    if not starts:
        from .checks import suggest

        names = [n.label for n in graph.nodes.values()]
        hint = suggest(focus, names)
        raise GraphError(f"nothing named '{focus}' in the graph" + (f" (did you mean {hint}?)" if hint else ""))
    out_edges: dict[str, list[str]] = {}
    in_edges: dict[str, list[str]] = {}
    for e in graph.edges:
        out_edges.setdefault(e.src, []).append(e.dst)
        in_edges.setdefault(e.dst, []).append(e.src)
    keep = set(starts)
    for neighbours in (out_edges, in_edges):  # downstream, then upstream
        queue = deque((s, 0) for s in starts)
        while queue:
            node, dist = queue.popleft()
            if dist == depth:
                continue
            for nxt in neighbours.get(node, []):
                if nxt not in keep:
                    keep.add(nxt)
                    queue.append((nxt, dist + 1))
    return Graph(
        {k: n for k, n in graph.nodes.items() if k in keep},
        [e for e in graph.edges if e.src in keep and e.dst in keep],
    )


# --- rendering ----------------------------------------------------------------------


def to_mermaid(graph: Graph) -> str:
    ids = {key: f"n{i}" for i, key in enumerate(_render_order(graph), 1)}
    lines = ["flowchart LR"]

    def node_line(node: Node) -> str:
        text = _mermaid_text(node.label)
        if node.kind == "beat":
            sub = f"<br/><i>{_mermaid_text(node.sublabel)}</i>" if node.sublabel else ""
            return f'{ids[node.id]}["{text}{sub}"]:::{node.cls}'
        if node.kind == "fact":
            return f'{ids[node.id]}(["{text}"]):::fact'
        return f'{ids[node.id]}{{{{"{text}"}}}}:::goal'

    groups = _groups(graph)
    for n, (group, members) in enumerate(groups.items(), 1):
        if group:
            lines.append(f'  subgraph g{n}["{_mermaid_text(group)}"]')
            lines += [f"    {node_line(m)}" for m in members]
            lines.append("  end")
    for member in groups.get("", []):
        lines.append(f"  {node_line(member)}")
    for node in graph.nodes.values():
        if node.kind != "beat":
            lines.append(f"  {node_line(node)}")
    for e in graph.edges:
        a, b = ids[e.src], ids[e.dst]
        label = _mermaid_text(e.label)
        if e.negated:
            lines.append(f'  {a} -. "{label}" .-> {b}' if label else f"  {a} -.-> {b}")
        else:
            lines.append(f'  {a} -- "{label}" --> {b}' if label else f"  {a} --> {b}")
    lines += [
        "  classDef beat fill:#eef,stroke:#446",
        "  classDef fact fill:#efe,stroke:#464",
        "  classDef goal fill:#ffe,stroke:#864",
        "  classDef unreachable fill:#fee,stroke:#c00,stroke-dasharray:4",
    ]
    return "\n".join(lines)


def to_dot(graph: Graph) -> str:
    ids = {key: f"n{i}" for i, key in enumerate(_render_order(graph), 1)}
    lines = [
        "digraph factgraph {",
        "  rankdir=LR;",
        '  node [fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=9];',
    ]

    def node_line(node: Node) -> str:
        if node.kind == "beat":
            label = _dot_text(node.label) + (f"\\n{_dot_text(node.sublabel)}" if node.sublabel else "")
            style = 'style="filled,dashed", fillcolor="#ffeeee", color="#cc0000"' if node.cls == "unreachable" \
                else 'style=filled, fillcolor="#eeeeff"'
            return f'{ids[node.id]} [shape=box, label="{label}", {style}];'
        if node.kind == "fact":
            return f'{ids[node.id]} [shape=box, style="rounded,filled", fillcolor="#eeffee", label="{_dot_text(node.label)}"];'
        return f'{ids[node.id]} [shape=hexagon, style=filled, fillcolor="#ffffee", label="{_dot_text(node.label)}"];'

    groups = _groups(graph)
    for n, (group, members) in enumerate(groups.items(), 1):
        if group:
            lines.append(f"  subgraph cluster_{n} {{")
            lines.append(f'    label="{_dot_text(group)}";')
            lines += [f"    {node_line(m)}" for m in members]
            lines.append("  }")
    for member in groups.get("", []):
        lines.append(f"  {node_line(member)}")
    for node in graph.nodes.values():
        if node.kind != "beat":
            lines.append(f"  {node_line(node)}")
    for e in graph.edges:
        attrs = []
        if e.label:
            attrs.append(f'label="{_dot_text(e.label)}"')
        if e.negated:
            attrs.append("style=dashed")
        suffix = f" [{', '.join(attrs)}]" if attrs else ""
        lines.append(f"  {ids[e.src]} -> {ids[e.dst]}{suffix};")
    lines.append("}")
    return "\n".join(lines)


def _groups(graph: Graph) -> dict[str, list[Node]]:
    groups: dict[str, list[Node]] = {}
    for node in graph.nodes.values():
        if node.kind == "beat":
            groups.setdefault(node.group, []).append(node)
    if "" in groups:  # ungrouped beats render last; keep the dict order for the rest
        groups[""] = groups.pop("")
    return groups


def _render_order(graph: Graph) -> list[str]:
    beats = [n.id for members in _groups(graph).values() for n in members]
    return beats + [k for k, n in graph.nodes.items() if n.kind != "beat"]


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;")


def _dot_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
