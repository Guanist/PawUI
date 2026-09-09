"""Tests for the PawUI parser."""

import pytest

from pawui.errors import ParseError
from pawui.parser import parse


class TestParser:
    def test_simple_element(self):
        source = '<Window title="Test"/>'
        program = parse(source)
        assert len(program.elements) == 1
        assert program.elements[0].tag == "Window"
        assert program.elements[0].props["title"] == "Test"

    def test_element_with_children(self):
        source = '<Window><Text>Hello</Text></Window>'
        program = parse(source)
        assert len(program.elements) == 1
        window = program.elements[0]
        assert window.tag == "Window"
        assert len(window.children) == 1
        assert window.children[0].tag == "Text"
        assert window.children[0].props.get("__content__") == "Hello"

    def test_self_closing_element(self):
        source = '<Input placeholder="Name"/>'
        program = parse(source)
        assert len(program.elements) == 1
        assert program.elements[0].tag == "Input"
        assert program.elements[0].props["placeholder"] == "Name"

    def test_component_definition(self):
        source = '<Component name="Card"><Text>{$label}</Text></Component>'
        program = parse(source)
        assert len(program.elements) == 1
        comp = program.elements[0]
        assert comp.tag == "component"
        assert comp.name == "Card"
        assert len(comp.children) == 1

    def test_script_block(self):
        source = '<script>\ndef hello():\n    return "world"\n</script>'
        program = parse(source)
        assert program.script is not None
        assert 'def hello():' in program.script.source

    def test_comment(self):
        source = '<!-- This is a comment --><Window/>'
        program = parse(source)
        assert len(program.elements) == 1
        assert program.elements[0].tag == "Window"

    def test_boolean_attributes(self):
        source = '<Button disabled/>'
        program = parse(source)
        assert program.elements[0].props["disabled"] is True

    def test_unquoted_attributes(self):
        source = '<Window title=Test></Window>'
        program = parse(source)
        assert program.elements[0].props["title"] == "Test"

    def test_multiple_attributes(self):
        source = '<Window title="Test" width="400" height="300"/>'
        program = parse(source)
        props = program.elements[0].props
        assert props["title"] == "Test"
        assert props["width"] == "400"
        assert props["height"] == "300"

    def test_nested_elements(self):
        source = '<Column><Row><Text>A</Text><Text>B</Text></Row></Column>'
        program = parse(source)
        col = program.elements[0]
        assert col.tag == "Column"
        row = col.children[0]
        assert row.tag == "Row"
        assert len(row.children) == 2

    def test_parse_error_unclosed_tag(self):
        source = '<Window><Text>Hello</Window>'
        with pytest.raises(ParseError):
            parse(source)

    def test_parse_error_mismatched_tag(self):
        source = '<Window></Div>'
        with pytest.raises(ParseError):
            parse(source)

    def test_component_requires_name(self):
        source = '<Component><Text/></Component>'
        with pytest.raises(ParseError, match="requires a name"):
            parse(source)

    def test_template_syntax_in_props(self):
        source = '<Text>{$count}</Text>'
        program = parse(source)
        assert program.elements[0].props["__content__"] == "{$count}"

    def test_multiple_root_elements_allowed_in_parse(self):
        source = '<Text>A</Text><Text>B</Text>'
        program = parse(source)
        assert len(program.elements) == 2
