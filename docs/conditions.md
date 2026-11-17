# Conditions and effects

factgraph models game logic as tests on single facts, combined with `all`, `any` and `not`, and as effects
that set a fact or add to it. Data files and goals use the JSON syntax below. Dialogue Manager files use
their own expressions, which are mapped through a vocabulary (see
[dialogue-manager.md](dialogue-manager.md#vocabulary)).

## Condition syntax

| Write | Means |
|---|---|
| `"clue.letter"` | the fact is truthy (shorthand for `{"fact": "clue.letter"}`) |
| `["a", "b"]` | all of them (shorthand for `{"all": [...]}`) |
| `true` or no condition | always |
| `{"all": [c1, c2]}` | every condition holds |
| `{"any": [c1, c2]}` | at least one holds |
| `{"not": c}` | the condition doesn't hold |
| `{"fact": "case.state", "eq": "solved"}` | equals a value |
| `{"fact": "case.state", "in": ["open", "reopened"]}` | equals one of the values |
| `{"fact": "clues.found", "gt": 2}` | an int greater than |
| `{"fact": "clues.found", "lt": 3}` | an int less than |

A fact test has exactly one of `eq`, `in`, `gt` or `lt`, or none for a truthy test. Unknown keys are
reported, not ignored, so `{"fact": "x", "ge": 3}` is an error rather than a silent truthy test.
In TOML, write the same structures as inline tables, e.g. `requires = { fact = "case.state", eq = "solved" }`.

## Semantics

- An unset fact is falsy and equal to nothing.
- A bare fact test is true when the value is truthy: `true`, a non-zero int or a non-empty string.
- `eq` and `in` compare type and value: `true` does not equal `1`, and `1` does not equal `"1"`.
- `gt` and `lt` are false for anything that is not an int.
- `all` of nothing is true; `any` of nothing is false.

## Effect syntax

| Write | Means |
|---|---|
| `"clue.letter"` | set it to `true` |
| `{"set": "case.state", "value": "solved"}` | set it to a value (`value` defaults to `true`) |
| `{"inc": "clues.found"}` | add 1 |
| `{"inc": "coins", "by": -2}` | add any amount, negative to subtract |
| `{"give_item": "rope"}` | a custom name mapped in `[effects]` (see [configuration.md](configuration.md#custom-effect-names)) |

Effects are a list, or a single effect.

## Keeping conditions analyzable

factgraph can only check what it can model. Conditions that compute ("clues found plus favours owed is at
least five", "the flag named after the current chapter") don't fit the model. The Dialogue Manager adapter
reports them as unmapped rather than guessing.

If your game has a condition evaluator of its own, keep its vocabulary small: fact tests, comparisons with
literals, `and`, `or` and `not`. When a rule needs computation, compute it into a fact in code
(`favours.enough = true`) and test that fact in content.

## Testing your game's evaluator

Your game decides what conditions mean at run time. factgraph decides what they mean in analysis. To keep
the two in agreement, factgraph ships a set of test cases:

```
factgraph fixtures > tests/factgraph_conditions.json
```

The file has a list of `cases`, each with a `condition` in the syntax above, a `state` (facts not listed
are unset) and the `expected` result. Load it in your game's unit tests, run each condition through your
evaluator against its state, and compare. factgraph's own evaluator passes every case. Regenerate the
file when you upgrade factgraph.
