## factgraph exporter for Dialogue Manager.
##
## Compiles every .dialogue file with Dialogue Manager's own compiler and writes one JSON file that
## the factgraph analyzer reads. Run it headless from your Godot project folder:
##
##   godot --headless --import                       # once, so class names are registered
##   godot --headless --script res://addons/factgraph/export_dialogue.gd -- --out build/dialogue.json
##
## Options (after "--"):
##   --out <path>     output file (absolute, res:// or relative to the working directory)
##                    default: res://factgraph_dialogue.json
##   --root <dir>     folder to scan for .dialogue files; repeatable; default: res://
##
## Tested with Dialogue Manager 4.x. The output keeps Dialogue Manager's compiled line data as-is
## and adds the raw source text and inline expressions of each line, plus each response's
## next_id_after (where its response group rejoins the flow).
extends SceneTree

const Exporter := preload("res://addons/factgraph/dialogue_exporter.gd")


func _init() -> void:
	var code := run(OS.get_cmdline_user_args())
	quit(code)


func run(args: PackedStringArray) -> int:
	var out_path := "res://factgraph_dialogue.json"
	var roots: PackedStringArray = []
	var i := 0
	while i < args.size():
		match args[i]:
			"--out":
				i += 1
				out_path = args[i]
			"--root":
				i += 1
				roots.append(args[i])
			_:
				printerr("factgraph: unknown argument %s" % args[i])
				return 2
		i += 1
	if roots.is_empty():
		roots.append("res://")

	var exporter = Exporter.new()
	var dm_version: String = exporter.dialogue_manager_version()
	if dm_version == "":
		printerr("factgraph: Dialogue Manager not found at %s" % Exporter.DM_PLUGIN_CFG)
		return 1
	if not dm_version.begins_with("%d." % Exporter.SUPPORTED_MAJOR):
		push_warning("factgraph: Dialogue Manager %s is untested (supported: %d.x)" % [dm_version, Exporter.SUPPORTED_MAJOR])

	return _write(out_path, JSON.stringify(exporter.export_all(roots), "  "))


func _write(out_path: String, content: String) -> int:
	var target := ProjectSettings.globalize_path(out_path) if out_path.begins_with("res://") else out_path
	DirAccess.make_dir_recursive_absolute(target.get_base_dir())
	var file := FileAccess.open(target, FileAccess.WRITE)
	if file == null:
		printerr("factgraph: cannot write %s" % target)
		return 1
	file.store_string(content)
	file.close()
	print("factgraph: exported dialogue to %s" % target)
	return 0
