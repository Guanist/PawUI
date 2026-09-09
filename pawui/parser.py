"""PyUI HTML 风格解析器：<tag attr="v">content</tag>。

支持：
  - 普通元素 / 自闭合元素
  - 属性（key="v"、key='v'、key=v、裸布尔属性）
  - 文本内容（<Text>hello</Text>）
  - <!-- 注释 -->
  - <Component name="X">...</Component>  组件定义
  - <script>...</script>                原始 Python 块
"""

from __future__ import annotations

from typing import Any

from .errors import ParseError, Position
from .nodes import Element, Program, ScriptBlock


class _Scanner:
    def __init__(self, src: str):
        self.src = src
        self.i = 0
        self.line = 1
        self.col = 1
        self.n = len(src)

    def eof(self) -> bool:
        return self.i >= self.n

    def peek(self, k: int = 0) -> str:
        idx = self.i + k
        return self.src[idx] if idx < self.n else ""

    def advance(self) -> str:
        c = self.src[self.i]
        self.i += 1
        if c == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c

    def pos(self) -> Position:
        return Position(self.line, self.col)

    def skip_ws(self) -> None:
        while not self.eof() and self.peek() in " \t\r\n":
            self.advance()

    def starts_with(self, s: str) -> bool:
        return self.src.startswith(s, self.i)

    def read_until(self, token: str) -> str:
        idx = self.src.find(token, self.i)
        if idx == -1:
            raise ParseError(f"expected {token!r}", self.pos())
        text = self.src[self.i:idx]
        while self.i < idx:
            self.advance()
        return text


class ParS:
    def __init__(self, source: str, filename: str = "<memory>"):
        self.s = _Scanner(source)
        self.filename = filename

    def parse(self) -> Program:
        program = Program()
        while not self.s.eof():
            self.s.skip_ws()
            if self.s.eof():
                break
            if self.s.starts_with("<!--"):
                self._skip_comment()
                continue
            if self.s.peek() == "<" and self._is_script_open():
                program.script = self._read_script()
                continue
            if self.s.peek() == "<":
                program.elements.append(self._read_element())
            else:
                self.s.advance()
        return program

    def _is_script_open(self) -> bool:
        low = self.s.src[self.s.i:self.s.i + 8].lower()
        return low.startswith("<script") and self.s.peek(7) in "> \t\r\n"

    def _read_script(self) -> ScriptBlock:
        start = self.s.pos()
        self._read_tag_open()
        src = self.s.read_until("</script")
        self._consume_close_tag("script")
        return ScriptBlock(src.strip("\n"), start)

    def _read_element(self) -> Element:
        start = self.s.pos()
        tag, attrs, self_closing = self._read_tag_open()
        el = Element(tag=tag, props=dict(attrs), pos=start, is_block=not self_closing)
        el.props.pop("__content__", None)
        if self_closing:
            return el
        children, content = self._read_children(tag)
        el.children = children
        if not children and content:
            el.props["__content__"] = content
        if tag.lower() == "component":
            name = attrs.get("name")
            if not name:
                raise ParseError("<Component> requires a name attribute", start)
            el.tag = "component"
            el.name = str(name)
        return el

    def _read_children(self, tag: str) -> tuple[list[Element], str]:
        children: list[Element] = []
        buf: list[str] = []
        while True:
            self.s.skip_ws()
            if self.s.eof():
                raise ParseError(f"unclosed tag <{tag}>", self.s.pos())
            if self.s.starts_with("</"):
                self._consume_close_tag(tag)
                break
            if self.s.starts_with("<!--"):
                self._skip_comment()
                continue
            if self.s.peek() == "<":
                children.append(self._read_element())
                buf = []
            else:
                buf.append(self._read_text())
        return children, "".join(buf).strip()

    def _read_text(self) -> str:
        out: list[str] = []
        while not self.s.eof() and self.s.peek() != "<":
            out.append(self.s.advance())
        return "".join(out)

    def _read_tag_open(self) -> tuple[str, dict[str, Any], bool]:
        if self.s.peek() != "<":
            raise ParseError("expected '<'", self.s.pos())
        self.s.advance()
        tag = self._read_tagname()
        attrs: dict[str, Any] = {}
        self_closing = False
        while True:
            self.s.skip_ws()
            c = self.s.peek()
            if c == ">":
                self.s.advance()
                break
            if c == "/" and self.s.peek(1) == ">":
                self.s.advance()
                self.s.advance()
                self_closing = True
                break
            if c == "":
                raise ParseError(f"unterminated tag <{tag}>", self.s.pos())
            name = self._read_tagname()
            if not name:
                raise ParseError("malformed attribute", self.s.pos())
            self.s.skip_ws()
            if self.s.peek() == "=":
                self.s.advance()
                self.s.skip_ws()
                attrs[name] = self._read_value()
            else:
                attrs[name] = True
        return tag, attrs, self_closing

    def _read_value(self) -> Any:
        c = self.s.peek()
        if c in "\"'":
            q = self.s.advance()
            quoted: list[str] = []
            while not self.s.eof() and self.s.peek() != q:
                ch = self.s.advance()
                if ch == "\\" and not self.s.eof():
                    quoted.append(self.s.advance())
                else:
                    quoted.append(ch)
            if not self.s.eof():
                self.s.advance()
            return "".join(quoted)
        unquoted: list[str] = []
        while not self.s.eof() and self.s.peek() not in " \t\r\n>":
            unquoted.append(self.s.advance())
        text = "".join(unquoted)
        if text in ("true", "True"):
            return True
        if text in ("false", "False"):
            return False
        return text

    def _read_tagname(self) -> str:
        out: list[str] = []
        while not self.s.eof() and self.s.peek() not in " \t\r\n>/=":
            out.append(self.s.advance())
        return "".join(out)

    def _consume_close_tag(self, tag: str) -> None:
        if self.s.starts_with("</"):
            self.s.advance()
            self.s.advance()
        close_name = self._read_tagname()
        if close_name.lower() != tag.lower():
            raise ParseError(f"mismatched closing tag: expected </{tag}> got </{close_name}>", self.s.pos())
        while not self.s.eof() and self.s.peek() != ">":
            self.s.advance()
        if not self.s.eof():
            self.s.advance()

    def _skip_comment(self) -> None:
        idx = self.s.src.find("-->", self.s.i)
        if idx == -1:
            raise ParseError("unterminated comment", self.s.pos())
        while self.s.i < idx + 3:
            self.s.advance()


def parse(source: str, filename: str = "<memory>") -> Program:
    return ParS(source, filename).parse()
