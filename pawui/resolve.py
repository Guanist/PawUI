"""运行时值解析：props / 模板 / 事件回调。纯逻辑，不依赖任何 GUI 后端。"""

from __future__ import annotations

import re
from typing import Any

from .nodes import Symbol

runtime_refs_re = re.compile(
    r"\{\$([A-Za-z_][A-Za-z0-9_]*)\}|\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
)


def is_template(v: Any) -> bool:
    return isinstance(v, str) and ("$" in v or "{" in v)


def _ref_of(match: re.Match) -> str:
    return match.group(1) or match.group(2) or match.group(3) or ""


def runtime_refs(template: str) -> list[str]:
    out: list[str] = []
    for m in runtime_refs_re.finditer(template):
        g = _ref_of(m)
        if g:
            out.append(g)
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


def resolve_symbol(sym: Symbol, scope: dict, runtime: Any) -> Any:
    return _lookup_name(sym.name, scope, runtime, fallback=sym.name)


def resolve_prop_value(value: Any, scope: dict, runtime: Any) -> Any:
    if isinstance(value, Symbol):
        return resolve_symbol(value, scope, runtime)
    if is_template(value):
        return resolve_template(value, scope, runtime)
    if isinstance(value, str):
        name = value.strip()
        if hasattr(runtime.theme, name):
            return getattr(runtime.theme, name)
        custom = getattr(runtime.theme, "custom", {})
        if name in custom:
            return custom[name]
    return value


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
        value = _resolve_named(ref, scope, runtime)
        if isinstance(value, str) and is_template(value) and ref not in seen:
            seen.add(ref)
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
