from builders import summary
from dm_export import AND, NOT, assign, boolean, call, cmp, dialogue_file, export, number, string, var

from factgraph.checks import check
from factgraph.config import load_project

CONFIG = """
    [facts."clue.lighthouse.letter"]
    type = "bool"

    [facts."case.keeper.state"]
    type = "string"
    values = ["open", "solved"]
    initial = "open"

    [facts."clues.found"]
    type = "int"

    [vocabulary.read]
    has = "fact"
    get = "fact"

    [vocabulary.write]
    set_fact = "set"
    give_item = { set = "item.{}" }

    [vocabulary]
    ignore = ["play_sound"]

    [[sources.dialogue_manager]]
    export = "build/dialogue.json"
    res_root = "game"
"""


def test_bad_condition_is_reported_at_its_dialogue_line(project, run):
    project.write("factgraph.toml", CONFIG)
    project.write(
        "build/dialogue.json",
        export(
            dialogue_file(
                "res://dialogue/keeper.dialogue",
                cues={"start": "1"},
                lines={
                    "0": {"id": "0", "type": "cue", "next_id": "1"},
                    "1": {"id": "1", "type": "dialogue", "character": "Keeper", "text": "Hello.", "next_id": "2"},
                    "2": {
                        "id": "2",
                        "type": "condition",
                        "next_id": "3",
                        "condition": {"expression": [call("has", string("clue.lighthouse.leter"))]},
                        "next_id_after": "4",
                    },
                    "3": {"id": "3", "type": "dialogue", "character": "Keeper", "text": "My letter!", "next_id": "4"},
                    "4": {"id": "4", "type": "goto", "next_id": "end", "is_snippet": False, "next_id_after": ""},
                },
            )
        ),
    )

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert lines == [
        "game/dialogue/keeper.dialogue:3: A1 undefined fact 'clue.lighthouse.leter'"
        " (did you mean 'clue.lighthouse.letter'?)"
    ]


KEEPER_LINES = {
    # ~ start
    "0": {"id": "0", "type": "cue", "next_id": "1"},
    # Keeper: Hello.
    "1": {"id": "1", "type": "dialogue", "character": "Keeper", "text": "Hello.", "next_id": "2"},
    # if has("clue.lighthouse.letter") and get("case.keeper.state") == "open":
    "2": {
        "id": "2", "type": "condition", "next_id": "3", "next_sibling_id": "4", "next_id_after": "6",
        "condition": {"expression": [
            call("has", string("clue.lighthouse.letter")), AND,
            call("get", string("case.keeper.state")), cmp("=="), string("open"),
        ]},
    },
    #     Keeper: You read it.
    "3": {"id": "3", "type": "dialogue", "character": "Keeper", "text": "You read it.", "next_id": "6"},
    # else:
    "4": {"id": "4", "type": "condition", "next_id": "5", "next_id_after": "6"},
    #     Keeper: Look around.
    "5": {"id": "5", "type": "dialogue", "character": "Keeper", "text": "Look around.", "next_id": "6"},
    # - Ask about the boat [if get("clues.found") >= 2 /]
    "6": {
        "id": "6", "type": "response", "text": "Ask about the boat", "responses": ["6", "8"],
        "condition": {"expression": [call("get", string("clues.found")), cmp(">="), number(2)]},
        "next_id": "7", "next_id_after": "10",
    },
    #     do give_item("oar")
    "7": {"id": "7", "type": "mutation", "mutation": {"expression": [call("give_item", string("oar"))]},
          "next_id": "10"},
    # - Leave
    "8": {"id": "8", "type": "response", "text": "Leave", "next_id": "9", "next_id_after": "10"},
    #     do play_sound("door")
    "9": {"id": "9", "type": "mutation", "mutation": {"expression": [call("play_sound", string("door"))]},
          "next_id": "10"},
    # do set_fact("case.keeper.state", "solved")
    "10": {"id": "10", "type": "mutation",
           "mutation": {"expression": [call("set_fact", string("case.keeper.state"), string("solved"))]},
           "next_id": "11"},
    # set clues.found += 1
    "11": {"id": "11", "type": "mutation",
           "mutation": {"expression": [var("clues"), {"type": "dot"}, var("found"), assign("+="), number(1)]},
           "next_id": "12"},
    # => END
    "12": {"id": "12", "type": "goto", "next_id": "end", "is_snippet": False, "next_id_after": ""},
}


def write_keeper(project, **extra):
    project.write("factgraph.toml", CONFIG)
    project.write(
        "build/dialogue.json",
        export(dialogue_file("res://dialogue/keeper.dialogue", KEEPER_LINES, cues={"start": "1"},
                             sources={"11": "set clues.found += 1"}, **extra)),
    )


def test_dialogue_lines_become_beats_gated_by_their_branches(project):
    from factgraph.model import TRUE, All, Effect, FactTest, Not

    write_keeper(project)

    loaded = load_project(project.config)

    branch = All((FactTest("clue.lighthouse.letter"), FactTest("case.keeper.state", "eq", "open")))
    beats = {b.id: (b.kind, b.requires, b.effects) for b in loaded.beats}
    assert beats == {
        "dialogue/keeper:2": ("dialogue_line", TRUE, []),
        "dialogue/keeper:4": ("dialogue_line", branch, []),
        "dialogue/keeper:6": ("dialogue_line", Not(branch), []),
        "dialogue/keeper:7": ("choice", FactTest("clues.found", "gt", 1), []),
        "dialogue/keeper:8": ("dialogue_effect", FactTest("clues.found", "gt", 1), [Effect("set", "item.oar")]),
        "dialogue/keeper:9": ("choice", TRUE, []),
        "dialogue/keeper:10": ("dialogue_effect", TRUE, []),
        "dialogue/keeper:11": ("dialogue_effect", TRUE, [Effect("set", "case.keeper.state", "solved")]),
        "dialogue/keeper:12": ("dialogue_effect", TRUE, []),
    }
    assert loaded.beats[0].tags == {"file": "game/dialogue/keeper.dialogue", "cue": "start", "character": "Keeper"}
    assert [str(f) for f in loaded.load_findings] == [
        "game/dialogue/keeper.dialogue:12: adapter unmapped mutation 'set clues.found += 1': variable 'clues'"
        " (enable vocabulary.variables to read variables as facts)"
    ]


def test_dialogue_manager_compile_errors_are_reported(project, run):
    write_keeper(project, errors=[{"line": 4, "column": 2, "error": 115, "message": "Invalid indentation."}])

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert "game/dialogue/keeper.dialogue:4: adapter Dialogue Manager: Invalid indentation." in lines


def test_inline_mutations_and_conditions_and_variables(project):
    from factgraph.model import TRUE, Effect, FactTest

    project.write("factgraph.toml", CONFIG.replace('ignore = ["play_sound"]', 'ignore = ["play_sound"]\n    variables = true'))
    project.write(
        "build/dialogue.json",
        export(dialogue_file(
            "res://dialogue/pier.dialogue",
            cues={"pier": "1"},
            lines={
                "0": {"id": "0", "type": "cue", "next_id": "1"},
                # Fisher: Saw a boat. [do set_fact("clue.boat.seen")] [if clues.found > 1]Odd.[/if] [ID:fisher_boat]
                "1": {"id": "1", "type": "dialogue", "character": "Fisher", "static_id": "fisher_boat",
                      "text": "Saw a boat. [do set_fact(\"clue.boat.seen\")] [if clues.found > 1]Odd.[/if]",
                      "next_id": "2"},
                # set clues.found += 1
                "2": {"id": "2", "type": "mutation",
                      "mutation": {"expression": [var("clues"), {"type": "dot"}, var("found"), assign("+="), number(1)]},
                      "next_id": "end"},
            },
            inline={"1": [
                {"code": "do", "expression": [call("set_fact", string("clue.boat.seen"))]},
                {"code": "if", "expression": [var("clues"), {"type": "dot"}, var("found"), cmp(">"), number(1)]},
            ]},
        )),
    )

    loaded = load_project(project.config)

    assert loaded.load_findings == []
    beats = {b.id: (b.kind, b.requires, b.effects) for b in loaded.beats}
    assert beats == {
        "fisher_boat": ("dialogue_line", TRUE, [Effect("set", "clue.boat.seen")]),
        "fisher_boat#if1": ("dialogue_fragment", FactTest("clues.found", "gt", 1), []),
        "dialogue/pier:3": ("dialogue_effect", TRUE, [Effect("inc", "clues.found", 1)]),
    }
