"""VirtualList：只渲染可见行的长列表。"""

import textwrap

from PySide6.QtWidgets import QLabel, QScrollArea

from pawui.runtime import Runtime
from pawui.widgets import BUILTINS

SRC = """
<Script>rows = [{"n": i} for i in range(5000)]</Script>
<Window width="420" height="480">
  <VirtualList id="vl" rows="{$rows}" row_height="20" height="300">
    <Row padding="0"><Text>row {$item[n]}</Text></Row>
  </VirtualList>
</Window>
"""


def _rt(src: str, qapp) -> Runtime:
    rt = Runtime(textwrap.dedent(src))
    rt._prepare()
    rt._build_tree()
    return rt


def _texts(rt) -> list[str]:
    return [lb.text() for lb in rt.root.findChildren(QLabel)]


class TestVirtualList:
    def test_registered(self):
        assert "VirtualList" in BUILTINS

    def test_only_visible_rows_are_built(self, qapp):
        rt = _rt(SRC, qapp)
        rt.root.show()
        qapp.processEvents()
        labels = _texts(rt)
        assert 0 < len(labels) < 60, f"5000 行只该建几十个控件，实际 {len(labels)}"
        assert labels[0] == "row 0"
        rt.root.close()

    def test_scroll_changes_rendered_rows(self, qapp):
        rt = _rt(SRC, qapp)
        rt.root.show()
        qapp.processEvents()
        scroll = rt.root.findChild(QScrollArea, "vl")
        bar = scroll.verticalScrollBar()
        assert bar.maximum() > 4000, "滚动范围要按全部行数算"
        bar.setValue(2000)
        qapp.processEvents()
        labels = _texts(rt)
        assert labels[0] == "row 100", labels[:3]
        assert len(labels) < 60
        rt.root.close()

    def test_content_height_matches_row_count(self, qapp):
        rt = _rt(SRC, qapp)
        scroll = rt.root.findChild(QScrollArea, "vl")
        assert scroll.widget().height() == 5000 * 20
        rt.root.close()

    def test_rows_update_with_state(self, qapp):
        rt = _rt("""
        <Script>rows = [1, 2]
        def grow():
            state.set("rows", [1, 2, 3, 4])
        </Script>
        <Window><VirtualList id="vl" rows="{$rows}" row_height="20" height="200">
          <Text>n {$item}</Text>
        </VirtualList></Window>
        """, qapp)
        scroll = rt.root.findChild(QScrollArea, "vl")
        assert scroll.widget().height() == 2 * 20
        rt.namespace["grow"]()
        qapp.processEvents()
        assert scroll.widget().height() == 4 * 20
        assert _texts(rt) == ["n 1", "n 2", "n 3", "n 4"]
        rt.root.close()

    def test_large_list_is_virtualized(self, qapp):
        """5 万行只建出个位数控件 —— 这才是「虚拟化」的判据。

        别用耗时当判据：CI/本地负载一抖就会假红（历史上这条在
        ``pytest -q`` 全量跑时反复失败，单独跑又必过）。控件数才是
        机器无关的硬指标。
        """
        import time

        started = time.perf_counter()
        rt = _rt("""
        <Script>rows = list(range(50000))</Script>
        <Window><VirtualList rows="{$rows}" row_height="18" height="300">
          <Text>{$item}</Text>
        </VirtualList></Window>
        """, qapp)
        elapsed = (time.perf_counter() - started) * 1000

        # 硬判据：虚拟化之后控件数必须远小于行数
        widgets = rt.all_widgets()
        assert len(widgets) < 100, f"5 万行不该建出 {len(widgets)} 个控件"

        # 耗时只做「明显退化」的粗筛：给足余量（正常 <100ms），
        # 只拦「有人把虚拟化写没了」这种数量级级别的退化
        assert elapsed < 5000, f"5 万行建树耗时异常：{elapsed:.0f}ms（预期几十 ms 量级）"
        rt.root.close()

    def test_empty_rows(self, qapp):
        rt = _rt("""
        <Window><VirtualList rows="{$rows}" row_height="20" height="200">
          <Text>{$item}</Text>
        </VirtualList></Window>
        """, qapp)
        assert _texts(rt) == []
        rt.root.close()
