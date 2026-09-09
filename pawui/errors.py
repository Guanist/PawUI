"""PawUI 统一错误类型与友好的错误提示。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    line: int
    col: int = 0

    def __str__(self) -> str:
        return f"{self.line}:{self.col}"


class PyxError(Exception):
    """PyX 错误基类，携带位置信息。"""

    def __init__(self, message: str, pos: Position | None = None):
        self.message = message
        self.pos = pos
        super().__init__(self.formatted())

    def formatted(self) -> str:
        location = f"  (at line {self.pos})" if self.pos else ""
        return f"PawUI error: {self.message}{location}"


class LexerError(PyxError):
    pass


class ParseError(PyxError):
    pass


class ComponentError(PyxError):
    pass


class RenderError(PyxError):
    pass


class ScriptError(PyxError):
    """script 块里的 Python 代码编译/执行失败。"""

    def __init__(self, message: str, pos: Position | None = None, cause: Exception | None = None):
        self.cause = cause
        detail = f"{message}: {cause}" if cause else message
        super().__init__(detail, pos)
