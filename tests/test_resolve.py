"""Tests for the PawUI resolver."""

import pytest

from pawui.nodes import Symbol
from pawui.resolve import (
    collect_refs,
    is_template,
    resolve_handler,
    resolve_prop_value,
    resolve_raw,
    resolve_template,
)
from pawui.state import State
from pawui.theme import Theme


class MockRuntime:
    def __init__(self):
        self.state = State()
        self.namespace = {}
        self.theme = Theme.dark()

    def invoke(self, fn, *args):
        if callable(fn):
            return fn(*args)
        return None


@pytest.fixture
def runtime():
    return MockRuntime()


@pytest.fixture
def scope():
    return {"local_var": "local_value"}


class TestIsTemplate:
    def test_detects_dollar_brace(self):
        assert is_template("{$var}") is True

    def test_detects_brace(self):
        assert is_template("{var}") is True

    def test_detects_dollar(self):
        assert is_template("$var") is True

    def test_plain_string(self):
        assert is_template("hello") is False

    def test_non_string(self):
        assert is_template(123) is False
        assert is_template(None) is False


class TestResolvePropValue:
    def test_resolves_symbol_from_scope(self, runtime, scope):
        sym = Symbol(name="local_var", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == "local_value"

    def test_resolves_symbol_from_state(self, runtime, scope):
        runtime.state.set("state_var", "state_value")
        sym = Symbol(name="state_var", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == "state_value"

    def test_resolves_symbol_from_namespace(self, runtime, scope):
        runtime.namespace["ns_var"] = "ns_value"
        sym = Symbol(name="ns_var", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == "ns_value"

    def test_resolves_symbol_from_theme(self, runtime, scope):
        sym = Symbol(name="accent", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == runtime.theme.accent

    def test_resolves_custom_theme_color(self, runtime, scope):
        runtime.theme.custom["brand"] = "#ff0000"
        sym = Symbol(name="brand", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == "#ff0000"

    def test_returns_fallback_for_unknown(self, runtime, scope):
        sym = Symbol(name="unknown", pos=None)
        result = resolve_prop_value(sym, scope, runtime)
        assert result == "unknown"

    def test_resolves_template_string(self, runtime, scope):
        runtime.state.set("name", "World")
        result = resolve_prop_value("Hello {$name}", scope, runtime)
        assert result == "Hello World"

    def test_passes_through_non_template(self, runtime, scope):
        result = resolve_prop_value("plain string", scope, runtime)
        assert result == "plain string"

    def test_resolves_theme_color_by_name(self, runtime, scope):
        result = resolve_prop_value("accent", scope, runtime)
        assert result == runtime.theme.accent


class TestResolveTemplate:
    def test_simple_interpolation(self, runtime, scope):
        runtime.state.set("count", 42)
        result = resolve_template("Count: {$count}", scope, runtime)
        assert result == "Count: 42"

    def test_multiple_interpolations(self, runtime, scope):
        runtime.state.set("a", 1)
        runtime.state.set("b", 2)
        result = resolve_template("{$a} + {$b} = {$a}", scope, runtime)
        assert result == "1 + 2 = 1"

    def test_brace_syntax(self, runtime, scope):
        runtime.state.set("name", "Test")
        result = resolve_template("Hello {name}", scope, runtime)
        assert result == "Hello Test"

    def test_dollar_syntax(self, runtime, scope):
        runtime.state.set("name", "Test")
        result = resolve_template("Hello $name", scope, runtime)
        assert result == "Hello Test"

    def test_nested_templates(self, runtime, scope):
        scope["template"] = "{$inner}"
        runtime.state.set("inner", "deep")
        result = resolve_template("{$template}", scope, runtime)
        assert result == "deep"

    def test_callable_in_template(self, runtime, scope):
        def get_value():
            return "called"
        runtime.namespace["get_value"] = get_value
        result = resolve_template("{$get_value}", scope, runtime)
        assert result == "called"

    def test_attribute_path(self, runtime, scope):
        scope["item"] = {"name": "Alice", "meta": {"level": 3}}
        assert resolve_template("{$item.name}", scope, runtime) == "Alice"
        assert resolve_template("{$item.meta.level}", scope, runtime) == "3"

    def test_index_path(self, runtime, scope):
        scope["items"] = ["a", "b", "c"]
        assert resolve_template("{$items[1]}", scope, runtime) == "b"

    def test_mixed_dollar_path(self, runtime, scope):
        scope["item"] = {"label": "x"}
        assert resolve_template("$item.label", scope, runtime) == "x"

    def test_attr_fallback_to_item(self, runtime, scope):
        scope["item"] = {"name": "Bob"}
        assert resolve_template("{$item.name}", scope, runtime) == "Bob"


class TestResolveRaw:
    def test_returns_list_for_single_ref(self, runtime, scope):
        runtime.state.set("items", [1, 2, 3])
        assert resolve_raw("{$items}", scope, runtime) == [1, 2, 3]

    def test_returns_dict_for_dollar_ref(self, runtime, scope):
        scope["data"] = {"k": "v"}
        assert resolve_raw("$data", scope, runtime) == {"k": "v"}

    def test_falls_back_for_plain_string(self, runtime, scope):
        assert resolve_raw("hello", scope, runtime) == "hello"

    def test_falls_back_for_interpolated(self, runtime, scope):
        runtime.state.set("a", 1)
        assert resolve_raw("val={$a}", scope, runtime) == "val=1"

    def test_symbol_returns_object(self, runtime, scope):
        runtime.state.set("things", [9, 8])
        result = resolve_raw(Symbol(name="things", pos=None), scope, runtime)
        assert result == [9, 8]


class TestResolveHandler:
    def test_resolves_function_from_scope(self, runtime, scope):
        def handler():
            return "handled"
        scope["my_handler"] = handler
        result = resolve_handler("my_handler", scope, runtime)
        assert result is handler

    def test_resolves_function_from_namespace(self, runtime, scope):
        def handler():
            return "handled"
        runtime.namespace["my_handler"] = handler
        result = resolve_handler("my_handler", scope, runtime)
        assert result is handler

    def test_resolves_from_braces(self, runtime, scope):
        def handler():
            return "handled"
        scope["handler"] = handler
        result = resolve_handler("{handler}", scope, runtime)
        assert result is handler

    def test_returns_none_for_unknown(self, runtime, scope):
        result = resolve_handler("unknown", scope, runtime)
        assert result is None

    def test_returns_none_for_non_callable(self, runtime, scope):
        scope["not_fn"] = "string"
        result = resolve_handler("not_fn", scope, runtime)
        assert result is None

    def test_passes_through_callable(self, runtime, scope):
        def handler():
            pass
        result = resolve_handler(handler, scope, runtime)
        assert result is handler


class TestCollectRefs:
    def test_collects_simple_refs(self, runtime, scope):
        refs = collect_refs("Hello {$name}", scope, runtime)
        assert "name" in refs

    def test_collects_multiple_refs(self, runtime, scope):
        refs = collect_refs("{$a} and {$b}", scope, runtime)
        assert refs == {"a", "b"}

    def test_collects_nested_refs(self, runtime, scope):
        scope["outer"] = "{$inner}"
        refs = collect_refs("{$outer}", scope, runtime)
        assert refs == {"outer", "inner"}

    def test_no_refs_in_plain_string(self, runtime, scope):
        refs = collect_refs("plain text", scope, runtime)
        assert refs == set()
