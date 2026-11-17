# factgraph

A story-flow linter for state-driven narrative games.

Narrative games gate content on facts: `clue.letter` is set, `case.state` is `"solved"`, `clues.found > 2`.
Those facts are written and read across dialogue files, data files and code. A typo or a deleted scene
breaks the flow without breaking any build: the branch just never opens. Dialogue tools check their own
syntax, not the fact graph across files, so these bugs usually reach players.

factgraph reads your content, builds the graph of facts and the beats that read and write them, and reports:

```
data/interactables.json:20: A1 undefined fact 'clue.lighthouse.leter' (did you mean 'clue.lighthouse.letter'?)
data/interactables.json:37: A4 unreachable beat 'island_footprints'
data/deductions.json:10: A5 self-gated deduction 'deduction.keeper_rowed_to_island': it needs 'clue.island.footprints', which is only reachable after its own effect on 'case.island.searched'
data/interactables.json:44: A6 softlock: after relight_lamp, goal 'chapter.1.complete' can no longer be reached
game/dialogue/harbour_master.dialogue:7: A1 undefined fact 'clue.boat.missng' (did you mean 'clue.boat.missing'?)
```

It works with plain JSON game data through a small mapping config, and with
[Dialogue Manager](https://github.com/nathanhoad/godot_dialogue_manager) for Godot through a bundled exporter
addon. The analyzer is pure Python with no dependencies and doesn't need the engine to run.

## Install

```
pip install factgraph
```

Python 3.11 or newer. For Dialogue Manager projects, also copy [godot/addons/factgraph](godot/addons/factgraph)
into your Godot project's `addons/` folder (see [docs/dialogue-manager.md](docs/dialogue-manager.md)).

## Quick start

Try it on the bundled sample, a tiny invented mystery with one seeded bug per check:

```
git clone https://github.com/kirillito/factgraph
cd factgraph
factgraph check --config examples/lighthouse/factgraph.toml
```

For your own game, write a `factgraph.toml` next to your content:

```toml
[facts."clue.letter"]
type = "bool"

[facts."case.state"]
type = "string"
values = ["open", "solved"]
initial = "open"

[goals."chapter.1.complete"]
requires = { fact = "case.state", eq = "solved" }

[[sources.json]]
files = "data/interactables/*.json"
kind = "interactable"
requires = "requires"
effects = "effects"
```

Then run `factgraph check`. [docs/configuration.md](docs/configuration.md) covers every option, and
[docs/conditions.md](docs/conditions.md) describes the condition and effect syntax.

## Concepts

- **Fact:** a named piece of game state (`bool`, `int` or `string`, optionally with a fixed set of values).
- **Beat:** a unit of content that can happen: a dialogue line or choice, an interactable, entering a
  location, solving a deduction. A beat has a condition that gates it and effects that write facts.
- **Goal:** a condition that marks progress, such as `chapter.1.complete`. The softlock search uses goals.

## Checks

| ID | Finds | Severity |
|---|---|---|
| A1 | A fact that is read but never written or declared (with "did you mean") | error |
| A2 | A fact that is written but never read | warning |
| A3 | Type and value misuse: `eq "open"` on a bool, a value outside the declared set | error |
| A4 | A beat no play-through can reach | error |
| A5 | A deduction or puzzle whose requirements are only reachable after its own effects | error |
| A6 | A softlock: a reachable state from which a goal can no longer be reached, with the beats that lead there | error, opt-in (`--deep`) |
| A7 | Coverage: reachable beats the game's automated tests never fire | report, opt-in (`--coverage`) |

A4 never reports a reachable beat as unreachable: it over-approximates every play-through, so an
"unreachable" result is certain. A6 is an exact search within a bound. It slices the graph down to the
facts each goal depends on, stops at `--max-states` per goal, and says so when it stops early.

## Commands

```
factgraph check [--deep] [--max-states N] [--coverage TRACE_DIR]   # exit 1 on errors, 2 on usage errors
factgraph why <beat-id>       # one path of beats that makes it reachable, or what blocks it
factgraph who <fact-id>       # every declaration, read and write of a fact, with file:line
factgraph graph [--chapter N] [--focus NAME] [--depth N] [--group-by TAG] [--format mermaid|dot]
factgraph fixtures            # condition-semantics test cases for your game's own evaluator
```

Every command takes `--config` (default `factgraph.toml`). Reports are one line per finding,
`file:line: CHECK message`, so editors and CI annotate them directly.

`why` and `who` answer the usual questions ("why can't I reach this scene?", "who sets this flag?")
without reading the content files, which makes them handy for coding agents as well as people.

`graph` draws beats, facts and goals as a Mermaid or Graphviz diagram. Unreachable beats are highlighted.
See [examples/lighthouse/chapter1.md](examples/lighthouse/chapter1.md).

## Integrating with a game

The sample project in [examples/lighthouse](examples/lighthouse) is the reference setup.

1. **Declare** facts, goals and, for dialogue, the condition vocabulary in `factgraph.toml`. Map your data
   files to beats with `[[sources.json]]` tables. Facts can live in a separate declaration file
   (`[project] facts_file`), which can also hold an alias table for renamed facts.
2. **Check on every change.** Run `factgraph check` in CI or a pre-commit hook. It is fast, and exits 1 on errors.
   For Dialogue Manager, run the headless exporter first (see [docs/dialogue-manager.md](docs/dialogue-manager.md)).
3. **Search for softlocks less often.** Run `factgraph check --deep` nightly or before milestones, since the
   search costs more.
4. **Measure coverage.** Have your automated tests write the ID of each beat they fire to a trace folder,
   then run `factgraph check --coverage <folder>`. The format is described in
   [docs/configuration.md](docs/configuration.md#coverage-traces).
5. **Keep evaluators in sync.** `factgraph fixtures` prints condition test cases with expected results.
   Run them through your game's own condition evaluator in its unit tests, so the game and factgraph agree
   on what a condition means. See [docs/conditions.md](docs/conditions.md#testing-your-games-evaluator).

## Limits

- Conditions are tests on single facts combined with `all`, `any` and `not`. Arithmetic and string
  building in conditions are reported as unmapped rather than guessed; keep a small condition vocabulary
  (see [docs/conditions.md](docs/conditions.md)).
- Ints are tracked only as precisely as the constants your conditions compare them with.
- The Dialogue Manager exporter is tested with Dialogue Manager 4.x and warns on other major versions.

## License

MIT. See [LICENSE](LICENSE).
