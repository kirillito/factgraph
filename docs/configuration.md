# Configuration

factgraph reads one TOML file, `factgraph.toml` by default (`--config` picks another). Paths in it are
relative to the file's folder, and reports name files relative to it too.

[examples/lighthouse/factgraph.toml](../examples/lighthouse/factgraph.toml) uses every section below.

## Facts

Declare each fact the game reads, either inline:

```toml
[facts."clue.letter"]
type = "bool"                 # bool (default), int or string

[facts."case.state"]
type = "string"
values = ["open", "solved"]   # optional: the only values it may hold (checked by A3)
initial = "open"              # default: false, 0 or ""
```

or in a JSON declaration file, which can also hold aliases:

```toml
[project]
facts_file = "facts.json"
```

```json
{
  "facts": {
    "clue.letter": {"type": "bool"},
    "case.state":  {"type": "string", "values": ["open", "solved"], "initial": "open"}
  },
  "aliases": {
    "clue.old_letter": "clue.letter"
  }
}
```

Aliases map an old fact ID to its current one. They suit games that can't rename facts once saves exist:
content may use either name and factgraph treats them as one fact. A `[aliases]` table in the TOML works
the same way.

A fact that something writes doesn't have to be declared, but declaring it gives A3 a type to check
against. A fact that is read but never declared or written is reported by A1.

## Goals

```toml
[goals."chapter.1.complete"]
requires = { fact = "case.state", eq = "solved" }   # any condition, see conditions.md
tags = { chapter = "1" }                            # optional; `graph --chapter` shows goals of that chapter
```

Goals mark progress. The softlock search (`check --deep`) looks for states from which a goal can no
longer be reached. Goals without a `chapter` tag appear in every chapter's graph.

## Check options

```toml
[check]
write_only_allow = ["stats.*", "achievement.*"]   # globs: facts written for analytics etc., not read by content (A2)
self_gated_kinds = ["deduction", "puzzle"]        # beat kinds checked for self-gating (A5); this is the default
```

## Sources

Each `[[sources.<adapter>]]` table loads beats from one kind of content. Two adapters ship with factgraph:
`json` for game data files, and `dialogue_manager` for Godot Dialogue Manager files (see
[dialogue-manager.md](dialogue-manager.md)).

### JSON data files

```toml
[[sources.json]]
files = "data/interactables/*.json"   # glob or list of globs; ** recurses
kind = "interactable"                 # beat kind for every record...
# kind_field = "type"                 # ...or the record field that holds it
items = "interactables"               # dotted path to the record list; omit if the file is the list (or one record)
# keyed = true                        # items is an object of records keyed by ID: {"desk": {...}, "lamp": {...}}
# optional = true                     # a file without items has no records (default: reported)
id = "id"                             # record field holding the ID (default "id"); keyed records use the key
id_prefix = "clue."                   # prefix added to every beat ID
requires = "requires"                 # record field(s) holding the condition (default "requires")
effects = "effects"                   # record field(s) holding the effects (default "effects")
# once = "once"                       # record field holding a fact the beat needs unset, and sets: it plays once
tags = { chapter = "chapter", location = "room" }   # beat tag = record field
static_tags = { chapter = "1" }       # tags added to every beat from these files
```

`{file}` in `id_prefix` and `static_tags` stands for the file's name without its extension, for records
whose IDs are unique only within their file (`id_prefix = "{file}/"`).

Every record field name above may be a dotted path into nested objects, e.g. `once = "on_enter.once"` or
`effects = "on_enter.then"`.

Records are plain JSON objects. Their conditions and effects use the syntax in
[conditions.md](conditions.md). When `requires` lists several fields, all of their conditions must hold.
For example, a deduction that needs every listed clue and the case still open:

```toml
[[sources.json]]
files = "data/deductions.json"
kind = "deduction"
id_prefix = "deduction."
requires = ["clues", "requires"]
effects = "on_solve"
```

```json
[
  {
    "id": "keeper_left_by_boat",
    "clues": ["clue.boat.missing", "clue.lamp.cold"],
    "requires": {"fact": "case.keeper.state", "eq": "open"},
    "on_solve": [{"set": "case.keeper.state", "value": "solved"}]
  }
]
```

Each beat is reported at the line where its record starts. Each condition or effect is reported at its
own line.

Two tags have meaning to factgraph:

- `chapter` is used by `graph --chapter`.
- `location` is the default grouping for `graph` (`--group-by` picks another tag).

Other tags are kept for your own use.

### Custom effect names

Data files often say `{"give_item": "rope"}` rather than `{"set": "item.rope"}`. Map such names once:

```toml
[effects]
give_item = { set = "item.{}" }          # {"give_item": "rope"} sets item.rope = true
add_clue_points = { inc = "points.{}", by = 1 }
```

Effects that touch no facts (a sound, a camera shake) are dropped by mapping them to `"ignore"`:

```toml
[effects]
play_sound = "ignore"
```

A source table can add its own with `effects_map = { ... }`.

## Opaque conditions

```toml
[conditions]
opaque = ["skill"]   # condition keys that test something other than facts
```

A condition object with one of these keys (`{"skill": "strength", "gte": 3}`) is treated as possibly true
and possibly false. See [conditions.md](conditions.md#keeping-conditions-analyzable).

## Coverage traces

`factgraph check --coverage <folder>` reads every file under the folder, at any depth:

- `*.jsonl`: one JSON object per line with a `"beat"` key, e.g. `{"beat": "keeper_desk", "test": "intro"}`.
  Other keys are ignored.
- any other file: one beat ID per line. Blank lines and lines starting with `#` are skipped.

Beat IDs are the ones factgraph reports: the JSON record ID with its `id_prefix`, and for dialogue the ID
described in [dialogue-manager.md](dialogue-manager.md#beat-ids).

The report gives a summary line, then each reachable beat no trace mentions. Beats A4 already reports as
unreachable are left out. A trace ID that matches no beat is a warning: it usually means an ID changed in
content but not in the game. Coverage lines never change the exit code.
