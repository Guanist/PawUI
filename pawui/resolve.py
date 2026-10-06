"""运行时值解析：props / 模板 / 事件回调。纯逻辑，不依赖任何 GUI 后端。"""

from __future__ import annotations

import re
from typing import Any

from .nodes import Symbol
from .theme import COLOR_FIELDS

# 匹配 {$a.b[0]} / {a.b[0]} / $a.b[0] 三种插值形式，支持属性/索引路径。
runtime_refs_re = re.compile(
    r"\{\$([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]\s]+\])*)\}"
    r"|\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]\s]+\])*)\}"
    r"|\$([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]\s]+\])*)"
)


def is_template(v: Any) -> bool:
    return isinstance(v, str) and ("$" in v or "{" in v)


def _ref_of(match: re.Match) -> str:
    return match.group(1) or match.group(2) or match.group(3) or ""


def _base_name(ref: str) -> str:
    return ref.split(".", 1)[0].split("[", 1)[0]


def runtime_refs(template: str) -> list[str]:
    out: list[str] = []
    for m in runtime_refs_re.finditer(template):
        ref = _ref_of(m)
        if ref:
            base = _base_name(ref)
            if base not in out:
                out.append(base)
    return out


def _lookup_name(name: str, scope: dict, runtime: Any, fallback: Any = "") -> Any:
    if name in scope:
        return scope[name]
    if runtime.state.has(name):
        return runtime.state.get(name)
    if name in runtime.namespace:
        return runtime.namespace.get(name)
    if hasattr(runtime.theme, name):
        return getattr(runtime.theme, name)
    custom = getattr(runtime.theme, "custom", {})
    if name in custom:
        return custom[name]
    return fallback


def _resolve_path(ref: str, scope: dict, runtime: Any) -> Any:
    """求值一个可能带属性/索引路径的引用：``item.name`` / ``items[0]``。"""
    base = _base_name(ref)
    value = _lookup_name(base, scope, runtime)
    rest = ref[len(base):]
    i = 0
    while i < len(rest):
        c = rest[i]
        if c == ".":
            j = i + 1
            while j < len(rest) and (rest[j].isalnum() or rest[j] == "_"):
                j += 1
            name = rest[i + 1:j]
            try:
                value = getattr(value, name)
            except (AttributeError, TypeError):
                try:
                    value = value[name]
                except Exception:
                    return ""
            i = j
        elif c == "[":
            j = rest.find("]", i)
            if j == -1:
                return ""
            idx_key = rest[i + 1:j].strip()
            if len(idx_key) >= 2 and idx_key[0] in "\"'" and idx_key[-1] == idx_key[0]:
                key: Any = idx_key[1:-1]
            elif idx_key.isdigit():
                key = int(idx_key)
            else:
                key = idx_key
            try:
                value = value[key]
            except Exception:
                return ""
            i = j + 1
        else:
            break
    return value


def resolve_symbol(sym: Symbol, scope: dict, runtime: Any) -> Any:
    return _lookup_name(sym.name, scope, runtime, fallback=sym.name)


def resolve_prop_value(value: Any, scope: dict, runtime: Any) -> Any:
    """解析属性值：Symbol 走名字查找，模板走插值，**普通字符串原样返回**。

    裸字符串以前也会被拿去和主题字段比名字，于是任何撞名的字面量都会被悄悄换掉
    （``<Badge text="text"/>`` 显示 ``#1d1d1f``、``text="radius"`` 显示 ``24``、
    ``text="dark"`` 显示 ``<bound method Theme.dark of ...>`` —— ``hasattr`` 连方法
    名和数字字段都算命中）。

    「令牌名即颜色」只有颜色属性需要，那条路单独放在 :func:`resolve_color`，
    由 ``Component.opt_color`` 调用。
    """
    if isinstance(value, Symbol):
        return resolve_symbol(value, scope, runtime)
    if is_template(value):
        return resolve_template(value, scope, runtime)
    return value


def resolve_color(value: Any, scope: dict, runtime: Any) -> Any:
    """解析颜色属性：裸字符串可以是主题令牌名，也可以是 ``<Color name=...>`` 自定义色名。

    只认 ``COLOR_FIELDS`` 与 ``theme.custom``，避免 ``hasattr(theme, name)``
    把方法名、间距/圆角这类数字字段也当成颜色。
    """
    if isinstance(value, Symbol):
        return resolve_symbol(value, scope, runtime)
    if is_template(value):
        return resolve_template(value, scope, runtime)
    if isinstance(value, str):
        name = value.strip()
        custom = getattr(runtime.theme, "custom", {})
        if name in custom:
            return custom[name]
        if name in COLOR_FIELDS:
            return getattr(runtime.theme, name)
    return value


def resolve_raw(value: Any, scope: dict, runtime: Any, _seen: set | None = None) -> Any:
    """尽量取原始对象值：单个模板引用返回其底层对象（list/dict/...）而非常规化字符串。

    用于需要集合的字面量（``<For in="{$items}">``）和控件取值回调（``bind_state``）。
    链式引用也要穿透：``<Card value="{$name}"/>`` 里的 ``value`` 本身又是 ``{$name}``
    时，必须继续往下求值，否则界面上会直接显示字面量 ``{$name}``。
    """
    if isinstance(value, Symbol):
        return resolve_symbol(value, scope, runtime)
    if isinstance(value, str) and is_template(value):
        refs = runtime_refs(value)
        stripped = value.strip()
        if len(refs) == 1 and stripped in (
            f"{{${refs[0]}}}",
            f"{{{refs[0]}}}",
            f"${refs[0]}",
        ):
            resolved = _resolve_path(refs[0], scope, runtime)
            seen = set(_seen) if _seen else set()
            base = _base_name(refs[0])
            if isinstance(resolved, str) and is_template(resolved) and base not in seen:
                seen.add(base)
                return resolve_raw(resolved, scope, runtime, seen)
            return resolved
    return resolve_prop_value(value, scope, runtime)


def resolve_handler(value: Any, scope: dict, runtime: Any) -> Any:
    if isinstance(value, Symbol):
        name = value.name
    elif isinstance(value, str):
        name = value.strip()
        if name.startswith("{") and name.endswith("}"):
            name = name[1:-1].strip()
    else:
        return value if callable(value) else None
    resolved = _lookup_name(name, scope, runtime, fallback=None)
    return resolved if callable(resolved) else None


def _resolve_named(ref: str, scope: dict, runtime: Any) -> Any:
    return _lookup_name(ref, scope, runtime, fallback="")


def resolve_template(template: str, scope: dict, runtime: Any, _seen=None) -> str:
    seen = set(_seen) if _seen else set()

    def repl(match) -> str:
        ref = _ref_of(match)
        value = _resolve_path(ref, scope, runtime)
        base = _base_name(ref)
        if isinstance(value, str) and is_template(value) and base not in seen:
            seen.add(base)
            value = resolve_template(value, scope, runtime, seen)
        if callable(value):
            value = runtime.invoke(value)
        return str(value)

    return runtime_refs_re.sub(repl, template)


def collect_refs(template: str, scope: dict, runtime: Any) -> set[str]:
    acc: set[str] = set()
    seen: set[str] = set()

    def rec(t: str) -> None:
        for ref in runtime_refs(t):
            if ref in seen:
                continue
            seen.add(ref)
            acc.add(ref)
            val = scope.get(ref)
            if isinstance(val, str) and is_template(val):
                rec(val)

    rec(template)
    return acc
