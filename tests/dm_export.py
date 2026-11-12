"""Build exporter JSON (the factgraph Dialogue Manager export format) for tests.

Lines follow Dialogue Manager 4.x ``DMCompiledLine.to_data()``: IDs are 0-based source line indexes,
expressions are DM token lists. Helpers below spell the tokens out so fixtures stay readable.
"""


def string(v):
    return {"type": "string", "value": v}


def number(v):
    return {"type": "number", "value": v}


def boolean(v):
    return {"type": "bool", "value": v}


def var(name):
    return {"type": "variable", "value": name}


def call(name, *args):
    # DM keeps the closing parens token at the end of the last argument.
    arg_lists = [[a] for a in args] or [[]]
    arg_lists[-1] = arg_lists[-1] + [{"type": "parens_close"}]
    return {"type": "function", "function": name, "value": arg_lists}


def op(kind, value):
    return {"type": kind, "value": value}


NOT = {"type": "not"}
AND = op("and_or", "and")
OR = op("and_or", "or")


def cmp(value):
    return op("comparison", value)


def assign(value):
    return op("assignment", value)


def export(*files, version="4.2.0"):
    return {"format": "factgraph-dialogue-manager", "version": 1, "dialogue_manager": version, "files": list(files)}


def dialogue_file(path, lines, cues=None, errors=(), inline=None, sources=None):
    return {
        "path": path,
        "cues": cues or {},
        "errors": list(errors),
        "lines": lines,
        "inline": inline or {},
        "sources": sources or {},
    }
