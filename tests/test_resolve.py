"""Tests for the PawUI resolver."""

import pytest

from pawui.nodes import Symbol
from pawui.resolve import (
    collect_refs,
    is_template,
    resolve_color,
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

    def test_plain_string_keeps_theme_names_literal(self, runtime, scope):
        """裸字符串不再被当成主题令牌。

        旧行为：``resolve_prop_value("accent")`` 返回 ``#0071e3``，于是
        ``<Badge text="text"/>`` 显示 ``#1d1d1f``、``text="dark"`` 显示
        ``<bound method Theme.dark of ...>``。主题令牌只对颜色属性生效，
        见 TestResolveColor。
        """
        assert resolve_prop_value("accent", scope, runtime) == "accent"
        assert resolve_prop_value("text", scope, runtime) == "text"
        assert resolve_prop_value("radius", scope, runtime) == "radius"
        assert resolve_prop_value("dark", scope, runtime) == "dark"


class TestResolveColor:
    """颜色属性专用：裸字符串可以是主题令牌名或自定义色名。"""

    def test_resolves_theme_color_by_name(self, runtime, scope):
        assert resolve_color("accent", scope, runtime) == runtime.theme.accent
        assert resolve_color("surface", scope, runtime) == runtime.theme.surface
        assert resolve_color("danger", scope, runtime) == runtime.theme.danger

    def test_resolves_custom_color_by_name(self, runtime, scope):
        runtime.theme.custom["brand"] = "#22d3ee"
        assert resolve_color("brand", scope, runtime) == "#22d3ee"

    def test_leaves_hex_untouched(self, runtime, scope):
        assert resolve_color("#ff0000", scope, runtime) == "#ff0000"

    def test_non_color_theme_fields_are_not_colors(self, runtime, scope):
        """radius / spacing / 方法名都不是颜色，不能被替换。"""
        assert resolve_color("radius", scope, runtime) == "radius"
        assert resolve_color("padding", scope, runtime) == "padding"
        assert resolve_color("dark", scope, runtime) == "dark"
        assert resolve_color("qss", scope, runtime) == "qss"

    def test_still_resolves_templates(self, runtime, scope):
        runtime.state.set("mine", "#123456")
        assert resolve_color("{$mine}", scope, runtime) == "#123456"

    def test_template_result_is_treated_as_a_token(self, runtime, scope):
        """``{$token}`` 解析出 "accent" 时要继续查令牌表，不能停在裸字符串。

        回归：``<Column bg="{$token}"/>``（token="accent"）以前会拿到字符串
        "accent"，Qt 把它当非法颜色静默丢弃 —— 界面没上色，只留一条
        "unknown color 'accent'" 的警告。
        """
        runtime.state.set("token", "accent")
        assert resolve_color("{$token}", scope, runtime) == runtime.theme.accent

    def test_template_result_can_be_a_custom_color(self, runtime, scope):
        runtime.theme.custom["brand"] = "#22d3ee"
        runtime.state.set("token", "brand")
        assert resolve_color("{$token}", scope, runtime) == "#22d3ee"

    def test_template_result_is_not_a_token_keeps_value(self, runtime, scope):
        """解析结果不是令牌（普通颜色/文本）时不能被乱改。"""
        runtime.state.set("mine", "#123456")
        assert resolve_color("{$mine}", scope, runtime) == "#123456"
        runtime.state.set("mine", "hello")
        assert resolve_color("{$mine}", scope, runtime) == "hello"


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
