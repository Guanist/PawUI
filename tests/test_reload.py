"""Tests for hot reload API (Runtime.reload)."""

from PySide6.QtWidgets import QLabel

from pawui.runtime import Runtime


def labels(root):
    return [lbl.text() for lbl in root.findChildren(QLabel)]


class TestReload:
    def test_reload_updates_content(self, qapp):
        source = '<Window><Text>alpha</Text></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert labels(rt.root) == ["alpha"]

        rt.reload('<Window><Text>beta</Text></Window>')
        assert labels(rt.root) == ["beta"]
        rt.root.close()

    def test_reload_keeps_state(self, qapp):
        source = '''<Window><Text>{$msg}</Text></Window>
        <script>
state.msg = "hello"
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.state.get("msg") == "hello"
        assert labels(rt.root) == ["hello"]

        rt.reload('<Window><Text>{$msg}!</Text></Window>')
        assert labels(rt.root) == ["hello!"]
        rt.root.close()

    def test_reload_registers_new_components(self, qapp):
        source = '''
        <Window><Card label="one"/></Window>
        <Component name="Card">
            <Text>{$label}</Text>
        </Component>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert labels(rt.root) == ["one"]

        rt.reload('''
        <Window><Card label="hi"/></Window>
        <Component name="Card">
            <Text color="accent">{$label}</Text>
        </Component>''')
        assert labels(rt.root) == ["hi"]
        rt.root.close()

    def test_reload_handles_script_added_state(self, qapp):
        source = '<Window><Text>-</Text></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()

        rt.reload('''<Window><Text>{$n}</Text></Window>
        <script>
state.n = 42
        </script>''')
        assert labels(rt.root) == ["42"]
        rt.root.close()
