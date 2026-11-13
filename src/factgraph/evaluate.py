"""Condition semantics, concrete and abstract.

``evaluate(cond, state)`` is the reference evaluator over one concrete state (missing facts are
unset: falsy, equal to nothing). Host games run the shipped fixtures against their own evaluator
to stay in sync with it.

``possible(cond, values)`` is the three-valued version used by the reachability analysis: each fact
maps to the set of values it may hold, and the result is the set of outcomes the condition may
have ({True}, {False} or both, i.e. "maybe").
"""

from __future__ import annotations

from .model import All, Any_, Condition, FactTest, Not

TOP = object()  # "any value": used for facts nothing declares or writes


def _same(a, b) -> bool:
    return type(a) is type(b) and a == b


def test_value(value, op: str | None, operand) -> bool:
    if op is None:
        return bool(value)
    if op == "eq":
        return _same(value, operand)
    if op == "in":
        return any(_same(value, item) for item in operand)
    is_int = isinstance(value, int) and not isinstance(value, bool)
    if op == "gt":
        return is_int and value > operand
    if op == "lt":
        return is_int and value < operand
    raise ValueError(f"unknown operator {op!r}")


def evaluate(cond: Condition, state: dict) -> bool:
    if isinstance(cond, FactTest):
        return test_value(state.get(cond.fact), cond.op, cond.value)
    if isinstance(cond, Not):
        return not evaluate(cond.item, state)
    if isinstance(cond, All):
        return all(evaluate(item, state) for item in cond.items)
    return any(evaluate(item, state) for item in cond.items)


BOTH = frozenset((True, False))


def possible(cond: Condition, values, resolve=lambda f: f) -> frozenset:
    """Outcomes ``cond`` may have when each fact ranges over ``values[fact]`` independently."""
    if isinstance(cond, FactTest):
        vals = values.get(resolve(cond.fact), (None,))
        if TOP in vals:
            return BOTH
        return frozenset(test_value(v, cond.op, cond.value) for v in vals)
    if isinstance(cond, Not):
        return frozenset(not b for b in possible(cond.item, values, resolve))
    outcomes = [possible(item, values, resolve) for item in cond.items]
    if isinstance(cond, All):
        result = set()
        if all(True in o for o in outcomes):
            result.add(True)
        if any(False in o for o in outcomes):
            result.add(False)
        return frozenset(result)
    result = set()
    if any(True in o for o in outcomes):
        result.add(True)
    if all(False in o for o in outcomes):
        result.add(False)
    return frozenset(result)
