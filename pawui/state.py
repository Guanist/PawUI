"""PawUI 响应式状态：state.key = value 触发所有绑定的 widget 自动刷新。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class State:
    """一个轻量的响应式状态容器。

    - 通过属性或键访问：``state.greeting`` / ``state["greeting"]``
    - 写入：``state.greeting = "hi"`` 或 ``state.set("greeting", "hi")``
    - 订阅：``state.watch("greeting", fn)``，fn 在新值写入时被调用
    - 绑定：``Text "$greeting"`` 会在 greeting 变化时自动更新
    """

    def __init__(self, initial: dict[str, Any] | None = None):
        object.__setattr__(self, "_data", dict(initial or {}))
        object.__setattr__(self, "_listeners", defaultdict(list))

    # ---- dict 风格操作 ----
    def get(self, key: str, default: Any = "") -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        for fn in self._listeners.get(key, []):
            fn(value)
        for fn in self._listeners.get("*", []):
            fn(value)

    def has(self, key: str) -> bool:
        return key in self._data

    def watch(self, key: str, fn: Callable[[Any], None]) -> Callable[[], None]:
        """订阅某个键（'*' 表示订阅全部），返回一个退订函数。"""
        self._listeners[key].append(fn)
        return lambda: self._listeners[key].remove(fn) if fn in self._listeners[key] else None

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def snapshot(self) -> dict[str, Any]:
        return dict(self._data)

    # ---- 属性风格访问 ----
    def __getattr__(self, key: str) -> Any:
        # 避免递归陷阱：处理内部属性
        if key in ("_data", "_listeners"):
            return object.__getattribute__(self, key)
        return self.get(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in ("_data", "_listeners"):
            object.__setattr__(self, key, value)
            return
        self.set(key, value)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"State({self._data!r})"
