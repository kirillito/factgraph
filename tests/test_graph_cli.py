CONFIG = """
    [facts."clue.letter"]
    type = "bool"

    [facts."case.state"]
    type = "string"
    values = ["open", "solved"]
    initial = "open"

    [goals."chapter.1.complete"]
    requires = { fact = "case.state", eq = "solved" }
    tags = { chapter = "1" }

    [[sources.json]]
    files = "data/*.json"
    kind = "interactable"
    tags = { chapter = "chapter", location = "room" }
"""

BEATS = [
    {"id": "desk", "chapter": "1", "room": "study", "effects": ["clue.letter"]},
    {"id": "accuse", "chapter": "1", "room": "harbour", "requires": "clue.letter",
     "effects": [{"set": "case.state", "value": "solved"}]},
    {"id": "early_exit", "chapter": "1", "room": "harbour", "requires": {"not": "clue.letter"}},
    {"id": "epilogue", "chapter": "2", "room": "harbour", "requires": {"fact": "case.state", "eq": "closed"}},
    {"id": "flavour", "chapter": "1", "room": "study"},
]


def write(project):
    project.write("factgraph.toml", CONFIG)
    project.write("data/beats.json", BEATS)


def test_mermaid_graph_of_a_chapter(project, run):
    write(project)

    code, lines = run("graph", "--chapter", "1", "--config", project.config)

    assert code == 0
    assert lines == [
        "flowchart LR",
        '  subgraph g1["study"]',
        '    n1["desk<br/><i>interactable</i>"]:::beat',
        "  end",
        '  subgraph g2["harbour"]',
        '    n2["accuse<br/><i>interactable</i>"]:::beat',
        '    n3["early_exit<br/><i>interactable</i>"]:::beat',
        "  end",
        '  n4(["case.state"]):::fact',
        '  n5(["clue.letter"]):::fact',
        '  n6{{"chapter.1.complete"}}:::goal',
        "  n1 --> n5",
        '  n2 -- "= \'solved\'" --> n4',
        "  n5 --> n2",
        '  n5 -. "not" .-> n3',
        '  n4 -- "= \'solved\'" --> n6',
        "  classDef beat fill:#eef,stroke:#446",
        "  classDef fact fill:#efe,stroke:#464",
        "  classDef goal fill:#ffe,stroke:#864",
        "  classDef unreachable fill:#fee,stroke:#c00,stroke-dasharray:4",
    ]


def test_unreachable_beats_are_marked(project, run):
    write(project)

    code, lines = run("graph", "--chapter", "2", "--config", project.config)

    assert '    n1["epilogue<br/><i>interactable</i>"]:::unreachable' in lines


def test_dot_graph(project, run):
    write(project)

    code, lines = run("graph", "--chapter", "1", "--focus", "accuse", "--depth", "1", "--format", "dot",
                      "--config", project.config)

    assert code == 0
    assert lines == [
        "digraph factgraph {",
        "  rankdir=LR;",
        '  node [fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=9];',
        "  subgraph cluster_1 {",
        '    label="harbour";',
        '    n1 [shape=box, label="accuse\\ninteractable", style=filled, fillcolor="#eeeeff"];',
        "  }",
        '  n2 [shape=box, style="rounded,filled", fillcolor="#eeffee", label="case.state"];',
        '  n3 [shape=box, style="rounded,filled", fillcolor="#eeffee", label="clue.letter"];',
        '  n1 -> n2 [label="= \'solved\'"];',
        "  n3 -> n1;",
        "}",
    ]


def test_focus_keeps_the_neighbourhood_only(project, run):
    write(project)

    _, lines = run("graph", "--focus", "clue.letter", "--depth", "1", "--config", project.config)
    text = "\n".join(lines)

    assert all(name in text for name in ("desk", "accuse", "early_exit", "clue.letter"))
    assert "case.state" not in text and "chapter.1.complete" not in text and "epilogue" not in text


def test_focus_on_an_unknown_name_suggests_one(project, run):
    write(project)

    assert run("graph", "--focus", "clue.leter", "--config", project.config) == (
        2, ["nothing named 'clue.leter' in the graph (did you mean 'clue.letter'?)"]
    )


def test_dialogue_lines_with_the_same_gate_are_merged(project, run):
    project.write("factgraph.toml", """
        [facts."clue.letter"]
        type = "bool"
        initial = true

        [[sources.json]]
        files = "lines.json"
        kind = "dialogue_line"
        static_tags = { file = "keeper.dialogue", cue = "start" }
    """)
    project.write("lines.json", [
        {"id": "keeper:3", "requires": "clue.letter"},
        {"id": "keeper:4", "requires": "clue.letter"},
        {"id": "keeper:5", "requires": "clue.letter"},
        {"id": "keeper:7", "requires": {"not": "clue.letter"}},
    ])

    _, lines = run("graph", "--config", project.config)

    assert lines[1:5] == [
        '  subgraph g1["keeper.dialogue"]',
        '    n1["keeper:3 (+2 lines)<br/><i>dialogue_line</i>"]:::beat',
        '    n2["keeper:7<br/><i>dialogue_line</i>"]:::unreachable',
        "  end",
    ]
