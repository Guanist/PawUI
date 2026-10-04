"""0.1.3.3 的三个回归：TextArea 回声守卫 / Table 斑马纹 / Tabs 丢 stretch。

三条都是「issue 报的现象真实、但根因或范围被讲错」的类型，所以测试直接钉住
**真实触发路径**，而不是 issue 里那段可能绕开的写法：

1. ``<TextArea bind value on_change>`` 且 ``on_change`` 里**写回 state**：
   同文件已有的 ``test_bind_does_not_echo_loop`` 只测了 ``bind + value``（没有
   ``on_change``），于是绕开了这条环。QPlainTextEdit 内容不变也发 ``textChanged``，
   回填 → 回调写回 → 再回填，会撞穿递归并在事件循环里反复重入。
2. ``<Table striped>`` 在深色主题下斑马纹行落回 Qt 平台默认的浅色
   ``QPalette::AlternateBase``（#f7f7f7），文字又是浅色 → 白底白字。
3. ``Tabs.build()`` 直接 ``addWidget(widget)``，丢掉子元素的 ``stretch()``，
   于是 ``<Tab>`` 里第一个子元素的 ``expand`` / ``grow`` 静默失效。
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QTableWidget, QWidget

from pawui.runtime import Runtime


def _render(source: str) -> Runtime:
    rt = Runtime(source, filename="<test>")
    rt._prepare()
    rt._build_tree()
    from PySide6.QtWidgets import QApplication

    QApplication.instance().processEvents()
    return rt


class TestTextAreaEchoWithHandler:
    def test_on_change_writing_back_state_does_not_loop(self, qapp):
        """bind + value 回填 + on_change 写回 state 三件套不能成环。"""
        rt = _render("""
        <Window><TextArea bind="t" value="{$t}" on_change="on_t"/></Window>
        <script>
state.t = "hello"
def on_t(text):
    state.t = text
        </script>
        """)
        edit = rt.root.findChildren(QPlainTextEdit)[0]
        rt.state.watch("t", lambda _v: None)
        # 修复前这里会 RecursionError / 事件循环卡死；修复后应当立即返回。
        edit.setPlainText("hello world")
        assert edit.toPlainText() == "hello world"
        assert rt.state.get("t") == "hello world"
        rt.root.close()

    def test_suppressed_backfill_does_not_call_handler(self, qapp):
        """state 回填控件时，on_change 不应被回调触发（否则就是回声）。"""
        rt = _render("""
        <Window><TextArea bind="t" value="{$t}" on_change="on_t"/></Window>
        <script>
state.t = "a"
calls = []
def on_t(text):
    calls.append(text)
        </script>
        """)
        edit = rt.root.findChildren(QPlainTextEdit)[0]
        calls = rt.namespace["calls"]
        calls.clear()
        # 外部改 state -> 回填控件。这一步不该触发 on_change。
        rt.state.set("t", "b")
        assert edit.toPlainText() == "b"
        assert calls == [], calls
        rt.root.close()


class TestTableStripedDark:
    def test_alternate_color_is_dark_in_dark_theme(self, qapp):
        rt = _render("""
        <Window width="700" height="400" theme="dark"><Column grow="100">
          <Table columns="[A, B]" striped="true" height="220" sortable="false"
                 rows='[{"A":1,"B":2},{"A":3,"B":4},{"A":5,"B":6},{"A":7,"B":8}]'/>
        </Column></Window>
        """)
        table = rt.root.findChild(QTableWidget)
        sheet = table.styleSheet()
        assert "alternate-background-color" in sheet, sheet
        rt.root.close()

    def test_striped_default_is_true(self, qapp):
        """striped 默认 true：不写属性也走斑马纹，所以必须显式给交替色。"""
        rt = _render("""
        <Window width="700" height="400" theme="dark">
          <Table columns="[A]" height="160" sortable="false"
                 rows='[{"A":1},{"A":2}]'/>
        </Window>
        """)
        table = rt.root.findChild(QTableWidget)
        assert table.alternatingRowColors() is True
        assert "alternate-background-color" in table.styleSheet()
        rt.root.close()


class TestTabsKeepsChildStretch:
    def test_expanding_child_fills_tab_page(self, qapp):
        rt = _render("""
        <Window width="800" height="620"><Tabs grow="100"><Tab label="页一">
          <Scroll id="inner" expand="true" bg="surface">
            <Column padding="8"><Text>第一行</Text><Text>第二行</Text></Column>
          </Scroll>
        </Tab></Tabs></Window>
        """)
        inner = rt.root.findChild(QWidget, "inner")
        page = inner.parentWidget()
        # 修复前只按 sizeHint 显示（页签高度的 ~13%），修复后应占据绝大部分。
        assert inner.height() > page.height() * 0.6, (inner.height(), page.height())
        rt.root.close()

    def test_tab_without_stretch_still_pins_content_top(self, qapp):
        """没有子元素要伸展时，尾簧照旧存在（内容顶到上方，不能被这次修改弄丢）。"""
        rt = _render("""
        <Window width="400" height="400"><Tabs><Tab label="页一">
          <Text>a</Text>
        </Tab></Tabs></Window>
        """)
        # 没有子元素要伸展时，页里仍应补一个尾簧（stretch item）
        from PySide6.QtWidgets import QTabWidget

        tw = rt.root.findChild(QTabWidget)
        page = tw.widget(0)
        lay = page.layout()
        has_spacer = any(lay.itemAt(i).spacerItem() is not None for i in range(lay.count()))
        assert has_spacer, "无 stretch 子元素时仍应补尾簧"
        rt.root.close()


class TestSelectPlaceholder:
    """`<Select placeholder>`：此前文档里有、实现里没有的属性（0.1.3.3 补上）。"""

    def test_placeholder_shown_when_nothing_selected(self, qapp):
        rt = _render('<Window><Select items="[a, b, c]" placeholder="Pick"/></Window>')
        combo = rt.root.findChildren(QComboBox)[0]
        assert combo.placeholderText() == "Pick"
        assert combo.currentIndex() == -1
        assert combo.currentText() == ""
        rt.root.close()

    def test_real_value_wins_over_placeholder(self, qapp):
        rt = _render('<Window><Select items="[a, b, c]" value="b" placeholder="Pick"/></Window>')
        combo = rt.root.findChildren(QComboBox)[0]
        assert combo.currentText() == "b"
        assert combo.currentIndex() == 1
        rt.root.close()

    def test_value_outside_items_falls_back_to_placeholder(self, qapp):
        rt = _render('<Window><Select items="[a, b]" value="zzz" placeholder="Pick"/></Window>')
        combo = rt.root.findChildren(QComboBox)[0]
        assert combo.currentIndex() == -1
        rt.root.close()

    def test_without_placeholder_behaviour_unchanged(self, qapp):
        """向后兼容：没写 placeholder 时，还是默认选中第一项。"""
        rt = _render('<Window><Select items="[a, b]"/></Window>')
        combo = rt.root.findChildren(QComboBox)[0]
        assert combo.currentIndex() == 0
        assert combo.currentText() == "a"
        rt.root.close()
