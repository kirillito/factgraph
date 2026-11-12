## Exporter self-test. From a Godot project that has Dialogue Manager and this addon installed:
##   godot --headless --import
##   godot --headless --script res://addons/factgraph/tests/test_export.gd
## Exits 0 when every assertion holds; prints each failure otherwise.
extends SceneTree

const Exporter := preload("res://addons/factgraph/dialogue_exporter.gd")
const FIXTURE := "res://addons/factgraph/tests/fixture.dialogue"

var failures := 0


func _init() -> void:
	DMCache.add_file(FIXTURE)
	var entry: Dictionary = Exporter.new().export_file(FIXTURE)
	var lines: Dictionary = entry.lines

	check(entry.errors.is_empty(), "fixture compiles without errors: %s" % [entry.errors])
	check(entry.cues.get("start") == "1", "cue 'start' points at line id 1")
	check(lines["1"].type == "dialogue", "line id 1 is dialogue")
	check(lines["2"].type == "condition", "line id 2 is a condition")
	check(lines["2"].condition.expression[0].function == "has", "condition is tokenised as a has() call")
	check(lines["4"].type == "response", "line id 4 is a response")
	check(Array(lines["4"].responses) == ["4", "6"], "first response lists its group")
	check(lines["4"].next_id_after == "7", "exporter adds next_id_after to responses")
	check(lines["5"].type == "mutation", "line id 5 is a mutation")
	check(entry.sources["2"] == 'if has("clue.letter"):', "raw source text is kept")
	check(entry.inline["1"][0].code == "do", "inline [do] is exported")
	check(entry.inline["1"][0].expression[0].function == "set_fact", "inline [do] is tokenised")

	print("factgraph exporter: %s" % ("ok" if failures == 0 else "%d failure(s)" % failures))
	quit(1 if failures else 0)


func check(ok: bool, what: String) -> void:
	if not ok:
		failures += 1
		printerr("FAIL: %s" % what)
