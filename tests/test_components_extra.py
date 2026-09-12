"""Tests for Slider / Progress / Tabs / Image / Tooltip components."""

import pytest
from PySide6.QtWidgets import QLabel, QProgressBar, QSlider, QTabWidget

from pawui.runtime import Runtime


class TestSlider:
    def test_slider_basic(self, qapp):
        source = '<Window><Slider min="0" max="100" value="40"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        slider = rt.root.findChild(QSlider)
        assert slider is not None
        assert slider.minimum() == 0
        assert slider.maximum() == 100
        assert slider.value() == 40
        rt.root.close()

    def test_slider_on_change(self, qapp):
        source = '''<Window><Slider min="0" max="10" on_change="on_slide"/></Window>
        <script>
def on_slide(v):
    state.last = v
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        slider = rt.root.findChild(QSlider)
        slider.setValue(7)
        assert rt.state.get("last") == 7
        rt.root.close()


class TestProgress:
    def test_progress_basic(self, qapp):
        source = '<Window><Progress value="60" max="100"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        bar = rt.root.findChild(QProgressBar)
        assert bar is not None
        assert bar.value() == 60
        rt.root.close()

    def test_progress_binding(self, qapp):
        source = '''<Window><Progress value="{$pct}" max="100"/></Window>
        <script>
state.pct = 30
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        bar = rt.root.findChild(QProgressBar)
        assert bar.value() == 30
        rt.state.set("pct", 80)
        assert bar.value() == 80
        rt.root.close()


class TestTabs:
    def test_tabs_two_pages(self, qapp):
        source = '''
        <Window>
            <Tabs>
                <Tab label="One"><Text>A</Text></Tab>
                <Tab label="Two"><Text>B</Text></Tab>
            </Tabs>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        tabs = rt.root.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 2
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert labels == ["One", "Two"]
        rt.root.close()


class TestImage:
    def test_image_missing_raises(self, qapp):
        source = '<Window><Image src="definitely_missing_file.png"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        with pytest.raises(Exception, match="image not found"):
            rt._build_tree()


class TestTooltip:
    def test_tooltip_on_child(self, qapp):
        source = '''
        <Window>
            <Tooltip text="Hi there">
                <Text>Hover me</Text>
            </Tooltip>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        labels = rt.root.findChildren(QLabel)
        assert labels
        assert labels[0].toolTip() == "Hi there"
        rt.root.close()


    def test_select_bind_and_items_update(self, qapp):
        from PySide6.QtWidgets import QComboBox
        rt = Runtime('<Window><Select items="{$options}" bind="choice"/></Window>')
        rt.state.set("options", ["a", "b"])
        rt.state.set("choice", "a")
        rt._prepare()
        rt._build_tree()
        combo = rt.root.findChild(QComboBox)
        assert combo.count() == 2
        combo.setCurrentText("b")
        assert rt.state.get("choice") == "b"
        rt.state.set("options", ["b", "c"])
        assert combo.count() == 2
        assert combo.itemText(0) == "b"
        rt.root.close()
