"""A small JSON reader that remembers the source line of every value.

The standard library parser drops positions, but findings must point at ``file:line``.
Objects, arrays and strings come back as subclasses of dict, list and str carrying a
``line`` attribute (1-based); numbers, booleans and null come back as plain values.
"""

from __future__ import annotations

import json
import re


class LDict(dict):
    line: int = 0


class LList(list):
    line: int = 0


class LStr(str):
    line: int = 0


def line_of(value, default: int = 0) -> int:
    return getattr(value, "line", default)


_WS = re.compile(r"[ \t\n\r]*")
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?")
_STRING = re.compile(r'"(?:[^"\\\x00-\x1f]|\\.)*"', re.DOTALL)


class JSONLocError(ValueError):
    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.line = line


def loads(text: str):
    parser = _Parser(text)
    value = parser.value()
    parser.skip_ws()
    if parser.pos != len(text):
        parser.fail("unexpected trailing content")
    return value


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1

    def fail(self, message: str):
        raise JSONLocError(message, self.line)

    def skip_ws(self):
        match = _WS.match(self.text, self.pos)
        self.line += match.group().count("\n")
        self.pos = match.end()

    def value(self):
        self.skip_ws()
        if self.pos >= len(self.text):
            self.fail("unexpected end of input")
        ch = self.text[self.pos]
        if ch == "{":
            return self.obj()
        if ch == "[":
            return self.arr()
        if ch == '"':
            return self.string()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(word, self.pos):
                self.pos += len(word)
                return val
        match = _NUMBER.match(self.text, self.pos)
        if not match:
            self.fail(f"unexpected character {ch!r}")
        self.pos = match.end()
        return json.loads(match.group())

    def string(self) -> LStr:
        match = _STRING.match(self.text, self.pos)
        if not match:
            self.fail("unterminated string")
        result = LStr(json.loads(match.group()))
        result.line = self.line
        self.line += match.group().count("\n")
        self.pos = match.end()
        return result

    def expect(self, ch: str):
        self.skip_ws()
        if not self.text.startswith(ch, self.pos):
            self.fail(f"expected {ch!r}")
        self.pos += 1

    def obj(self) -> LDict:
        result = LDict()
        result.line = self.line
        self.pos += 1
        self.skip_ws()
        if self.text.startswith("}", self.pos):
            self.pos += 1
            return result
        while True:
            self.skip_ws()
            if not self.text.startswith('"', self.pos):
                self.fail("expected a string key")
            key = self.string()
            self.expect(":")
            result[str(key)] = self.value()
            self.skip_ws()
            if self.text.startswith(",", self.pos):
                self.pos += 1
                continue
            self.expect("}")
            return result

    def arr(self) -> LList:
        result = LList()
        result.line = self.line
        self.pos += 1
        self.skip_ws()
        if self.text.startswith("]", self.pos):
            self.pos += 1
            return result
        while True:
            result.append(self.value())
            self.skip_ws()
            if self.text.startswith(",", self.pos):
                self.pos += 1
                continue
            self.expect("]")
            return result
