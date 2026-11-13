"""The shipped fixture set that host games run against their own evaluators must hold for ours."""

import json
from importlib import resources

import pytest

from factgraph.evaluate import evaluate
from factgraph.syntax import parse_condition

CASES = json.loads(resources.files("factgraph").joinpath("fixtures/conditions.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_condition_fixture(case):
    assert evaluate(parse_condition(case["condition"], "fixture"), case["state"]) is case["expected"]
