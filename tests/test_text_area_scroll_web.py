"""Tests for TextArea, Scroll and Web components plus invoke_async."""

import time

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea

from pawui.runtime import Runtime


def _find_plain(root):
    return root.findChild(QPlainTextEdit)


class TestTextArea:
    def test_initial_value_and_placeholder(self, qapp):
        source = '<Window><TextArea value="hello" placeholder="Type..."/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_plain(rt.root)
        assert edit.toPlainText() == "hello"
        assert edit.placeholderText() == "Type..."
        rt.root.close()

    def test_on_change_fires(self, qapp):
        calls = []

        src = '''<Window><TextArea on_change="log"/></Window>
        <script>
def log(text):
    app.handlers.append(text)
        </script>'''
        rt = Runtime(source=src)
        rt.handlers = calls
        rt._prepare()
        rt._build_tree()
        edit = _find_plain(rt.root)
        edit.setPlainText("typed")
        assert calls, "expected at least one on_change callback"
        assert calls[-1] == "typed"
        rt.root.close()

    def test_bind_pushes_and_readonly(self, qapp):
        source = '''<Window><TextArea bind="body" value="{$body}" readonly="true"/></Window>
        <script>
state.body = "initial"
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_plain(rt.root)
        assert edit.toPlainText() == "initial"
        assert edit.isReadOnly() is True
        edit.setPlainText("changed")
        assert rt.state.get("body") == "changed"
        rt.root.close()

    def test_value_template_updates(self, qapp):
        source = '''<Window><TextArea value="{$body}"/></Window>
        <script>
state.body = "a"
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        edit = _find_plain(rt.root)
        assert edit.toPlainText() == "a"
        rt.state.set("body", "b")
        assert edit.toPlainText() == "b"
        rt.root.close()


class TestScroll:
    def test_children_go_inside_scroll(self, qapp):
        source = '''
        <Window>
            <Scroll height="200">
                <Button>Top</Button>
                <Text>Inside scroll</Text>
            </Scroll>
        </Window>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        scroll = rt.root.findChild(QScrollArea)
        assert scroll is not None
        labels = scroll.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert texts == ["Inside scroll"]
        rt.root.close()


class TestWeb:
    def test_html_loads(self, qapp):
        source = '<Window><Web height="200" html="<b>hi</b>"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        view = rt.root.findChild(__import__("PySide6.QtWebEngineWidgets", fromlist=["QWebEngineView"]).QWebEngineView)
        assert view is not None
        rt.root.close()


class TestInvokeAsync:
    def test_invoke_async_done_callback(self, qapp):
        src = '''<script>
def slow():
    import time
    time.sleep(0.02)
    return 42
        </script>'''
        rt = Runtime(source=f"<Window><Text>wait</Text></Window>\n{src}")
        rt._prepare()
        rt._build_tree()
        completed = []

        def done(result, error):
            completed.append((result, error))

        rt.invoke_async(rt.namespace.get("slow"), done=done)
        deadline = time.monotonic() + 2.0
        while not completed and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
        assert completed, "done() was never called"
        assert completed[0] == (42, None)
        rt.root.close()

    def test_invoke_async_reports_error(self, qapp):
        rt = Runtime(source='<Window><Text>wait</Text></Window>')
        rt._prepare()
        rt._build_tree()
        completed = []

        def boom():
            raise ValueError("nope")

        def done(result, error):
            completed.append((result, error))

        rt.invoke_async(boom, done=done)
        deadline = time.monotonic() + 2.0
        while not completed and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
        assert completed
        assert completed[0][0] is None
        assert isinstance(completed[0][1], ValueError)
        rt.root.close()
