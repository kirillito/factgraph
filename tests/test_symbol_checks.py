from builders import make_project, summary

from factgraph.checks import check


def test_write_only_fact_is_a_warning():
    project = make_project(
        beats=[{"id": "desk", "effects": ["clue.lighthouse.letter", "stats.desk_opened"]}],
        goals={"case": "clue.lighthouse.letter"},
    )

    findings = check(project)

    assert summary(findings) == [("A2", "write-only fact 'stats.desk_opened'")]
    assert findings[0].severity == "warning"


def test_write_only_allow_list_takes_globs():
    project = make_project(
        beats=[{"id": "desk", "effects": ["stats.desk_opened", "achievement.reader"]}],
        write_only_allow=["stats.*", "achievement.reader"],
    )

    assert check(project) == []


STATE_FACTS = {
    "door.open": {"type": "bool"},
    "case.keeper.state": {"type": "string", "values": ["open", "solved", "failed"], "initial": "open"},
    "clues.found": {"type": "int"},
}


def test_condition_type_and_value_misuse():
    project = make_project(
        facts=STATE_FACTS,
        beats=[
            {"id": "a", "requires": {"fact": "door.open", "eq": "open"}},
            {"id": "b", "requires": {"fact": "case.keeper.state", "eq": "closed"}},
            {"id": "c", "requires": {"fact": "case.keeper.state", "in": ["solved", "won"]}},
            {"id": "d", "requires": {"fact": "case.keeper.state", "gt": 1}},
            {"id": "e", "requires": {"fact": "clues.found", "gt": 2}},
            {"id": "f", "effects": ["door.open", {"set": "case.keeper.state", "value": "solved"},
                                    {"inc": "clues.found"}]},
        ],
    )

    assert summary(check(project)) == [
        ("A3", "'case.keeper.state' compared with 'gt' but is string"),
        ("A3", "'case.keeper.state' compared with value 'closed' outside its declared values"),
        ("A3", "'case.keeper.state' compared with value 'won' outside its declared values"),
        ("A3", "'door.open' compared with string 'open' but is bool"),
    ]


def test_effect_type_and_value_misuse():
    project = make_project(
        facts=STATE_FACTS,
        beats=[
            {"id": "a", "effects": [{"set": "door.open", "value": "yes"},
                                    {"set": "case.keeper.state", "value": "closed"},
                                    {"inc": "case.keeper.state"},
                                    {"set": "clues.found", "value": 3}]},
            {"id": "b", "requires": ["door.open", "case.keeper.state", "clues.found"]},
        ],
    )

    assert summary(check(project)) == [
        ("A3", "'case.keeper.state' incremented but is string"),
        ("A3", "'case.keeper.state' set to value 'closed' outside its declared values"),
        ("A3", "'door.open' set to string 'yes' but is bool"),
    ]
