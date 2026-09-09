"""Tests for the PawUI nodes module."""

from pawui.errors import Position
from pawui.nodes import ComponentDef, Element, Program, ScriptBlock, Symbol


class TestNodes:
    def test_element_creation(self):
        pos = Position(1, 1)
        el = Element(
            tag="Window",
            props={"title": "Test"},
            children=[],
            pos=pos,
            is_block=True
        )
        assert el.tag == "Window"
        assert el.props["title"] == "Test"
        assert el.pos == pos
        assert el.is_block is True

    def test_element_defaults(self):
        el = Element(tag="Text")
        assert el.props == {}
        assert el.children == []
        assert el.pos is None
        assert el.name is None
        assert el.is_block is False

    def test_script_block(self):
        pos = Position(10, 1)
        script = ScriptBlock(source="print('hello')", pos=pos)
        assert script.source == "print('hello')"
        assert script.pos == pos

    def test_program(self):
        el = Element(tag="Window")
        script = ScriptBlock(source="pass")
        program = Program(elements=[el], script=script)
        assert len(program.elements) == 1
        assert program.script is script

    def test_program_defaults(self):
        program = Program()
        assert program.elements == []
        assert program.script is None

    def test_component_def(self):
        pos = Position(5, 1)
        root = Element(tag="Column", children=[Element(tag="Text", props={"__content__": "Hello"})])
        comp_def = ComponentDef(name="Card", root=root, pos=pos)
        assert comp_def.name == "Card"
        assert comp_def.root == root
        assert comp_def.pos == pos

    def test_symbol(self):
        pos = Position(3, 10)
        sym = Symbol(name="handler", pos=pos)
        assert sym.name == "handler"
        assert sym.pos == pos
