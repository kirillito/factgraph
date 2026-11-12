# Sample project: The Missing Lighthouse Keeper

A tiny invented mystery used as factgraph's own test bed. The keeper of a lighthouse has vanished; the
player finds a letter, a cold lamp and an empty mooring, then deduces that the keeper left by boat.

Run it from the repository root:

```
factgraph check --config examples/lighthouse/factgraph.toml
```

## Seeded bugs

These are deliberate, so each check has something to find:

| Check | Where | Bug |
|---|---|---|
| A1 | `data/interactables.json` | `empty_mooring` reads `clue.lighthouse.leter`, a typo of `clue.lighthouse.letter` |
