"""The bundled sample project is the tool's own test bed: each seeded bug must be found."""

from pathlib import Path

SAMPLE = str(Path(__file__).parent.parent / "examples" / "lighthouse" / "factgraph.toml")


def test_sample_typo_is_reported_with_suggestion(run):
    code, lines = run("check", "--config", SAMPLE)

    assert code == 1
    assert (
        "data/interactables.json:19: A1 undefined fact 'clue.lighthouse.leter'"
        " (did you mean 'clue.lighthouse.letter'?)"
    ) in lines


def test_sample_dialogue_bad_condition_is_reported_at_its_line(run):
    code, lines = run("check", "--config", SAMPLE)

    assert (
        "game/dialogue/harbour_master.dialogue:5: A1 undefined fact 'clue.boat.missng'"
        " (did you mean 'clue.boat.missing'?)"
    ) in lines
