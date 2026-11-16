from builders import make_project, summary

from factgraph.checks import check

FACTS = {
    "clue.letter": {"type": "bool"},
    "clue.lamp": {"type": "bool"},
    "lamp.lit": {"type": "bool"},
    "case.state": {"type": "string", "values": ["open", "solved"], "initial": "open"},
    "coins": {"type": "int", "initial": 1},
}

GOAL = {"chapter.1.complete": {"fact": "case.state", "eq": "solved"}}

LIGHTHOUSE = [
    {"id": "desk", "effects": ["clue.letter"]},
    {"id": "lamp_room", "requires": {"not": "lamp.lit"}, "effects": ["clue.lamp"]},
    {"id": "relight_lamp", "effects": ["lamp.lit"]},
    {"id": "solve", "requires": ["clue.letter", "clue.lamp"],
     "effects": [{"set": "case.state", "value": "solved"}]},
]


def softlocks(findings):
    return [(f.check, f.message, f.severity) for f in findings if f.check == "A6"]


def test_softlock_is_reported_with_its_witness_path():
    project = make_project(facts=FACTS, beats=LIGHTHOUSE, goals=GOAL)

    findings = check(project, deep=True)

    assert softlocks(findings) == [(
        "A6",
        "softlock: after relight_lamp, goal 'chapter.1.complete' can no longer be reached",
        "error",
    )]
    a6 = next(f for f in findings if f.check == "A6")
    assert str(a6.source) == "beats.json:3"  # the beat that seals it


def test_softlock_search_is_opt_in():
    project = make_project(facts=FACTS, beats=LIGHTHOUSE, goals=GOAL)

    assert softlocks(check(project)) == []


def test_another_way_to_the_goal_means_no_softlock():
    beats = LIGHTHOUSE + [{"id": "keeper_log", "effects": ["clue.lamp"]}]
    project = make_project(facts=FACTS, beats=beats, goals=GOAL)

    assert softlocks(check(project, deep=True)) == []


def test_witness_path_lists_the_beats_leading_to_the_softlock():
    beats = [
        {"id": "desk", "effects": ["clue.letter"]},
        {"id": "lamp_room", "requires": {"not": "lamp.lit"}, "effects": ["clue.lamp"]},
        {"id": "relight_lamp", "requires": "clue.letter", "effects": ["lamp.lit"]},
        {"id": "solve", "requires": ["clue.letter", "clue.lamp"],
         "effects": [{"set": "case.state", "value": "solved"}]},
    ]
    project = make_project(facts=FACTS, beats=beats, goals=GOAL)

    assert softlocks(check(project, deep=True)) == [(
        "A6",
        "softlock: after desk -> relight_lamp, goal 'chapter.1.complete' can no longer be reached",
        "error",
    )]


def test_spending_a_counter_can_softlock():
    beats = [
        {"id": "buy_bread", "requires": {"fact": "coins", "gt": 0}, "effects": [{"inc": "coins", "by": -1}]},
        {"id": "ferry", "requires": {"fact": "coins", "gt": 0},
         "effects": [{"set": "case.state", "value": "solved"}]},
        {"id": "street_music", "requires": {"fact": "coins", "lt": 0}, "effects": [{"inc": "coins"}]},
    ]
    project = make_project(facts=FACTS, beats=beats, goals=GOAL)

    assert softlocks(check(project, deep=True)) == [(
        "A6",
        "softlock: after buy_bread, goal 'chapter.1.complete' can no longer be reached",
        "error",
    )]


def test_goal_that_can_never_be_reached_is_reported_once():
    project = make_project(facts=FACTS, beats=[{"id": "desk", "effects": ["clue.letter"]}], goals=GOAL)

    assert softlocks(check(project, deep=True)) == [
        ("A6", "goal 'chapter.1.complete' can never be reached", "error"),
    ]


def test_search_stops_at_the_state_bound_and_says_so():
    facts = {f"clue.{n}": {"type": "bool"} for n in range(8)} | {"case.state": FACTS["case.state"]}
    beats = [{"id": f"find_{n}", "effects": [f"clue.{n}"]} for n in range(8)]
    beats.append({"id": "solve", "requires": [f"clue.{n}" for n in range(8)],
                  "effects": [{"set": "case.state", "value": "solved"}]})
    project = make_project(facts=facts, beats=beats, goals=GOAL)

    assert softlocks(check(project, deep=True, max_states=20)) == [(
        "A6",
        "softlock search for goal 'chapter.1.complete' stopped after 20 states;"
        " states beyond them were not checked (raise --max-states)",
        "warning",
    )]
    assert softlocks(check(project, deep=True)) == []


def test_facts_the_goal_does_not_depend_on_are_sliced_away():
    facts = {f"stats.{n}": {"type": "bool"} for n in range(30)} | FACTS
    beats = LIGHTHOUSE + [{"id": f"stat_{n}", "effects": [f"stats.{n}"]} for n in range(30)]
    project = make_project(facts=facts, beats=beats, goals=GOAL)

    # 2**30 states without slicing; a few dozen with it.
    assert [m for _, m, _ in softlocks(check(project, deep=True, max_states=100))] == [
        "softlock: after relight_lamp, goal 'chapter.1.complete' can no longer be reached",
    ]


def test_cli_deep_check_reports_softlocks(project, run):
    project.write("factgraph.toml", """
        [facts."lamp.lit"]
        type = "bool"

        [facts."clue.lamp"]
        type = "bool"

        [goals."chapter.1.complete"]
        requires = "clue.lamp"

        [[sources.json]]
        files = "beats.json"
        kind = "interactable"
    """)
    project.write("beats.json", [
        {"id": "lamp_room", "requires": {"not": "lamp.lit"}, "effects": ["clue.lamp"]},
        {"id": "relight_lamp", "effects": ["lamp.lit"]},
    ])

    assert run("check", "--config", project.config) == (0, [])
    assert run("check", "--deep", "--config", project.config) == (1, [
        "beats.json:11: A6 softlock: after relight_lamp, goal 'chapter.1.complete' can no longer be reached",
    ])
