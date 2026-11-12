CLUES_CONFIG = """
    [facts."clue.lighthouse.letter"]
    type = "bool"
    initial = false

    [[sources.json]]
    files = "data/*.json"
    kind = "interactable"
    items = "interactables"
"""


def test_typoed_fact_is_reported_with_suggestion(project, run):
    project.write("factgraph.toml", CLUES_CONFIG)
    project.write(
        "data/pier.json",
        """\
        {
          "interactables": [
            {
              "id": "desk",
              "effects": [{"set": "clue.lighthouse.letter"}]
            },
            {
              "id": "lamp",
              "requires": {"fact": "clue.lighthouse.letter"}
            },
            {
              "id": "accuse",
              "requires": {"fact": "clue.lighthouse.leter"}
            }
          ]
        }
        """,
    )

    code, lines = run("check", "--config", project.config)

    assert code == 1
    assert lines == [
        "data/pier.json:13: A1 undefined fact 'clue.lighthouse.leter'"
        " (did you mean 'clue.lighthouse.letter'?)"
    ]


def test_clean_project_passes_silently(project, run):
    project.write("factgraph.toml", CLUES_CONFIG)
    project.write(
        "data/pier.json",
        {
            "interactables": [
                {"id": "desk", "effects": [{"set": "clue.lighthouse.letter"}]},
                {"id": "lamp", "requires": {"fact": "clue.lighthouse.letter"}},
            ]
        },
    )

    code, lines = run("check", "--config", project.config)

    assert (code, lines) == (0, [])
