"""Tests for the PawUI components module."""

import pytest

from pawui.components import (
    BUILTINS,
    Button,
    Checkbox,
    Column,
    Divider,
    Input,
    Row,
    Spacer,
    Text,
    Window,
)
from pawui.nodes import Element
from pawui.theme import Theme


class MockRuntime:
    def __init__(self):
        self.theme = Theme.dark()
        self.state = None

    def invoke(self, fn, *args):
        if callable(fn):
            return fn(*args)
        return None

    def queue_animation(self, *args):
        pass


@pytest.fixture
def runtime():
    return MockRuntime()


@pytest.fixture
def scope():
    return {}


class TestComponents:
    def test_window_build(self, runtime, scope):
        element = Element(tag="Window", props={"title": "Test", "width": "400", "height": "300"})
        comp = Window(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        # Title is set by runtime on root widget, not by component
        assert comp.opt_str("title") == "Test"

    def test_column_build(self, runtime, scope):
        element = Element(tag="Column", props={"padding": "20", "spacing": "10"})
        comp = Column(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert comp.layout is not None

    def test_row_build(self, runtime, scope):
        element = Element(tag="Row", props={"padding": "20", "spacing": "10"})
        comp = Row(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert comp.layout is not None

    def test_text_build(self, runtime, scope):
        element = Element(tag="Text", props={"__content__": "Hello", "size": "14", "color": "#ff0000"})
        comp = Text(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert widget.text() == "Hello"

    def test_button_build(self, runtime, scope):
        element = Element(tag="Button", props={"__content__": "Click", "bg": "#00ff00"})
        comp = Button(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert widget.text() == "Click"

    def test_input_build(self, runtime, scope):
        element = Element(tag="Input", props={"placeholder": "Enter text", "value": "initial"})
        comp = Input(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert widget.placeholderText() == "Enter text"
        assert widget.text() == "initial"

    def test_checkbox_build(self, runtime, scope):
        element = Element(tag="Checkbox", props={"checked": "true", "__content__": "Check me"})
        comp = Checkbox(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert comp._toggle.isChecked() is True

    def test_divider_build(self, runtime, scope):
        element = Element(tag="Divider", props={"thickness": "2", "color": "#ff0000"})
        comp = Divider(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None

    def test_spacer_build(self, runtime, scope):
        element = Element(tag="Spacer", props={"width": "10", "height": "20"})
        comp = Spacer(runtime, None, element, scope)
        widget = comp.build()
        assert widget is not None
        assert widget.width() == 10
        assert widget.height() == 20

    def test_builtins_registry(self):
        assert "Window" in BUILTINS
        assert "Column" in BUILTINS
        assert "Row" in BUILTINS
        assert "Text" in BUILTINS
        assert "Button" in BUILTINS
        assert "Input" in BUILTINS
        assert "Checkbox" in BUILTINS
        assert "Divider" in BUILTINS
        assert "Spacer" in BUILTINS

    def test_opt_size_priority(self, runtime, scope):
        # size takes priority over font_size
        element = Element(tag="Text", props={"size": "20", "font_size": "10", "__content__": "Test"})
        comp = Text(runtime, None, element, scope)
        size = comp.opt_size()
        assert size == 20

    def test_opt_bool_various(self, runtime, scope):
        element = Element(tag="Test", props={})
        comp = Text(runtime, None, element, scope)

        # Test string true values
        element.props["bool_str"] = "true"
        assert comp.opt_bool("bool_str") is True

        element.props["bool_str"] = "1"
        assert comp.opt_bool("bool_str") is True

        element.props["bool_str"] = "yes"
        assert comp.opt_bool("bool_str") is True

        element.props["bool_str"] = "on"
        assert comp.opt_bool("bool_str") is True

        element.props["bool_str"] = "false"
        assert comp.opt_bool("bool_str") is False

        # Test actual boolean
        element.props["bool_actual"] = True
        assert comp.opt_bool("bool_actual") is True

    def test_padding_parsing(self, runtime, scope):
        element = Element(tag="Test", props={})
        comp = Text(runtime, None, element, scope)

        # Single value
        element.props["padding"] = "10"
        assert comp.padding() == (10, 10, 10, 10)

        # Two values (vertical, horizontal)
        element.props["padding"] = (10, 20)
        assert comp.padding() == (20, 10, 20, 10)

        # Four values
        element.props["padding"] = (1, 2, 3, 4)
        # CSS 简写顺序是「上 / 右 / 下 / 左」，返回值是 Qt 的 (左, 上, 右, 下)
        assert comp.padding() == (4, 1, 2, 3)
