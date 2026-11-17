## Editor side of the factgraph addon: adds "Export dialogue for factgraph" to Project > Tools.
## The output path is the project setting factgraph/export_path. CI should use the headless
## export_dialogue.gd script instead; both write the same file.
@tool
extends EditorPlugin

const Exporter := preload("res://addons/factgraph/dialogue_exporter.gd")
const SETTING := "factgraph/export_path"
const DEFAULT_PATH := "res://factgraph_dialogue.json"
const MENU := "Export dialogue for factgraph"


func _enter_tree() -> void:
	if not ProjectSettings.has_setting(SETTING):
		ProjectSettings.set_setting(SETTING, DEFAULT_PATH)
	ProjectSettings.set_initial_value(SETTING, DEFAULT_PATH)
	ProjectSettings.add_property_info({
		"name": SETTING,
		"type": TYPE_STRING,
		"hint": PROPERTY_HINT_SAVE_FILE,
		"hint_string": "*.json",
	})
	add_tool_menu_item(MENU, _export)


func _exit_tree() -> void:
	remove_tool_menu_item(MENU)


func _export() -> void:
	var exporter = Exporter.new()
	var problem: String = exporter.check_dialogue_manager()
	if problem != "":
		push_error("factgraph: %s" % problem)
		return
	var path: String = ProjectSettings.get_setting(SETTING, DEFAULT_PATH)
	var target: String = exporter.save(path, PackedStringArray(["res://"]))
	if target != "":
		print("factgraph: exported dialogue to %s" % target)
		EditorInterface.get_resource_filesystem().scan()
