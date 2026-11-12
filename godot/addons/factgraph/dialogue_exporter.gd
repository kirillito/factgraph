## Exports Dialogue Manager files to the factgraph JSON format. Used by export_dialogue.gd.
extends RefCounted

const FORMAT := "factgraph-dialogue-manager"
const FORMAT_VERSION := 1
const SUPPORTED_MAJOR := 4
const DM_PLUGIN_CFG := "res://addons/dialogue_manager/plugin.cfg"
const MUTATION_CODES := ["do", "do!", "set", "$>", "$>>"]


## Export every .dialogue file under the given roots. Returns the whole export document.
func export_all(roots: PackedStringArray) -> Dictionary:
	var paths: PackedStringArray = []
	for root in roots:
		_find_dialogue_files(root, paths)
	paths.sort()

	# Register every file first so that "import" lines resolve without the editor's cache.
	for path in paths:
		DMCache.add_file(path)

	var files: Array = []
	for path in paths:
		files.append(export_file(path))

	return {
		"format": FORMAT,
		"version": FORMAT_VERSION,
		"dialogue_manager": dialogue_manager_version(),
		"files": files,
	}


## Compile one file and return its export entry.
func export_file(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var raw_lines := text.split("\n")
	# DMCompilation rather than DMCompiler.compile_string: we also need each response's
	# next_id_after (where its group rejoins), which the stored line data leaves out.
	var compilation := DMCompilation.new()
	compilation.compile(text, path)
	var lines: Dictionary = compilation.data.duplicate(true)
	for id: String in compilation.lines:
		var compiled: DMCompiledLine = compilation.lines[id]
		if compiled.type == DMConstants.TYPE_RESPONSE and lines.has(id) and not lines[id].has("next_id_after"):
			lines[id]["next_id_after"] = compiled.next_id_after

	var errors: Array = []
	for error: DMError in compilation.errors:
		errors.append({
			"line": error.line_number,
			"column": error.column_number,
			"error": error.error,
			"message": DMConstants.get_error_message(error.error),
		})

	var sources := {}
	var inline := {}
	var parser := DMExpressionParser.new()
	for id: String in lines:
		var head := id.get_slice(".", 0)
		if head.is_valid_int() and int(head) < raw_lines.size():
			sources[id] = raw_lines[int(head)].strip_edges()
		var line: Dictionary = lines[id]
		if line.get("type") in [DMConstants.TYPE_DIALOGUE, DMConstants.TYPE_RESPONSE]:
			var found := _inline_expressions(str(line.get("text", "")), parser)
			if not found.is_empty():
				inline[id] = found

	return {
		"path": path,
		"cues": compilation.cues,
		"errors": errors,
		"lines": lines,
		"sources": sources,
		"inline": inline,
	}


## Inline [do ...], [set ...] and [if ...] tags in a line's text, tokenised by Dialogue Manager.
func _inline_expressions(text: String, parser: DMExpressionParser) -> Array:
	var found: Array = []
	for bbcode: Dictionary in DMResolvedLineData.find_bbcode_positions_in_string(text, true, true):
		var code: String = bbcode.code
		var kind := ""
		if code == "if":
			kind = DMConstants.TYPE_CONDITION
		elif code in MUTATION_CODES:
			kind = DMConstants.TYPE_MUTATION
		else:
			continue
		var expression: Array = parser.tokenise(bbcode.raw_args, kind, 0)
		if expression.is_empty() or expression[0].get("type") == DMConstants.TOKEN_ERROR:
			continue  # Dialogue Manager reports these as compile errors.
		found.append({"code": code, "expression": expression})
	return found


func dialogue_manager_version() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(DM_PLUGIN_CFG) != OK:
		return ""
	return str(cfg.get_value("plugin", "version", ""))


func _find_dialogue_files(dir_path: String, into: PackedStringArray) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		if sub.begins_with(".") or (dir_path == "res://" and sub == "addons"):
			continue
		_find_dialogue_files(dir_path.path_join(sub), into)
	for file in dir.get_files():
		if file.get_extension() == "dialogue":
			into.append(dir_path.path_join(file))


