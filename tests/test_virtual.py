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

    def test_large_list_is_fast(self, qapp):
        import time

        started = time.perf_counter()
        rt = _rt("""
        <Script>rows = list(range(50000))</Script>
        <Window><VirtualList rows="{$rows}" row_height="18" height="300">
          <Text>{$item}</Text>
        </VirtualList></Window>
        """, qapp)
        elapsed = (time.perf_counter() - started) * 1000
        assert elapsed < 1200, f"5 万行建树不该超过 1.2 秒，实际 {elapsed:.0f}ms"
        assert len(rt.all_widgets()) < 100
        rt.root.close()

    def test_empty_rows(self, qapp):
        rt = _rt("""
        <Window><VirtualList rows="{$rows}" row_height="20" height="200">
          <Text>{$item}</Text>
        </VirtualList></Window>
        """, qapp)
        assert _texts(rt) == []
        rt.root.close()
