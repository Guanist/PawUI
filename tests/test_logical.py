"""Tests for <If> and <For> logical container components."""

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from pawui.runtime import Runtime


def descendants(widget: QWidget | None, cls):
    if widget is None:
        return []
    out = []
    for child in widget.findChildren(cls):
        out.append(child)
    return out


def label_texts(root):
    return [lbl.text() for lbl in descendants(root, QLabel)]


class TestIf:
    def test_if_true_renders_children(self, qapp):
        source = '''
        <Window>
            <If condition="{$show}">
                <Text>A</Text>
            </If>
        </Window>
        <script>
state.show = True
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["A"]
        rt.root.close()

    def test_if_false_renders_nothing(self, qapp):
        source = '''
        <Window>
            <If condition="{$show}">
                <Text>A</Text>
            </If>
        </Window>
        <script>
state.show = False
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == []
        rt.root.close()

    def test_if_with_plain_truthy(self, qapp):
        source = '''
        <Window>
            <If condition="yes">
                <Text>A</Text>
            </If>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["A"]
        rt.root.close()

    def test_if_no_blocks(self, qapp):
        source = '''
        <Window>
            <If condition="true"><Text>A</Text></If>
            <If condition="false"><Text>B</Text></If>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["A"]
        rt.root.close()


class TestFor:
    def test_for_iterates(self, qapp):
        source = '''
        <Window>
            <For each="item" in="{$items}">
                <Text>{$item}</Text>
            </For>
        </Window>
        <script>
state.items = ["x", "y", "z"]
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["x", "y", "z"]
        rt.root.close()

    def test_for_default_each(self, qapp):
        source = '''
        <Window>
            <For in="{$nums}">
                <Text>{$item}</Text>
            </For>
        </Window>
        <script>
state.nums = [1, 2]
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["1", "2"]
        rt.root.close()

    def test_for_attr_access(self, qapp):
        source = '''
        <Window>
            <For each="user" in="{$users}">
                <Text>{$user.name}</Text>
            </For>
        </Window>
        <script>
state.users = [{"name": "A"}, {"name": "B"}]
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["A", "B"]
        rt.root.close()

    def test_for_empty(self, qapp):
        source = '''
        <Window>
            <For in="{$items}">
                <Text>A</Text>
            </For>
        </Window>
        <script>
state.items = []
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == []
        rt.root.close()

    def test_nested_for(self, qapp):
        source = '''
        <Window>
            <For each="row" in="{$grid}">
                <For each="cell" in="{$row}">
                    <Text>{$cell}</Text>
                </For>
            </For>
        </Window>
        <script>
state.grid = [["a", "b"], ["c"]]
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["a", "b", "c"]
        rt.root.close()

    def test_if_inside_for(self, qapp):
        source = '''
        <Window>
            <For each="n" in="{$nums}">
                <If condition="{$n.keep}">
                    <Text>{$n.label}</Text>
                </If>
            </For>
        </Window>
        <script>
state.nums = [{"keep": True, "label": "y"}, {"keep": False, "label": "n"}]
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert label_texts(rt.root) == ["y"]
        rt.root.close()

    def test_unknown_logical_error(self, qapp):
        source = '''
        <Window>
            <While><Text>A</Text></While>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        with pytest.raises(Exception, match="unknown component"):
            rt._build_tree()
