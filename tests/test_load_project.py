from factgraph.config import load_project
from factgraph.model import Effect, FactTest, Not, Source


def test_json_adapter_maps_records_to_beats(project):
    project.write(
        "factgraph.toml",
        """
        [effects]
        give_item = { set = "item.{}" }

        [[sources.json]]
        files = "data/deductions/*.json"
        kind = "deduction"
        id_prefix = "deduction."
        requires = ["clues", "requires"]
        effects = "on_solve"
        tags = { case = "case" }
        static_tags = { chapter = "1" }
        """,
    )
    project.write(
        "data/deductions/keeper.json",
        """\
        [
          {
            "id": "keeper_left_by_boat",
            "case": "keeper",
            "clues": ["clue.boat.missing"],
            "requires": {
              "not": {"fact": "case.keeper.solved"}
            },
            "on_solve": [{"give_item": "oar"}, {"inc": "deductions.count"}]
          }
        ]
        """,
    )

    loaded = load_project(project.config)

    assert loaded.load_findings == []
    [beat] = loaded.beats
    assert (beat.id, beat.kind, beat.source, beat.tags) == (
        "deduction.keeper_left_by_boat",
        "deduction",
        Source("data/deductions/keeper.json", 2),
        {"chapter": "1", "case": "keeper"},
    )
    clue_test, not_solved = beat.requires.items[0].items[0], beat.requires.items[1]
    assert clue_test == FactTest("clue.boat.missing")
    assert clue_test.source == Source("data/deductions/keeper.json", 5)
    assert not_solved == Not(FactTest("case.keeper.solved"))
    assert not_solved.item.source.line == 7
    assert beat.effects == [Effect("set", "item.oar", True), Effect("inc", "deductions.count", 1)]


def test_unmapped_syntax_is_reported_not_guessed(project, run):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/*.json"
        kind = "interactable"
        """,
    )
    project.write(
        "data/well.json",
        """\
        [
          {"id": "well", "requires": {"fact": "rope.length", "ge": 3}},
          {"id": "bucket", "effects": [{"play_sound": "splash"}]}
        ]
        """,
    )

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert lines == [
        "data/well.json:2: adapter beat 'well': unrecognized condition {'fact': 'rope.length', 'ge': 3}",
        "data/well.json:3: adapter beat 'bucket': unrecognized effect {'play_sound': 'splash'}",
    ]


def test_facts_file_declares_facts_and_aliases(project, run):
    project.write(
        "factgraph.toml",
        """
        [project]
        facts_file = "facts.json"

        [[sources.json]]
        files = "data/*.json"
        """,
    )
    project.write(
        "facts.json",
        {
            "facts": {"lamp.lit": {"type": "bool", "initial": True}},
            "aliases": {"lighthouse.lamp_lit": "lamp.lit"},
        },
    )
    project.write("data/tower.json", [{"id": "climb", "requires": "lighthouse.lamp_lit"}])

    assert run("check", "--config", project.config) == (0, [])
