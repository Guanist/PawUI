"""Tests for two-way binding (bind=) and default props (<Prop>)."""

from PySide6.QtWidgets import QLineEdit, QProgressBar, QSlider

from pawui.components import ToggleSwitch
from pawui.runtime import Runtime


def _find_line_edit(root):
    return root.findChild(QLineEdit)


def _find_slider(root):
    return root.findChild(QSlider)


class TestInputBind:
    def test_bind_pushes_to_state(self, qapp):
        source = '''<Window><Input bind="name"/></Window>
        <script>
state.name = "start"
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_line_edit(rt.root)
        edit.setText("typed")
        assert rt.state.get("name") == "typed"
        rt.root.close()

    def test_bind_brace_syntax(self, qapp):
        source = '<Window><Input bind="{$name}"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_line_edit(rt.root)
        edit.setText("hello")
        assert rt.state.get("name") == "hello"
        rt.root.close()

    def test_bind_no_loop_on_state_change(self, qapp):
        source = '''<Window><Input bind="text" value="{$text}"/></Window>
        <script>
state.text = "a"
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_line_edit(rt.root)
        assert edit.text() == "a"
        rt.state.set("text", "b")
        assert edit.text() == "b"
        assert rt.state.get("text") == "b"
        rt.root.close()


class TestCheckboxBind:
    def test_bind_pushes_checked(self, qapp):
        source = '''<Window><Checkbox bind="flag">Go</Checkbox></Window>
        <script>
state.flag = False
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        toggle = rt.root.findChildren(__import__("pawui.components", fromlist=["ToggleSwitch"]).ToggleSwitch)[0]
        toggle.setChecked(True)
        assert rt.state.get("flag") is True
        rt.root.close()


class TestTemplateBindingValueType:
    """``value="{$x}"`` 这类模板绑定必须把**原始值**交给控件，不能给字符串。

    旧实现走 ``resolve_template()``，拿到的是字符串；``Checkbox`` 里写
    ``setChecked(bool(v))``，于是 ``bool("False") == True`` —— 用户点掉开关后
    绑定立刻把它按回打开，开关、state、界面三者互相矛盾，而且再也切不回去。
    """

    def test_checkbox_syncs_both_ways(self, qapp):
        source = '''<Window>
            <Checkbox checked="{$flag}" on_change="on_change">light</Checkbox>
        </Window>
        <script>
def on_change(checked):
    state.flag = checked
        </script>'''
        rt = Runtime(source)
        rt.state.set("flag", True)
        rt._prepare()
        rt._build_tree()
        toggle = rt.root.findChild(ToggleSwitch)
        assert toggle.isChecked() is True

        rt.state.set("flag", False)
        assert toggle.isChecked() is False, "state 变 False 后开关必须跟着关掉"

        rt.state.set("flag", True)
        assert toggle.isChecked() is True
        rt.root.close()

    def test_numeric_template_binding_keeps_number(self, qapp):
        source = '''<Window>
            <Slider value="{$level}"/><Progress value="{$level}"/>
        </Window>'''
        rt = Runtime(source)
        rt.state.set("level", 40)
        rt._prepare()
        rt._build_tree()

        rt.state.set("level", 70)
        assert rt.root.findChild(QSlider).value() == 70
        assert rt.root.findChild(QProgressBar).value() == 70
        rt.root.close()


class TestSliderBind:
    def test_bind_pushes_value(self, qapp):
        source = '''<Window><Slider min="0" max="10" bind="vol"/></Window>
        <script>
state.vol = 3
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        slider = _find_slider(rt.root)
        slider.setValue(9)
        assert rt.state.get("vol") == 9
        rt.root.close()

    def test_value_template_updates(self, qapp):
        source = '''<Window><Slider min="0" max="10" value="{$vol}"/></Window>
        <script>
state.vol = 4
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        slider = _find_slider(rt.root)
        assert slider.value() == 4
        rt.state.set("vol", 6)
        assert slider.value() == 6
        rt.root.close()


class TestDefaultProps:
    def test_default_used_when_missing(self, qapp):
        source = '''
        <Window>
            <Card/>
        </Window>
        <Component name="Card">
            <Prop name="label" default="Default label"/>
            <Text>{$label}</Text>
        </Component>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        labels = rt.root.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
        assert labels[0].text() == "Default label"
        rt.root.close()

    def test_explicit_overrides_default(self, qapp):
        source = '''
        <Window>
            <Card label="Custom"/>
        </Window>
        <Component name="Card">
            <Prop name="label" default="Default label"/>
            <Text>{$label}</Text>
        </Component>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        labels = rt.root.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
        assert labels[0].text() == "Custom"
        rt.root.close()

    def test_default_with_template(self, qapp):
        source = '''
        <Window>
            <Card/>
        </Window>
        <Component name="Card">
            <Prop name="value" default="{$count}"/>
            <Text>{$value}</Text>
        </Component>
        <script>
state.count = 7
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        labels = rt.root.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
        assert labels[0].text() == "7"
        rt.root.close()
