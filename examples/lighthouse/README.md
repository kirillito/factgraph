# Sample project: The Missing Lighthouse Keeper

A tiny invented mystery used as factgraph's own test bed. The keeper of a lighthouse has vanished; the
player finds a letter, a cold lamp and an empty mooring, then deduces that the keeper left by boat.

Run it from the repository root:

```
factgraph check --config examples/lighthouse/factgraph.toml
```

The chapter's flow graph is in [chapter1.md](chapter1.md).

## Seeded bugs

These are deliberate, so each check has something to find:

| Check | Where | Bug |
|---|---|---|
| A1 | `data/interactables.json` | `empty_mooring` reads `clue.lighthouse.leter`, a typo of `clue.lighthouse.letter` |
| A1 | `game/dialogue/harbour_master.dialogue` | the "Ask about the boat" choice reads `clue.boat.missng`, a typo of `clue.boat.missing` |
| A4 | `game/dialogue/harbour_master.dialogue` | the branch on `clue.keeper.found` can never open: the fact is declared but nothing sets it |
| A5 | `data/deductions.json` | `keeper_rowed_to_island` needs footprints that are only found once the island is searched, which needs the deduction itself |

## Dialogue

`game/` is a minimal Godot project holding the sample's Dialogue Manager files. `build/dialogue.json` is
the exporter's output for them, kept in the repository so the sample runs without Godot. To regenerate it,
install Dialogue Manager 4.x and the factgraph addon into `game/addons/`, then from `game/`:

```
godot --headless --import
godot --headless --script res://addons/factgraph/export_dialogue.gd -- --out ../build/dialogue.json
```
