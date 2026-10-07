"""DOM 层：脚本侧 query / on / append / remove / class / css。"""

from PySide6.QtWidgets import QPushButton

from pawui.runtime import Runtime

APP = """
<Style>
  .accent { color: #ff0000; }
</Style>
<Window width="360" height="260">
  <Column id="root-col" class="board">
    <Text id="title" class="title">hello</Text>
    <Text class="title">second</Text>
    <Button id="go">go</Button>
  </Column>
</Window>
"""


def _rt(src: str = APP, qapp=None) -> Runtime:
    rt = Runtime(src)
    rt._prepare()
    rt._build_tree()
    return rt


class TestQuery:
    def test_query_by_id(self, qapp):
        rt = _rt(qapp=qapp)
        assert rt.query("#title").text == "hello"
        rt.root.close()

    def test_query_by_class_and_tag(self, qapp):
        rt = _rt(qapp=qapp)
        assert len(rt.query_all(".title")) == 2
        assert rt.query("Button").tag == "Button"
        assert rt.query("Text").text == "hello"
        rt.root.close()

    def test_query_descendant(self, qapp):
        rt = _rt(qapp=qapp)
        assert [e.text for e in rt.query_all(".board Text")] == ["hello", "second"]
        assert rt.query(".board Button") is not None
        rt.root.close()

    def test_query_miss_returns_none(self, qapp):
        rt = _rt(qapp=qapp)
        assert rt.query("#nope") is None
        assert rt.query_all(".nope") == []
        rt.root.close()

    def test_element_tag_and_classes(self, qapp):
        rt = _rt(qapp=qapp)
        title = rt.query("#title")
        assert title.id == "title"
        assert title.classes == ["title"]
        assert title.tag == "Text"
        rt.root.close()


class TestContent:
    def test_text_read_write(self, qapp):
        rt = _rt(qapp=qapp)
        title = rt.query("#title")
        title.text = "changed"
        assert rt.query("#title").text == "changed"
        rt.root.close()

    def test_value_on_checkable(self, qapp):
        rt = _rt('<Window><Checkbox id="c" checked="false">x</Checkbox></Window>', qapp)
        box = rt.query("#c")
        box.value = True
        assert box.value is True
        rt.root.close()

    def test_class_add_remove_toggle(self, qapp):
        rt = _rt(qapp=qapp)
        title = rt.query("#title")
        title.add_class("accent")
        assert title.has_class("accent")
        assert "color: #ff0000" in rt.query("#title").widget.styleSheet()
        title.remove_class("accent")
        assert not title.has_class("accent")
        title.toggle_class("accent")
        assert title.has_class("accent")
        rt.root.close()

    def test_css_injects_only_this_widget(self, qapp):
        rt = _rt(qapp=qapp)
        rt.query("#title").css("fg: #00ff00;")
        assert "color: #00ff00" in rt.query("#title").widget.styleSheet()
        assert "color: #00ff00" not in rt.query_all(".title")[1].widget.styleSheet()
        rt.root.close()

    def test_attr_read_write(self, qapp):
        rt = _rt(qapp=qapp)
        title = rt.query("#title")
        title.attr("pw-state", "busy")
        assert title.attr("pw-state") == "busy"
        rt.root.close()


class TestStructure:
    def test_append_fragment(self, qapp):
        rt = _rt(qapp=qapp)
        added = rt.append("<Text class='title'>third</Text>", "#root-col")
        assert len(added) == 1
        assert [e.text for e in rt.query_all(".title")] == ["hello", "second", "third"]
        rt.root.close()

    def test_append_before_trailing_stretch(self, qapp):
        rt = _rt(qapp=qapp)
        rt.append("<Button id='extra'>x</Button>", "#root-col")
        children = [c.id for c in rt.query("#root-col").children()]
        assert children[-1] == "extra", children
        rt.root.close()

    def test_prepend_fragment(self, qapp):
        rt = _rt(qapp=qapp)
        rt.query("#root-col").prepend("<Text class='title'>zero</Text>")
        assert [e.text for e in rt.query_all(".title")] == ["zero", "hello", "second"]
        rt.root.close()

    def test_append_accepts_documented_argument_order(self, qapp):
        """文档一直写的是 ``app.append(target, markup)``，必须也能用。

        实现签名是 ``append(markup, target)``，两种顺序都要认 —— 否则照文档写的
        调用会**静默返回空列表**（不插元素、不报错），用户根本查不出原因。
        """
        rt = _rt(qapp=qapp)
        added = rt.append("#root-col", "<Text class='title'>third</Text>")
        assert len(added) == 1
        assert [e.text for e in rt.query_all(".title")] == ["hello", "second", "third"]
        rt.root.close()

    def test_append_accepts_keyword_arguments(self, qapp):
        rt = _rt(qapp=qapp)
        added = rt.append(markup="<Text class='title'>third</Text>", target="#root-col")
        assert len(added) == 1
        assert [e.text for e in rt.query_all(".title")] == ["hello", "second", "third"]
        rt.root.close()

    def test_prepend_accepts_documented_argument_order(self, qapp):
        rt = _rt(qapp=qapp)
        rt.append("#root-col", "<Text class='title'>zero</Text>", prepend=True)
        assert [e.text for e in rt.query_all(".title")] == ["zero", "hello", "second"]
        rt.root.close()

    def test_append_documented_order_lands_before_trailing_stretch(self, qapp):
        """文档顺序也要插在尾簧之前（和实现顺序行为一致）。"""
        rt = _rt(qapp=qapp)
        rt.append("#root-col", "<Button id='extra'>x</Button>")
        children = [c.id for c in rt.query("#root-col").children()]
        assert children[-1] == "extra", children
        rt.root.close()

    def test_remove_element(self, qapp):
        rt = _rt(qapp=qapp)
        assert rt.remove("#title") is True
        assert rt.query("#title") is None
        assert len(rt.query_all(".title")) == 1
        rt.root.close()

    def test_clear_children(self, qapp):
        rt = _rt(qapp=qapp)
        rt.query("#root-col").clear()
        assert rt.query("#root-col").children() == []
        rt.root.close()

    def test_root_cannot_be_removed(self, qapp):
        rt = _rt(qapp=qapp)
        assert rt.remove_widget(rt.root) is False
        rt.root.close()

    def test_children_helper(self, qapp):
        rt = _rt(qapp=qapp)
        kids = rt.query("#root-col").children()
        assert [k.id for k in kids] == ["title", "", "go"]
        rt.root.close()


class TestEvents:
    def test_click_handler(self, qapp):
        seen = []
        rt = _rt(qapp=qapp)
        rt.query("#go").on("click", lambda e: seen.append(e.type))
        rt.root.findChild(QPushButton).click()
        assert seen == ["click"]
        rt.root.close()

    def test_change_handler_gets_value(self, qapp):
        seen = []
        rt = _rt('<Window><Input id="name"/></Window>', qapp)
        rt.query("#name").on("change", lambda e: seen.append(e.value))
        rt.query("#name").widget.setText("abc")
        assert seen == ["abc"]
        rt.root.close()

    def test_event_bubbles_to_ancestor(self, qapp):
        seen = []
        rt = _rt(qapp=qapp)
        record = lambda e: seen.append(e.target.id)  # noqa: E731
        assert rt.bind_event_selector(".board", "click", record) == 1
        rt._emit(rt.query("#title").widget, "click")
        assert seen == ["title"], "子控件的事件要冒到祖先身上"
        rt.root.close()

    def test_event_target_is_paw_element(self, qapp):
        seen = []
        rt = _rt(qapp=qapp)
        rt.query("#go").on("hover", lambda e: seen.append(e.target.id))
        rt._emit(rt.query("#go").widget, "hover")
        assert seen == ["go"]
        rt.root.close()

    def test_unknown_event_rejected(self, qapp):
        import pytest

        from pawui.errors import ScriptError
        rt = _rt(qapp=qapp)
        with pytest.raises(ScriptError):
            rt.query("#go").on("teleport", lambda e: None)
        rt.root.close()

    def test_ready_runs_after_build(self, qapp):
        rt = Runtime("""
        <Script>
app.note = None
def mark():
    app.note = app.query("#title").text
ready(mark)
        </Script>
        <Window><Text id="title">loaded</Text></Window>
        """)
        rt._prepare()
        rt._build_tree()
        assert rt.note == "loaded"
        rt.root.close()

    def test_on_after_ready(self, qapp):
        rt = Runtime("""
        <Script>
seen = []
def wire():
    app.on(".row", "click", lambda e: seen.append(e.target.text))
ready(wire)
        </Script>
        <Window><Column class="row"><Button id="b">press</Button></Column></Window>
        """)
        rt._prepare()
        rt._build_tree()
        rt.root.findChild(QPushButton).click()
        assert rt.namespace["seen"] == ["press"]
        rt.root.close()
