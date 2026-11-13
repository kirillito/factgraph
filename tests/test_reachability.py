from builders import make_project, summary

from factgraph.checks import check

FACTS = {
    "clue.letter": {"type": "bool"},
    "clue.boat": {"type": "bool"},
    "case.state": {"type": "string", "values": ["open", "solved"], "initial": "open"},
    "clues.found": {"type": "int"},
}


def unreachable(findings):
    return [msg for check_id, msg in summary(findings) if check_id in ("A4", "A5")]


def test_beat_gated_on_a_value_nothing_sets_is_unreachable():
    project = make_project(
        facts=FACTS,
        beats=[
            {"id": "desk", "effects": ["clue.letter"]},
            {"id": "read_letter", "requires": "clue.letter", "effects": ["clue.boat"]},
            {"id": "closing", "requires": {"fact": "case.state", "eq": "solved"}},
            {"id": "after_closing", "requires": ["clue.boat", {"fact": "case.state", "eq": "solved"}]},
        ],
        goals={"g": ["clue.boat"]},
    )

    assert unreachable(check(project)) == [
        "unreachable beat 'after_closing'",
        "unreachable beat 'closing'",
    ]


def test_negation_and_counters_stay_sound():
    project = make_project(
        facts=FACTS,
        beats=[
            {"id": "find", "requires": {"fact": "clues.found", "lt": 3}, "effects": [{"inc": "clues.found"}]},
            {"id": "enough", "requires": {"fact": "clues.found", "gt": 2}, "effects": ["clue.boat"]},
            {"id": "too_many", "requires": {"fact": "clues.found", "gt": 3}},
            {"id": "before_boat", "requires": {"not": "clue.boat"}},
            {"id": "never_unset", "requires": {"not": {"fact": "case.state", "in": ["open", "solved"]}}},
            {"id": "undefined_is_unknown", "requires": "clue.typo"},
        ],
    )

    assert unreachable(check(project)) == [
        "unreachable beat 'never_unset'",
        "unreachable beat 'too_many'",
    ]


def test_deduction_whose_clue_needs_its_own_solution_is_self_gated():
    project = make_project(
        facts={**FACTS, "clue.island": {"type": "bool"}},
        beats=[
            {"id": "island_shore", "requires": {"fact": "case.state", "eq": "solved"}, "effects": ["clue.island"]},
            {"id": "deduction.island", "kind": "deduction", "requires": ["clue.island"],
             "effects": [{"set": "case.state", "value": "solved"}]},
        ],
    )

    assert unreachable(check(project)) == [
        "unreachable beat 'island_shore'",
        "self-gated deduction 'deduction.island': it needs 'clue.island',"
        " which is only reachable after its own effect on 'case.state'",
    ]
