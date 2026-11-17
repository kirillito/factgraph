"""Content shapes beyond the basic syntax: more comparisons, opaque conditions, ignored effects, records keyed
by ID, nested fields, play-once flags, and the dialogue vocabulary's value reads and per-argument writes."""

import pytest
from builders import make_project, summary
from dm_export import call, cmp, dialogue_file, export, number, string

from factgraph.checks import check
from factgraph.config import load_project
from factgraph.evaluate import BOTH, evaluate, possible
from factgraph.model import TRUE, All, Effect, FactTest, Not, Unknown
from factgraph.syntax import SyntaxProblem, parse_condition, parse_effects


# --- ne, gte, lte --------------------------------------------------------------


def test_ne_gte_lte_parse_to_the_core_tests():
    assert parse_condition({"fact": "case.state", "ne": "open"}, "f") == Not(FactTest("case.state", "eq", "open"))
    assert parse_condition({"fact": "clues.found", "gte": 2}, "f") == FactTest("clues.found", "gt", 1)
    assert parse_condition({"fact": "clues.found", "lte": 2}, "f") == FactTest("clues.found", "lt", 3)


def test_gte_and_lte_need_an_integer():
    with pytest.raises(SyntaxProblem, match="'gte' needs an integer"):
        parse_condition({"fact": "clues.found", "gte": "2"}, "f")
    with pytest.raises(SyntaxProblem, match="'lte' needs an integer"):
        parse_condition({"fact": "clues.found", "lte": True}, "f")


def test_ne_gte_lte_semantics():
    ne = parse_condition({"fact": "x", "ne": 1}, "f")
    gte = parse_condition({"fact": "x", "gte": 2}, "f")
    assert evaluate(ne, {}) is True
    assert evaluate(ne, {"x": "1"}) is True
    assert evaluate(ne, {"x": 1}) is False
    assert [evaluate(gte, {"x": v}) for v in (1, 2, 3)] == [False, True, True]
    assert evaluate(gte, {"x": "3"}) is False


# --- opaque conditions -----------------------------------------------------------


def test_opaque_condition_keys_may_be_true_or_false():
    cond = parse_condition({"all": [{"fact": "door.open"}, {"skill": "strength", "gte": 3}]}, "f", opaque=["skill"])
    assert cond == All((FactTest("door.open"), Unknown("skill")))
    assert possible(Unknown("skill"), {}) == BOTH
    assert possible(Not(Unknown("skill")), {}) == BOTH


def test_opaque_keys_are_still_unrecognized_without_config():
    with pytest.raises(SyntaxProblem, match="unrecognized condition"):
        parse_condition({"skill": "strength", "gte": 3}, "f")


def test_beats_behind_opaque_conditions_stay_reachable(project, run):
    project.write(
        "factgraph.toml",
        """
        [conditions]
        opaque = ["skill"]

        [[sources.json]]
        files = "data/doors.json"
        kind = "interactable"
        """,
    )
    project.write(
        "data/doors.json",
        [
            {"id": "force_door", "requires": {"skill": "strength", "gte": 3}, "effects": ["door.open"]},
            {"id": "pick_lock", "requires": {"not": {"skill": "strength", "gte": 3}}, "effects": ["door.open"]},
            {"id": "enter", "requires": "door.open"},
        ],
    )

    code, lines = run("check", "--config", project.config)

    assert (code, lines) == (0, [])


# --- ignored effects ---------------------------------------------------------------


def test_effect_map_can_ignore_effects_that_touch_no_facts():
    effects = parse_effects([{"play_sound": "gull"}, {"set": "door.open"}], "f", 1, {"play_sound": "ignore"})
    assert effects == [Effect("set", "door.open", True)]


# --- keyed records, nested fields, play-once flags ------------------------------


def test_keyed_records_take_their_id_from_the_key(project):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/rooms/*.json"
        kind = "interactable"
        items = "objects"
        keyed = true
        id_prefix = "lamp_room."
        requires = "visible_if"
        effects = "on_use"
        """,
    )
    project.write(
        "data/rooms/lamp_room.json",
        """\
        {
          "objects": {
            "desk": {"on_use": [{"set": "clue.logbook"}]},
            "lamp": {
              "visible_if": {"fact": "clue.logbook"}
            }
          }
        }
        """,
    )

    loaded = load_project(project.config)

    assert loaded.load_findings == []
    assert [(b.id, b.source.line, b.requires, b.effects) for b in loaded.beats] == [
        ("lamp_room.desk", 3, TRUE, [Effect("set", "clue.logbook", True)]),
        ("lamp_room.lamp", 4, FactTest("clue.logbook"), []),
    ]


def test_keyed_needs_an_object(project, run):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/rooms.json"
        items = "objects"
        keyed = true
        """,
    )
    project.write("data/rooms.json", {"objects": [{"id": "desk"}]})

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert lines == ["data/rooms.json:1: adapter no keyed records at 'objects'"]


def test_fields_may_be_dotted_paths_and_once_plays_a_beat_once(project):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/locations/*.json"
        kind = "location"
        id_prefix = "enter."
        requires = "arrival.when"
        effects = "arrival.then"
        once = "arrival.once"
        tags = { music = "arrival.music" }
        """,
    )
    project.write(
        "data/locations/pier.json",
        {
            "id": "pier",
            "arrival": {
                "when": {"fact": "boat.fixed"},
                "then": [{"set": "pier.visited"}],
                "once": "pier.intro_seen",
                "music": "gulls",
            },
        },
    )

    [beat] = load_project(project.config).beats

    assert beat.id == "enter.pier"
    assert beat.requires == All((FactTest("boat.fixed"), Not(FactTest("pier.intro_seen"))))
    assert beat.effects == [Effect("set", "pier.visited", True), Effect("set", "pier.intro_seen", True)]
    assert beat.tags == {"music": "gulls"}


def test_once_alone_gates_on_its_flag(project):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/intro.json"
        once = "once"
        """,
    )
    project.write("data/intro.json", {"id": "intro", "once": "intro.seen"})

    [beat] = load_project(project.config).beats

    assert beat.requires == Not(FactTest("intro.seen"))
    assert beat.effects == [Effect("set", "intro.seen", True)]


def test_once_flag_counts_as_read_and_written():
    project = make_project(beats=[{"id": "a", "requires": {"not": "intro.seen"}, "effects": ["intro.seen"]}])
    assert summary(check(project)) == []


# --- dialogue: value reads, opaque reads, per-argument writes -------------------

DIALOGUE_CONFIG = """
    [facts."case.state"]
    type = "string"
    values = ["open", "solved"]
    initial = "open"

    [facts."keeper.name"]
    type = "string"

    [vocabulary.read]
    has = "fact"
    equals = "eq"
    skill = "opaque"

    [vocabulary.write.open_menu]
    cases = { naming = { set = "keeper.name", value = "Ada" }, solve = { set = "case.state", value = "solved" }, map = [] }

    [[sources.dialogue_manager]]
    export = "build/dialogue.json"
    res_root = "game"
"""


def _cond_line(n, nxt, expression, after):
    return {"id": n, "type": "condition", "next_id": nxt, "next_id_after": after,
            "condition": {"expression": expression}}


def _do_line(n, nxt, expression):
    return {"id": n, "type": "mutation", "mutation": {"expression": expression}, "next_id": nxt}


def _say(n, nxt, text):
    return {"id": n, "type": "dialogue", "character": "Keeper", "text": text, "next_id": nxt}


def test_dialogue_value_reads_opaque_reads_and_per_argument_writes(project):
    project.write("factgraph.toml", DIALOGUE_CONFIG)
    project.write(
        "build/dialogue.json",
        export(dialogue_file(
            "res://dialogue/keeper.dialogue",
            cues={"start": "1"},
            lines={
                "0": {"id": "0", "type": "cue", "next_id": "1"},
                "1": _do_line("1", "2", [call("open_menu", string("naming"))]),
                "2": _do_line("2", "3", [call("open_menu", string("map"))]),
                "3": _do_line("3", "4", [call("open_menu", string("solve"))]),
                "4": _cond_line("4", "5", [call("equals", string("case.state"), string("solved"))], "6"),
                "5": _say("5", "6", "Solved."),
                "6": _cond_line("6", "7", [call("skill", string("strength")), cmp(">="), number(3)], "end"),
                "7": _say("7", "end", "Strong."),
            },
        )),
    )

    loaded = load_project(project.config)

    assert loaded.load_findings == []
    beats = {b.id: (b.requires, b.effects) for b in loaded.beats}
    assert beats["dialogue/keeper:2"] == (TRUE, [Effect("set", "keeper.name", "Ada")])
    assert beats["dialogue/keeper:3"] == (TRUE, [])
    assert beats["dialogue/keeper:4"] == (TRUE, [Effect("set", "case.state", "solved")])
    assert beats["dialogue/keeper:6"] == (FactTest("case.state", "eq", "solved"), [])
    assert beats["dialogue/keeper:8"] == (Unknown("skill"), [])


def test_dialogue_per_argument_write_reports_an_unknown_argument(project, run):
    project.write("factgraph.toml", DIALOGUE_CONFIG)
    project.write(
        "build/dialogue.json",
        export(dialogue_file(
            "res://dialogue/keeper.dialogue",
            cues={"start": "1"},
            lines={
                "0": {"id": "0", "type": "cue", "next_id": "1"},
                "1": _do_line("1", "end", [call("open_menu", string("nameing"))]),
            },
        )),
    )

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert lines == [
        "game/dialogue/keeper.dialogue:2: adapter unmapped mutation:"
        " 'open_menu' has no case for 'nameing' (did you mean 'naming'?)"
    ]


def test_file_placeholder_in_id_prefix_and_static_tags(project):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/rooms/*.json"
        items = "objects"
        keyed = true
        id_prefix = "{file}/"
        static_tags = { location = "{file}" }
        """,
    )
    project.write("data/rooms/lamp_room.json", {"objects": {"desk": {}}})
    project.write("data/rooms/pier.json", {"objects": {"desk": {}}})

    beats = load_project(project.config).beats

    assert [(b.id, b.tags) for b in beats] == [
        ("lamp_room/desk", {"location": "lamp_room"}),
        ("pier/desk", {"location": "pier"}),
    ]


def test_optional_items_may_be_missing(project, run):
    project.write(
        "factgraph.toml",
        """
        [[sources.json]]
        files = "data/rooms/*.json"
        items = "objects"
        keyed = true
        optional = true
        """,
    )
    project.write("data/rooms/lamp_room.json", {"objects": {"desk": {}}})
    project.write("data/rooms/pier.json", {"id": "pier"})

    assert [b.id for b in load_project(project.config).beats] == ["desk"]
    assert run("check", "--config", project.config) == (0, [])
