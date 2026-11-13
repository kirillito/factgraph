CONFIG = """
    [facts."clue.letter"]
    type = "bool"

    [facts."clue.boat"]
    type = "bool"

    [facts."case.state"]
    type = "string"
    values = ["open", "solved"]
    initial = "open"

    [[sources.json]]
    files = "data/*.json"
    kind = "interactable"
"""

BEATS = """\
[
  {"id": "desk", "effects": ["clue.letter"]},
  {"id": "read_letter", "requires": "clue.letter", "effects": ["clue.boat"]},
  {"id": "mooring", "requires": ["clue.boat", {"not": {"fact": "case.state", "eq": "solved"}}]},
  {"id": "closing", "requires": {"fact": "case.state", "eq": "solved"}, "effects": ["clue.letter"]}
]
"""


def test_why_lists_the_beats_that_make_a_beat_reachable(project, run):
    project.write("factgraph.toml", CONFIG)
    project.write("data/pier.json", BEATS)

    code, lines = run("why", "mooring", "--config", project.config)

    assert code == 0
    assert lines == [
        "'mooring' is reachable. One path (facts are treated independently; confirm it in-game):",
        "  1. data/pier.json:2: desk (interactable) sets clue.letter = true",
        "  2. data/pier.json:3: read_letter (interactable) sets clue.boat = true",
        "  3. data/pier.json:4: mooring (interactable)",
    ]


def test_why_explains_an_unreachable_beat(project, run):
    project.write("factgraph.toml", CONFIG)
    project.write("data/pier.json", BEATS)

    code, lines = run("why", "closing", "--config", project.config)

    assert code == 1
    assert lines == [
        "'closing' is unreachable (data/pier.json:5):",
        "  needs 'case.state' = 'solved', but it can only be 'open' (written by: nothing)",
    ]


def test_why_suggests_a_beat_id(project, run):
    project.write("factgraph.toml", CONFIG)
    project.write("data/pier.json", BEATS)

    code, lines = run("why", "moring", "--config", project.config)

    assert (code, lines) == (2, ["no beat 'moring' (did you mean 'mooring'?)"])


def test_who_lists_every_read_and_write_with_its_place(project, run):
    project.write("factgraph.toml", CONFIG + '\n    [aliases]\n    "clue.old_letter" = "clue.letter"\n')
    project.write("data/pier.json", BEATS)

    code, lines = run("who", "clue.old_letter", "--config", project.config)

    assert code == 0
    assert lines == [
        "'clue.old_letter' is an alias of 'clue.letter'",
        "factgraph.toml: declared bool, initial false",
        "data/pier.json:2: written by desk (interactable): set true",
        "data/pier.json:3: read by read_letter (interactable): to be set",
        "data/pier.json:5: written by closing (interactable): set true",
    ]


def test_who_suggests_a_fact_id(project, run):
    project.write("factgraph.toml", CONFIG)
    project.write("data/pier.json", BEATS)

    assert run("who", "clue.leter", "--config", project.config) == (
        2, ["no fact 'clue.leter' is declared, read or written (did you mean 'clue.letter'?)"]
    )
