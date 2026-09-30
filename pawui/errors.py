"""PawUI 统一错误类型与友好的错误提示。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    line: int
    col: int = 0

    def __str__(self) -> str:
        return f"{self.line}:{self.col}"


class PawUIError(Exception):
    """PawUI 错误基类，携带位置信息。"""

    def __init__(self, message: str, pos: Position | None = None):
        self.message = message
        self.pos = pos
        super().__init__(self.formatted())

    def formatted(self) -> str:
        location = f"  (at line {self.pos})" if self.pos else ""
        return f"PawUI error: {self.message}{location}"


class LexerError(PawUIError):
    pass


class ParseError(PawUIError):
    pass


class ComponentError(PawUIError):
    pass


class RenderError(PawUIError):
    pass


class ScriptError(PawUIError):
    """script 块里的 Python 代码编译/执行失败。"""

    def __init__(self, message: str, pos: Position | None = None, cause: Exception | None = None):
        self.cause = cause
        detail = f"{message}: {cause}" if cause else message
        super().__init__(detail, pos)


# 历史名字：早期项目内部叫 PyX，保留别名不算破坏性变更
PyxError = PawUIError
