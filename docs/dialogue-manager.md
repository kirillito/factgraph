# Dialogue Manager

factgraph doesn't parse `.dialogue` syntax itself. A small Godot addon compiles each file with Dialogue
Manager's own compiler and writes the result to one JSON file, and factgraph reads that file. The
analysis then follows Dialogue Manager's real behaviour and needs no engine at check time.

The exporter is tested with Dialogue Manager 4.x on Godot 4. It warns on other major versions.

## Install the addon

1. Install Dialogue Manager 4.x in your project as usual (`addons/dialogue_manager`).
2. Copy [godot/addons/factgraph](../godot/addons/factgraph) from this repository to `addons/factgraph` in
   your project.
3. Optionally, enable **factgraph** under Project > Project Settings > Plugins. This adds
   **Project > Tools > Export dialogue for factgraph**, which writes to the project setting
   `factgraph/export_path` (default `res://factgraph_dialogue.json`). The headless export below works
   without enabling it.

## Export

From your Godot project folder:

```
godot --headless --import
godot --headless --script res://addons/factgraph/export_dialogue.gd -- --out build/dialogue.json
```

The first command registers class names and only needs to run once on a fresh checkout or CI machine.

- `--out <path>`: the output file, absolute, `res://` or relative to the working directory (Godot's
  `--path` changes the working directory to the project folder). The default is `res://factgraph_dialogue.json`.
- `--root <dir>`: the folder to scan for `.dialogue` files. Repeat it for several folders. The default is
  `res://`, which skips `res://addons` and hidden folders.

The exporter exits non-zero if Dialogue Manager is missing or the file can't be written. Compile errors in
dialogue files are not exporter failures: they are exported, and `factgraph check` reports them at their
lines.

To check that the exporter works with your Dialogue Manager version, run its self-test:

```
godot --headless --script res://addons/factgraph/tests/test_export.gd
```

It prints `factgraph exporter: ok` and exits 0 when every assertion holds.

## Configure factgraph

```toml
[[sources.dialogue_manager]]
export = "game/build/dialogue.json"   # the exporter's output, relative to factgraph.toml
res_root = "game"                     # the Godot project folder, relative to factgraph.toml; makes reports point at real files
static_tags = { chapter = "1" }       # tags added to every dialogue beat
```

## Vocabulary

Dialogue conditions and mutations are code, so you tell factgraph which functions and variables read and
write facts:

```toml
[vocabulary.read]
has = "fact"                 # has("clue.letter"): the first string argument names a fact

[vocabulary.write]
set_fact = "set"             # set_fact("clue.letter") sets true; set_fact("case.state", "solved") sets a value
add = "inc"                  # add("clues.found") adds 1; add("coins", -2) adds an amount
give_item = { set = "item.{}" }   # give_item("rope") sets item.rope = true

[vocabulary]
ignore = ["play_sound", "shake_camera"]   # calls that don't touch facts
variables = false            # true: bare variables are fact IDs (case.state == "solved", clues.found += 1)
```

A source table can extend the vocabulary with its own `vocabulary = { ... }`.

### What maps

In conditions (`if`, `elif`, `while`, response `[if ...]`, inline `[if ...]`):

- calls in the read vocabulary, e.g. `has("clue.letter")`, which test whether the fact is truthy;
- comparisons between a fact and a literal: `==`, `!=`, `>`, `<`, `>=`, `<=`, and `in [ ... ]` with an
  array of literals. A fact is a read call or, with `variables = true`, a variable or dotted variable.
  `count("clues.found") > 2` and `case.state == "solved"` both map;
- `and`, `or`, `not` and parentheses.

In mutations (`do`, `set`, `$>`, inline `[do ...]`):

- calls in the write vocabulary with literal arguments;
- with `variables = true`, assignments `fact = literal`, `fact += n` and `fact -= n`;
- calls in `ignore`, which are dropped.

Anything else is reported at its line, for example:

```
game/dialogue/keeper.dialogue:12: adapter unmapped condition 'if favours() + clues() > 4': function 'favours' is not in the read vocabulary
```

factgraph doesn't guess what unmapped code does. The line still becomes a beat, and an unmapped condition
is treated as possibly true and possibly false, so it hides no content from the other checks.
To keep dialogue analyzable, keep the vocabulary small; see
[conditions.md](conditions.md#keeping-conditions-analyzable).

## Beats

Each line of the compiled dialogue that factgraph can reach from a cue becomes a beat:

| Dialogue | Beat kind |
|---|---|
| a line of dialogue | `dialogue_line` |
| a response (choice) | `choice` |
| a mutation line (`do ...`) | `dialogue_effect` |
| an inline `[if ...]` inside a line | `dialogue_fragment` |

A beat's condition is everything that must hold on the way to it from a cue: the `if`/`elif`/`else`
branches around it and the condition on the response that leads to it. After an `if` block or a response
group ends, the lines that follow are no longer gated by it. Every cue (`~ title`) counts as an entry
point, since the game may start any of them. Beats are tagged with `file`, `cue` and `character`.

### Beat IDs

A dialogue beat's ID is the line's static ID if it has one (`[ID:...]`). Otherwise it is the file's path
without `res://` and `.dialogue`, then `:` and the 1-based line number, e.g. `dialogue/harbour_master:7`.
An inline `[if ...]` adds `#if1`, `#if2` and so on.

To log coverage traces from the game, build the same ID when a line is shown. For lines without a static
ID, Dialogue Manager's line ID is the 0-based line index:

```gdscript
func factgraph_beat_id(resource: DialogueResource, line: DialogueLine) -> String:
	var base := resource.resource_path.trim_prefix("res://").trim_suffix(".dialogue")
	return "%s:%d" % [base, int(line.id) + 1]
```

## Continuous integration

Godot runs headless on CI runners. A typical content check:

```
godot --headless --path game --import
godot --headless --path game --script res://addons/factgraph/export_dialogue.gd -- --out res://build/dialogue.json
factgraph check
```

With `export = "game/build/dialogue.json"` in `factgraph.toml`, as above.

The sample project ([examples/lighthouse](../examples/lighthouse)) keeps its export in the repository, so its
check runs without Godot. That works too, if you re-export whenever dialogue changes.
