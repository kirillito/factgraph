"""The bundled sample project is the tool's own test bed: each seeded bug must be found."""

from pathlib import Path

SAMPLE = str(Path(__file__).parent.parent / "examples" / "lighthouse" / "factgraph.toml")


def test_sample_typo_is_reported_with_suggestion(run):
    code, lines = run("check", "--config", SAMPLE)

    assert code == 1
    assert (
        "data/interactables.json:20: A1 undefined fact 'clue.lighthouse.leter'"
        " (did you mean 'clue.lighthouse.letter'?)"
    ) in lines


def test_sample_dialogue_bad_condition_is_reported_at_its_line(run):
    code, lines = run("check", "--config", SAMPLE)

    assert (
        "game/dialogue/harbour_master.dialogue:7: A1 undefined fact 'clue.boat.missng'"
        " (did you mean 'clue.boat.missing'?)"
    ) in lines


def test_sample_unreachable_branch_and_self_gated_deduction_are_found(run):
    code, lines = run("check", "--config", SAMPLE)

    assert "game/dialogue/harbour_master.dialogue:6: A4 unreachable beat 'dialogue/harbour_master:6'" in lines
    assert (
        "data/deductions.json:10: A5 self-gated deduction 'deduction.keeper_rowed_to_island':"
        " it needs 'clue.island.footprints', which is only reachable after its own effect on 'case.island.searched'"
    ) in lines


def test_sample_softlock_is_found_with_its_path(run):
    code, lines = run("check", "--deep", "--config", SAMPLE)

    assert (
        "data/interactables.json:44: A6 softlock: after relight_lamp,"
        " goal 'chapter.1.complete' can no longer be reached"
    ) in lines


def test_sample_coverage_lists_beats_no_test_fires(run):
    traces = str(Path(SAMPLE).parent / "traces")

    code, lines = run("check", "--coverage", traces, "--config", SAMPLE)

    assert "A7 coverage: 5 of 16 reachable beats fired by tests [info]" in lines
    assert "data/interactables.json:44: A7 beat 'relight_lamp' is never fired by a test [info]" in lines
    assert "traces/opening_smoke_test.trace:7: A7 trace names unknown beat 'keeper_dairy' [warning]" in lines
