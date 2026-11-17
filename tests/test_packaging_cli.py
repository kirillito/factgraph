import json

from factgraph import __version__


def test_version(run, capsys):
    try:
        run("--version")
    except SystemExit as exit:
        assert exit.code == 0
    assert capsys.readouterr().out.strip() == f"factgraph {__version__}"


def test_fixtures_command_prints_the_condition_fixtures(run):
    code, lines = run("fixtures")

    assert code == 0
    data = json.loads("\n".join(lines))
    assert data["cases"] and {"name", "condition", "state", "expected"} <= set(data["cases"][0])
