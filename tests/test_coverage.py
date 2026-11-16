CONFIG = """
    [facts."clue.letter"]
    type = "bool"

    [facts."case.state"]
    type = "string"
    values = ["open", "solved"]
    initial = "open"

    [facts."keeper.found"]
    type = "bool"

    [goals."chapter.1.complete"]
    requires = { fact = "case.state", eq = "solved" }

    [[sources.json]]
    files = "beats.json"
    kind = "interactable"
"""

BEATS = """\
[
  {"id": "desk", "effects": ["clue.letter"]},
  {"id": "read_letter", "requires": "clue.letter"},
  {"id": "accuse", "requires": "clue.letter", "effects": [{"set": "case.state", "value": "solved"}]},
  {"id": "epilogue", "requires": "keeper.found"}
]
"""


def write(project):
    project.write("factgraph.toml", CONFIG)
    project.write("beats.json", BEATS)


def test_coverage_lists_beats_no_test_fires(project, run):
    write(project)
    project.write("traces/intro_test.trace", "# beats fired by the intro test\ndesk\nread_letter\ndesk\n")

    code, lines = run("check", "--coverage", str(project.root / "traces"), "--config", project.config)

    assert code == 1  # epilogue is unreachable (A4); coverage itself never fails the run
    assert lines == [
        "A7 coverage: 2 of 3 reachable beats fired by tests [info]",
        "beats.json:4: A7 beat 'accuse' is never fired by a test [info]",
        "beats.json:5: A4 unreachable beat 'epilogue'",
    ]


def test_traces_can_be_json_lines_in_nested_folders(project, run):
    write(project)
    project.write("traces/ci/run1.jsonl", '{"beat": "desk", "t": 0.5}\n{"beat": "accuse"}\n')
    project.write("traces/ci/run2.jsonl", '{"beat": "read_letter"}\n')

    code, lines = run("check", "--coverage", str(project.root / "traces"), "--config", project.config)

    assert lines[0] == "A7 coverage: 3 of 3 reachable beats fired by tests [info]"
    assert not any("never fired" in line for line in lines)


def test_unknown_beat_ids_in_traces_are_flagged(project, run):
    write(project)
    project.write("traces/t.trace", "desk\nred_letter\n")

    _, lines = run("check", "--coverage", str(project.root / "traces"), "--config", project.config)

    assert (
        "traces/t.trace:2: A7 trace names unknown beat 'red_letter' (did you mean 'read_letter'?) [warning]"
    ) in lines


def test_missing_trace_folder_is_a_usage_error(project, run, capsys):
    write(project)

    assert run("check", "--coverage", str(project.root / "nope"), "--config", project.config) == (2, [])
