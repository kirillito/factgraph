"""Parse the core JSON syntax for conditions and effects into the model.

Conditions:
  "fact.id"                          shorthand for {"fact": "fact.id"} (truthy)
  [c1, c2]                           shorthand for {"all": [c1, c2]}
  true                               always true
  {"all": [...]}, {"any": [...]}, {"not": c}
  {"fact": "id"} plus one of "eq", "gt", "lt", "in"

Effects:
  "fact.id"                          shorthand for {"set": "fact.id"}
  {"set": "id", "value": v}          value defaults to true
  {"inc": "id", "by": n}             by defaults to 1
  {<custom>: arg}                    via an effect map, e.g. give_item -> set item.{arg}
"""

from __future__ import annotations

from .jsonloc import line_of
from .model import TRUE, All, Any_, Condition, Effect, FactTest, Not, Source

OPS = ("eq", "gt", "lt", "in")


class SyntaxProblem(ValueError):
    def __init__(self, message: str, source: Source):
        super().__init__(message)
        self.source = source


def _src(file: str, node, fallback: int) -> Source:
    return Source(file, line_of(node, fallback))


def parse_condition(node, file: str, line: int = 0) -> Condition:
    here = _src(file, node, line)
    if node is None or node is True:
        return TRUE
    if isinstance(node, str):
        return FactTest(str(node), source=here)
    if isinstance(node, list):
        return All(tuple(parse_condition(item, file, here.line) for item in node))
    if isinstance(node, dict):
        if len(node) != 1 and set(node) & {"all", "any", "not"}:
            raise SyntaxProblem(f"unrecognized condition {_show(node)}", here)
        if "all" in node or "any" in node:
            key = "all" if "all" in node else "any"
            items = node[key]
            if not isinstance(items, list):
                raise SyntaxProblem(f"'{key}' needs a list of conditions", here)
            parsed = tuple(parse_condition(item, file, here.line) for item in items)
            return All(parsed) if key == "all" else Any_(parsed)
        if "not" in node:
            return Not(parse_condition(node["not"], file, here.line))
        if "fact" in node:
            fact = node["fact"]
            if not isinstance(fact, str):
                raise SyntaxProblem("'fact' needs a fact ID string", here)
            if set(node) - {"fact", *OPS}:
                raise SyntaxProblem(f"unrecognized condition {_show(node)}", here)
            ops = [op for op in OPS if op in node]
            if len(ops) > 1:
                raise SyntaxProblem(f"one comparison per fact test, got {', '.join(ops)}", here)
            if not ops:
                return FactTest(str(fact), source=here)
            op = ops[0]
            value = node[op]
            if op == "in":
                if not isinstance(value, list):
                    raise SyntaxProblem("'in' needs a list of values", here)
                value = tuple(_plain(v) for v in value)
            else:
                value = _plain(value)
            return FactTest(str(fact), op, value, source=here)
    raise SyntaxProblem(f"unrecognized condition {_show(node)}", here)


def parse_effects(node, file: str, line: int = 0, effect_map: dict | None = None) -> list[Effect]:
    if node is None:
        return []
    items = node if isinstance(node, list) else [node]
    effects: list[Effect] = []
    for item in items:
        effects.extend(parse_effect(item, file, line_of(node, line), effect_map or {}))
    return effects


def parse_effect(node, file: str, line: int, effect_map: dict) -> list[Effect]:
    here = _src(file, node, line)
    if isinstance(node, str):
        return [Effect("set", str(node), True, here)]
    if isinstance(node, dict):
        if "set" in node:
            return [Effect("set", str(node["set"]), _plain(node.get("value", True)), here)]
        if "inc" in node:
            return [Effect("inc", str(node["inc"]), _plain(node.get("by", 1)), here)]
        for name, template in effect_map.items():
            if name in node:
                return [effect_from_template(template, node[name], here)]
    raise SyntaxProblem(f"unrecognized effect {_show(node)}", here)


def effect_from_template(template: dict, arg, here: Source) -> Effect:
    """Effect-map entries look like {set = "item.{}", value = true} or {inc = "x.{}", by = 1}."""
    if "set" in template:
        return Effect("set", template["set"].replace("{}", str(arg)), template.get("value", True), here)
    if "inc" in template:
        return Effect("inc", template["inc"].replace("{}", str(arg)), template.get("by", 1), here)
    raise SyntaxProblem(f"effect map entry needs 'set' or 'inc': {template!r}", here)


def _plain(value):
    if isinstance(value, str):
        return str(value)
    return value


def _show(node) -> str:
    text = repr(node if not isinstance(node, str) else str(node))
    return text if len(text) < 60 else text[:57] + "..."
