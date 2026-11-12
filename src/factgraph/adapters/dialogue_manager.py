"""Dialogue Manager adapter: reads the JSON written by the Godot-side exporter.

The exporter compiles each ``.dialogue`` file with Dialogue Manager's own compiler, so this adapter
never parses dialogue syntax. It only interprets the compiled line graph and the expression tokens,
mapping them to facts through a configurable vocabulary:

    [vocabulary.read]                  # functions whose first string argument names a fact
    has = "fact"
    [vocabulary.write]                 # functions that write facts
    set_fact = "set"                   # set_fact("id") / set_fact("id", value)
    add = "inc"                        # add("id") / add("id", amount)
    give_item = { set = "item.{}" }    # give_item("oar") -> set item.oar = true
    [vocabulary]
    ignore = ["play_sound"]            # calls with no effect on facts
    variables = false                  # true: bare (dotted) variables are fact IDs

    [[sources.dialogue_manager]]
    export = "build/dialogue.json"     # the exporter's output, relative to the config
    res_root = "game"                  # where res:// points, for file:line in reports
    static_tags = { chapter = "1" }

Every line that shows text, offers a choice or mutates state becomes a beat whose condition is the
conjunction of the ``if``/``elif``/``else`` branches and response conditions on the way to it from
any cue. Anything the vocabulary doesn't cover is reported, not guessed.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..model import TRUE, All, Any_, Beat, Condition, Effect, FactTest, Finding, Not, Source
from ..syntax import SyntaxProblem, effect_from_template

FORMAT = "factgraph-dialogue-manager"
SUPPORTED_DM_MAJOR = (4,)
MUTATION_CODES = ("do", "do!", "set", "$>", "$>>")
MAX_PATHS_PER_LINE = 8


class Unmapped(Exception):
    pass


def load_dialogue_manager_source(entry: dict, root: Path, config: dict):
    findings: list[Finding] = []
    export_rel = entry.get("export", "")
    try:
        data = json.loads((root / export_rel).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return [], [Finding("adapter", f"dialogue export not found: {export_rel} (run the Godot exporter first)")]
    except json.JSONDecodeError as exc:
        return [], [Finding("adapter", f"invalid JSON: {exc.msg}", Source(export_rel, exc.lineno))]
    if data.get("format") != FORMAT:
        return [], [Finding("adapter", f"{export_rel} is not a factgraph Dialogue Manager export", Source(export_rel))]
    version = str(data.get("dialogue_manager", ""))
    major = version.split(".")[0]
    if not major.isdigit() or int(major) not in SUPPORTED_DM_MAJOR:
        findings.append(
            Finding("adapter", f"Dialogue Manager {version or '?'} is untested; supported: 4.x", Source(export_rel), "warning")
        )

    vocab = {**config.get("vocabulary", {}), **entry.get("vocabulary", {})}
    beats: list[Beat] = []
    for file_data in data.get("files", []):
        file_beats, file_findings = _DialogueFile(file_data, entry, vocab).load()
        beats += file_beats
        findings += file_findings
    return beats, findings


def _line_number(line_id: str) -> int:
    head = line_id.split(".")[0]
    return int(head) + 1 if head.isdigit() else 0


def conj(a: Condition, b: Condition) -> Condition:
    if a == TRUE:
        return b
    if b == TRUE:
        return a
    items = (a.items if isinstance(a, All) else (a,)) + (b.items if isinstance(b, All) else (b,))
    return All(items)


def disj(conds: list[Condition]) -> Condition:
    if not conds or TRUE in conds:
        return TRUE
    return conds[0] if len(conds) == 1 else Any_(tuple(conds))


class _DialogueFile:
    def __init__(self, data: dict, entry: dict, vocab: dict):
        self.data = data
        self.lines: dict = data.get("lines", {})
        self.res_path: str = data.get("path", "")
        local = self.res_path.removeprefix("res://")
        res_root = entry.get("res_root", "")
        self.rel = f"{res_root.rstrip('/')}/{local}" if res_root else local
        self.id_base = local.removesuffix(".dialogue")
        self.static_tags = {k: str(v) for k, v in entry.get("static_tags", {}).items()}
        self.vocab = vocab
        self.findings: list[Finding] = []
        self.reported: set[tuple[str, str]] = set()
        self.incoming: dict[str, list[Condition]] = {}
        self.cue_of: dict[str, str] = {}
        self.expr_cache: dict[tuple[str, str], Condition | None] = {}

    # --- reporting ----------------------------------------------------------

    def src(self, line_id: str) -> Source:
        return Source(self.rel, _line_number(line_id))

    def unmapped(self, line_id: str, what: str, reason: str):
        key = (line_id, what)
        if key in self.reported:
            return
        self.reported.add(key)
        raw = self.data.get("sources", {}).get(line_id, "")
        shown = f" '{raw.strip()}'" if raw.strip() else ""
        self.findings.append(Finding("adapter", f"unmapped {what}{shown}: {reason}", self.src(line_id)))

    # --- loading ------------------------------------------------------------

    def load(self):
        for err in self.data.get("errors", []):
            message = err.get("message") or f"error {err.get('error')}"
            self.findings.append(
                Finding("adapter", f"Dialogue Manager: {message}", Source(self.rel, int(err.get("line", 0))))
            )
        self.walk()
        return self.make_beats(), self.findings

    def condition_of(self, line_id: str, key: str = "condition", what: str = "condition") -> Condition | None:
        """The line's own condition, or None if it can't be mapped (already reported)."""
        cache_key = (line_id, key)
        if cache_key not in self.expr_cache:
            expr = self.lines[line_id].get(key, {}).get("expression")
            try:
                self.expr_cache[cache_key] = TRUE if not expr else _Translator(self, line_id).condition(expr)
            except Unmapped as exc:
                self.unmapped(line_id, what, str(exc))
                self.expr_cache[cache_key] = None
        return self.expr_cache[cache_key]

    def walk(self):
        """Propagate path conditions from every cue through the line graph.

        A branch's condition is scoped to its block: each work item carries a stack of
        (exit line, condition to restore) so that lines after an if/else or a response
        group are not gated by the branch that happened to lead there.
        """
        # Every cue is an entry point (the game may start any of them). Lines before the first cue
        # are walked last, so lines reachable from a cue get tagged with it. The work list is a stack.
        numeric = sorted((i for i in self.lines if i.isdigit()), key=int)
        starts = [(numeric[0], "")] if numeric else []
        starts += [(target, cue) for cue, target in reversed(self.data.get("cues", {}).items())]
        work = [(line_id, TRUE, cue, ()) for line_id, cue in starts]
        seen: dict[str, set] = {}
        while work:
            line_id, cond, cue, scopes = work.pop()
            while scopes and scopes[-1][0] == line_id:
                cond, scopes = scopes[-1][1], scopes[:-1]
            if line_id in ("", "end", "end!") or "@" in line_id or line_id not in self.lines:
                continue
            states = seen.setdefault(line_id, set())
            if (cond, scopes) in states or (TRUE, ()) in states:
                continue
            if len(states) >= MAX_PATHS_PER_LINE:
                cond, scopes = TRUE, ()  # too many paths: widen (stays an over-approximation)
            states.add((cond, scopes))
            incoming = self.incoming.setdefault(line_id, [])
            if cond not in incoming:
                incoming.append(cond)
            if cue and line_id not in self.cue_of:
                self.cue_of[line_id] = cue
            work += [(nxt, c, cue, s) for nxt, c, s in self.successors(line_id, cond, scopes)]

    def successors(self, line_id: str, cond: Condition, scopes: tuple):
        line = self.lines[line_id]
        kind = line.get("type")
        nxt = line.get("next_id", "")
        after = line.get("next_id_after", "")
        if kind == "condition":
            inner = scopes + ((after, cond),)
            if "condition" not in line:  # else
                return [(nxt, cond, inner)]
            own = self.condition_of(line_id)
            otherwise = line.get("next_sibling_id") or after
            # The elif/else chain shares the block's exit, so it restores the pre-chain condition too.
            if own is None:
                return [(nxt, cond, inner), (otherwise, cond, inner)]
            return [(nxt, conj(cond, own), inner), (otherwise, conj(cond, Not(own)), inner)]
        if kind == "while":
            own = self.condition_of(line_id)
            body = cond if own is None else conj(cond, own)
            return [(nxt, body, scopes + ((line_id, cond),)), (after, cond, scopes)]
        if kind == "match":
            out = [(after, cond, scopes)]
            for case in line.get("cases", []):
                if isinstance(case, dict):
                    out += [(case[k], cond, scopes) for k in ("id", "next_id") if case.get(k)]
            return out
        if kind == "response":
            out = [(rid, cond, scopes) for rid in line.get("responses", []) if rid != line_id]
            own = self.condition_of(line_id, what="response condition")
            inner = scopes + ((after, cond),)
            out.append((nxt, cond if own is None else conj(cond, own), inner))
            return out
        out = [(nxt, cond, scopes)]
        if kind == "goto" and line.get("is_snippet"):
            out.append((after, cond, scopes))
        for sibling in line.get("siblings", []):
            if isinstance(sibling, dict) and sibling.get("id"):
                out.append((sibling["id"], cond, scopes))
        return out

    def make_beats(self) -> list[Beat]:
        beats = []
        for line_id in sorted(self.incoming, key=lambda i: [int(p) if p.isdigit() else 0 for p in i.split(".")]):
            line = self.lines[line_id]
            kind = line.get("type")
            if kind not in ("dialogue", "response", "mutation"):
                continue
            requires = disj(self.incoming[line_id])
            if kind == "response":
                own = self.condition_of(line_id, what="response condition")
                requires = requires if own is None else conj(requires, own)
            effects: list[Effect] = []
            if kind == "mutation":
                effects += self.effects_of(line_id, line.get("mutation", {}).get("expression") or [])
            beat_id = line.get("static_id") or f"{self.id_base}:{_line_number(line_id)}"
            tags = dict(self.static_tags, file=self.rel)
            if line_id in self.cue_of:
                tags["cue"] = self.cue_of[line_id]
            if line.get("character"):
                tags["character"] = line["character"]
            fragments = []
            for item in self.data.get("inline", {}).get(line_id, []):
                code = item.get("code", "")
                if code in MUTATION_CODES:
                    effects += self.effects_of(line_id, item.get("expression") or [])
                elif code == "if":
                    try:
                        own = _Translator(self, line_id).condition(item.get("expression") or [])
                    except Unmapped as exc:
                        self.unmapped(line_id, "inline condition", str(exc))
                        continue
                    fragments.append(
                        Beat(f"{beat_id}#if{len(fragments) + 1}", "dialogue_fragment", self.src(line_id), conj(requires, own), [], tags)
                    )
            beat_kind = {"dialogue": "dialogue_line", "response": "choice", "mutation": "dialogue_effect"}[kind]
            beats.append(Beat(beat_id, beat_kind, self.src(line_id), requires, effects, tags))
            beats += fragments
        return beats

    def effects_of(self, line_id: str, expr: list) -> list[Effect]:
        try:
            return _Translator(self, line_id).effects(expr)
        except Unmapped as exc:
            self.unmapped(line_id, "mutation", str(exc))
            return []


class _Translator:
    """Translate one DM token list into a Condition or Effects, through the vocabulary."""

    def __init__(self, file: _DialogueFile, line_id: str):
        self.file = file
        self.source = file.src(line_id)
        vocab = file.vocab
        self.reads: dict = vocab.get("read", {})
        self.writes: dict = vocab.get("write", {})
        self.ignore: set = set(vocab.get("ignore", []))
        self.variables: bool = bool(vocab.get("variables", False))

    # --- conditions ---------------------------------------------------------

    def condition(self, tokens: list) -> Condition:
        self.tokens = _clean(tokens)
        self.pos = 0
        result = self.parse_or()
        if self.pos != len(self.tokens):
            raise Unmapped(f"unexpected {self.tokens[self.pos].get('type')}")
        return result

    def peek(self, kind: str, value=None) -> bool:
        if self.pos >= len(self.tokens):
            return False
        tok = self.tokens[self.pos]
        return tok.get("type") == kind and (value is None or tok.get("value") == value)

    def parse_or(self) -> Condition:
        items = [self.parse_and()]
        while self.peek("and_or", "or"):
            self.pos += 1
            items.append(self.parse_and())
        return items[0] if len(items) == 1 else Any_(tuple(items))

    def parse_and(self) -> Condition:
        items = [self.parse_not()]
        while self.peek("and_or", "and"):
            self.pos += 1
            items.append(self.parse_not())
        return items[0] if len(items) == 1 else All(tuple(items))

    def parse_not(self) -> Condition:
        if self.peek("not"):
            self.pos += 1
            return Not(self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Condition:
        left = self.operand()
        if not self.peek("comparison"):
            return self.as_condition(left)
        op = self.tokens[self.pos]["value"]
        self.pos += 1
        right = self.operand()
        if left[0] == "lit" and right[0] == "fact":
            left, right = right, left
            op = {">": "<", "<": ">", ">=": "<=", "<=": ">="}.get(op, op)
        if left[0] != "fact" or right[0] != "lit":
            raise Unmapped("only comparisons between a fact and a literal are supported")
        return self.compare(left[1], op, right[1])

    def compare(self, fact: str, op: str, value) -> Condition:
        test = lambda o=None, v=None: FactTest(fact, o, v, source=self.source)  # noqa: E731
        if op in ("==", "!="):
            if isinstance(value, bool):
                positive = test() if value else Not(test())
            else:
                positive = test("eq", value)
            return positive if op == "==" else _negate(positive)
        if op in (">", "<", ">=", "<="):
            if isinstance(value, bool) or not isinstance(value, int):
                raise Unmapped(f"'{op}' needs an integer literal")
            if op == ">=":
                return test("gt", value - 1)
            if op == "<=":
                return test("lt", value + 1)
            return test("gt" if op == ">" else "lt", value)
        if op == "in" and isinstance(value, tuple):
            return test("in", value)
        raise Unmapped(f"comparison '{op}' is not supported")

    def as_condition(self, operand) -> Condition:
        kind, value = operand
        if kind == "fact":
            return FactTest(value, source=self.source)
        if kind == "cond":
            return value
        if kind == "lit" and value is True:
            return TRUE
        raise Unmapped("a literal is not a condition")

    def operand(self):
        if self.pos >= len(self.tokens):
            raise Unmapped("incomplete expression")
        tok = self.tokens[self.pos]
        self.pos += 1
        kind = tok.get("type")
        if kind == "function":
            name = tok.get("function", "")
            if name not in self.reads:
                raise Unmapped(f"function '{name}' is not in the read vocabulary")
            return ("fact", self.fact_arg(name, tok))
        if kind == "variable":
            return ("fact", self.variable_chain(tok))
        if kind in ("string", "number", "bool"):
            return ("lit", tok.get("value"))
        if kind == "array":
            values = []
            for item in tok.get("value", []):
                item = _clean(item)
                if len(item) != 1 or item[0].get("type") not in ("string", "number", "bool"):
                    raise Unmapped("arrays must hold literals")
                values.append(item[0]["value"])
            return ("lit", tuple(values))
        if kind == "group":
            sub = _Translator(self.file, "0")
            sub.source = self.source
            return ("cond", sub.condition(tok.get("value", [])))
        raise Unmapped(f"unsupported token '{kind}'")

    def variable_chain(self, tok) -> str:
        if not self.variables:
            raise Unmapped(f"variable '{tok.get('value')}' (enable vocabulary.variables to read variables as facts)")
        parts = [tok.get("value", "")]
        while self.peek("dot") and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].get("type") == "variable":
            parts.append(self.tokens[self.pos + 1]["value"])
            self.pos += 2
        return ".".join(parts)

    def args(self, tok) -> list:
        """Literal arguments of a call."""
        values = []
        for arg in tok.get("value", []):
            arg = _clean(arg)
            if not arg:
                continue
            if len(arg) != 1 or arg[0].get("type") not in ("string", "number", "bool"):
                raise Unmapped(f"arguments to '{tok.get('function')}' must be literals")
            values.append(arg[0]["value"])
        return values

    def fact_arg(self, name: str, tok) -> str:
        args = self.args(tok)
        if not args or not isinstance(args[0], str):
            raise Unmapped(f"'{name}' needs a fact ID string as its first argument")
        return args[0]

    # --- effects --------------------------------------------------------------

    def effects(self, tokens: list) -> list[Effect]:
        tokens = _clean(tokens)
        if len(tokens) == 1 and tokens[0].get("type") == "function":
            return self.call_effect(tokens[0])
        if tokens and tokens[0].get("type") == "variable":
            self.tokens, self.pos = tokens, 0
            self.pos = 1
            fact = self.variable_chain(tokens[0])
            rest = tokens[self.pos:]
            if len(rest) == 2 and rest[0].get("type") == "assignment" and rest[1].get("type") in ("string", "number", "bool"):
                op, value = rest[0]["value"], rest[1]["value"]
                if op == "=":
                    return [Effect("set", fact, value, self.source)]
                if op in ("+=", "-=") and isinstance(value, int) and not isinstance(value, bool):
                    return [Effect("inc", fact, value if op == "+=" else -value, self.source)]
            raise Unmapped("only '=', '+=' and '-=' with a literal are supported")
        raise Unmapped("expected a single call or assignment")

    def call_effect(self, tok) -> list[Effect]:
        name = tok.get("function", "")
        if name in self.ignore:
            return []
        if name not in self.writes:
            raise Unmapped(f"function '{name}' is not in the write vocabulary")
        spec = self.writes[name]
        args = self.args(tok)
        if isinstance(spec, dict):
            if not args:
                raise Unmapped(f"'{name}' needs an argument")
            try:
                return [effect_from_template(spec, args[0], self.source)]
            except SyntaxProblem as exc:
                raise Unmapped(str(exc)) from None
        fact = self.fact_arg(name, tok)
        if spec == "set":
            return [Effect("set", fact, args[1] if len(args) > 1 else True, self.source)]
        if spec == "inc":
            return [Effect("inc", fact, args[1] if len(args) > 1 else 1, self.source)]
        raise Unmapped(f"vocabulary entry for '{name}' must be 'set', 'inc' or a template")


def _clean(tokens) -> list:
    """Drop the closing-bracket tokens DM keeps at the end of groups and argument lists."""
    return [t for t in tokens if isinstance(t, dict) and t.get("type") not in ("parens_close", "bracket_close", "brace_close")]


def _negate(cond: Condition) -> Condition:
    return cond.item if isinstance(cond, Not) else Not(cond)
