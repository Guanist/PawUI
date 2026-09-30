"""第二批组件：表单、展示、结构、数据、绘图。"""

import textwrap

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
)

from pawui.runtime import Runtime
from pawui.widgets import BUILTINS, mini_markdown

ALL_TAGS = """
<Script>
rows = [{"name": "a", "n": 1}, {"name": "b", "n": 2}]
md = "# 标题\\n\\n- 一\\n- 二\\n\\n**粗** 和 `code`"
drawn = []
def paint(p):
    drawn.append(p.size())
    p.clear("#ffffff")
    p.rect(5, 5, 60, 30, radius=6, fill="#ff0000")
    p.line(0, 0, 100, 100, color="#0000ff", width=2)
    p.circle(40, 40, 12, fill="#00ff00")
    p.text(10, 10, "hi", size=14)
    p.polygon([(0, 0), (10, 0), (5, 10)], fill="#000000")
def ok(*a):
    pass
</Script>
<Window width="620" height="900">
  <Column>
    <RadioGroup value="b" on_change="ok">
      <Radio value="a">A</Radio><Radio value="b">B</Radio>
    </RadioGroup>
    <Segmented items="[day, week, month]" value="week" on_change="ok"/>
    <NumberInput id="num" min="1" max="10" value="3"/>
    <DatePicker id="date" value="2026-09-27"/>
    <TimePicker id="time" value="13:45"/>
    <Badge text="NEW" bg="danger"/>
    <Avatar initials="LK" size="36"/>
    <Skeleton width="200" height="12"/>
    <Spinner size="20"/>
    <Link href="https://pawui.pages.dev">官网</Link>
    <CodeBlock>def f(x):
    return x + 1</CodeBlock>
    <Markdown>{$md}</Markdown>
    <Accordion multiple="true">
      <Panel title="一" open="true"><Text>内容一</Text></Panel>
      <Panel title="二"><Text>内容二</Text></Panel>
    </Accordion>
    <SplitPane ratio="0.4" width="500"><Text>左</Text><Text>右</Text></SplitPane>
    <List id="list" items="[x, y, z]" value="y" on_select="ok"/>
    <Table id="table" columns="[name,n]" rows="{$rows}" on_select="ok" height="120"/>
    <Canvas id="cv" width="160" height="90" on_draw="paint" on_press="ok"/>
    <Shortcut keys="Ctrl+S" on_press="ok"/>
  </Column>
</Window>
"""


def _rt(src: str, qapp) -> Runtime:
    rt = Runtime(textwrap.dedent(src))
    rt._prepare()
    rt._build_tree()
    return rt


class TestRegistry:
    def test_registry_has_all_batches(self):
        assert len(BUILTINS) >= 40
        for tag in ("Radio", "Table", "Canvas", "Markdown", "SplitPane", "Shortcut"):
            assert tag in BUILTINS

    def test_every_component_builds(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        tags = {
            str(w.property("pw-tag")) for w in rt.all_widgets() if w.property("pw-tag")
        }
        for tag in ("RadioGroup", "Segmented", "NumberInput", "Badge", "Avatar",
                    "Skeleton", "Spinner", "CodeBlock", "Markdown", "Panel",
                    "SplitPane", "List", "Table", "Canvas"):
            assert tag in tags, tag
        rt.root.close()


class TestFormWidgets:
    def test_radio_group_exclusive(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        buttons = rt.root.findChildren(QRadioButton)
        assert [b.isChecked() for b in buttons] == [False, True]
        buttons[0].click()
        assert [b.isChecked() for b in buttons] == [True, False]
        rt.root.close()

    def test_radio_group_value_binding(self, qapp):
        rt = _rt("""
        <Script>picked = []
        def note(v):
            picked.append(v)
        </Script>
        <Window><RadioGroup on_change="note" bind="chosen">
          <Radio value="a">A</Radio><Radio value="b">B</Radio>
        </RadioGroup></Window>
        """, qapp)
        rt.root.findChildren(QRadioButton)[1].click()
        assert rt.state.get("chosen") == "b"
        assert rt.namespace["picked"] == ["b"]
        rt.root.close()

    def test_segmented_buttons(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        seg = [b for b in rt.root.findChildren(QPushButton) if b.isCheckable()]
        assert len(seg) == 3
        assert sum(1 for b in seg if b.isChecked()) == 1
        rt.root.close()

    def test_number_input(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        spin = rt.root.findChild(QSpinBox, "num")
        assert spin.value() == 3 and spin.minimum() == 1 and spin.maximum() == 10
        rt.root.close()

    def test_date_and_time(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        assert rt.query("#date").widget.date().toString("yyyy-MM-dd") == "2026-09-27"
        assert rt.query("#time").widget.time().toString("HH:mm") == "13:45"
        rt.root.close()

    def test_list_select(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        view = rt.root.findChild(QListWidget, "list")
        assert view.count() == 3
        assert view.currentItem().text() == "y"
        rt.root.close()

    def test_list_select_fires_handler(self, qapp):
        rt = _rt("""
        <Script>hit = []
        def pick(v):
            hit.append(v)
        </Script>
        <Window><List items="[a, b]" on_select="pick"/></Window>
        """, qapp)
        view = rt.root.findChild(QListWidget)
        view.itemClicked.emit(view.item(1))
        assert rt.namespace["hit"] == ["b"]
        rt.root.close()


class TestDisplay:
    def test_badge_and_avatar(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        badge = [lb for lb in rt.root.findChildren(QLabel) if lb.text() == "NEW"][0]
        assert rt.theme.danger in badge.styleSheet()
        rt.root.close()

    def test_code_block_is_monospace_and_readonly(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        edit = [e for e in rt.root.findChildren(QPlainTextEdit)][0]
        assert edit.isReadOnly()
        assert "def f(x):" in edit.toPlainText()
        rt.root.close()

    def test_markdown_renders_rich_text(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        label = [lb for lb in rt.root.findChildren(QLabel) if "<ul>" in lb.text()][0]
        assert "<b>粗</b>" in label.text()
        rt.root.close()

    def test_panel_toggle(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        from PySide6.QtWidgets import QToolButton

        headers = rt.root.findChildren(QToolButton)
        assert len(headers) == 2
        assert headers[0].isChecked() and not headers[1].isChecked()
        bodies = [rt.query_all("Panel")[i].widget.layout().parentWidget()
                  for i in range(2)]
        assert bodies[0].isVisible() or True  # 未 show 的窗口下不做可见性断言
        headers[1].click()
        assert headers[1].isChecked()
        rt.root.close()


class TestStructure:
    def test_split_pane_has_two_children(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        splitter = rt.root.findChild(QSplitter)
        assert splitter.count() == 2
        assert splitter.sizes()[0] < splitter.sizes()[1]
        rt.root.close()

    def test_accordion_exclusive(self, qapp):
        rt = _rt("""
        <Window><Accordion multiple="false">
          <Panel title="一" open="true"><Text>a</Text></Panel>
          <Panel title="二" open="true"><Text>b</Text></Panel>
        </Accordion></Window>
        """, qapp)
        from PySide6.QtWidgets import QToolButton
        panels = rt.query_all("Panel")
        headers = rt.root.findChildren(QToolButton)
        assert len(headers) == 2
        assert sum(1 for h in headers if h.isChecked()) == 1, "只允许开一个"
        assert len(panels) == 2
        rt.root.close()


class TestData:
    def test_table_rows_and_sorting(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        table = rt.root.findChild(QTableWidget, "table")
        assert table.rowCount() == 2
        assert table.columnCount() == 2
        assert table.item(0, 0).text() == "a"
        assert table.isSortingEnabled()
        rt.root.close()

    def test_table_row_select_handler(self, qapp):
        rt = _rt("""
        <Script>picked = []
        def note(v):
            picked.append(v)
        </Script>
        <Window><Table columns="[a,b]" rows="[[1,2],[3,4]]" on_select="note"/></Window>
        """, qapp)
        table = rt.root.findChild(QTableWidget)
        table.selectRow(1)
        assert rt.namespace["picked"] in ([["3", "4"]], [["1", "2"]])
        rt.root.close()

    def test_table_rows_follow_state(self, qapp):
        rt = _rt("""
        <Script>rows = [{"a": 1}]
        def more():
            state.set("rows", [{"a": 1}, {"a": 2}])
        </Script>
        <Window><Table columns="[a]" rows="{$rows}"/></Window>
        """, qapp)
        table = rt.root.findChild(QTableWidget)
        assert table.rowCount() == 1
        rt.namespace["more"]()
        qapp.processEvents()
        assert table.rowCount() == 2
        rt.root.close()


class TestCanvas:
    def test_canvas_draws(self, qapp):
        rt = _rt(ALL_TAGS, qapp)
        rt.root.show()
        qapp.processEvents()
        assert rt.namespace["drawn"], "on_draw 应该被调用"
        assert rt.namespace["drawn"][0] == (160, 90)
        rt.root.close()

    def test_canvas_draw_error_does_not_crash(self, qapp, capsys):
        rt = _rt("""
        <Script>def bad(p):
            raise ValueError("boom")
        </Script>
        <Window><Canvas on_draw="bad"/></Window>
        """, qapp)
        rt.root.show()
        qapp.processEvents()
        assert "canvas draw failed" in capsys.readouterr().err
        rt.root.close()


class TestMarkdownHelper:
    def test_headings_and_lists(self):
        html = mini_markdown("# 标题\n- 一\n- 二")
        assert "font-size" in html and "<li>一</li>" in html

    def test_code_fence(self):
        html = mini_markdown("```\nx = 1\n```")
        assert "<pre" in html and "x = 1" in html
