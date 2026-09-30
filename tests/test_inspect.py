"""pawui inspect + 无障碍 + toast。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from pawui.runtime import Runtime

SRC = """
<Style>
  .card { radius: 12; }
  #go   { radius: 20; }
</Style>
<Window width="400" height="300">
  <Column class="card">
    <Text id="go" aria_label="提交按钮">正文</Text>
    <Button aria_label="确认">确认</Button>
    <Text tabindex="-1">不可聚焦</Text>
  </Column>
</Window>
"""


def _rt(src: str, qapp) -> Runtime:
    rt = Runtime(src)
    rt._prepare()
    rt._build_tree()
    return rt


class TestInspect:
    def test_tree_contains_tags_and_ids(self, qapp):
        rt = _rt(SRC, qapp)
        out = rt.inspect_tree()
        assert "<Window>" in out
        assert "<Text#go.card>" in out or "<Text#go>" in out
        assert "确认" in out
        rt.root.close()

    def test_tree_shows_matched_selectors(self, qapp):
        rt = _rt(SRC, qapp)
        out = rt.inspect_tree()
        assert "← .card" in out
        assert "← #go" in out
        rt.root.close()

    def test_tree_shows_state_subscriptions(self, qapp):
        rt = _rt("""
        <Script>state.set("name", "x")</Script>
        <Window><Text>{$name}</Text></Window>
        """, qapp)
        assert "state subscriptions: name" in rt.inspect_tree()
        rt.root.close()

    def test_cli_inspect_runs(self, qapp, tmp_path, capsys):
        from pawui import cli

        path = tmp_path / "mini.paw"
        path.write_text('<Window width="200" height="120"><Text id="t">hi</Text></Window>',
                        encoding="utf-8")
        assert cli.inspect(str(path)) == 0
        assert "<Text#t>" in capsys.readouterr().out

    def test_cli_inspect_missing_file(self, tmp_path, capsys):
        from pawui import cli

        assert cli.inspect(str(tmp_path / "nope.paw")) == 1
        assert "not found" in capsys.readouterr().err


class TestA11y:
    def test_aria_label_becomes_accessible_name(self, qapp):
        rt = _rt(SRC, qapp)
        assert rt.query("#go").widget.accessibleName() == "提交按钮"
        rt.root.close()

    def test_text_becomes_accessible_name_by_default(self, qapp):
        rt = _rt('<Window><Text id="t">你好</Text></Window>', qapp)
        assert rt.query("#t").widget.accessibleName() == "你好"
        rt.root.close()

    def test_tabindex_minus_one_disables_focus(self, qapp):
        rt = _rt(SRC, qapp)
        no_focus = [lb for lb in rt.root.findChildren(QLabel) if lb.text() == "不可聚焦"][0]
        assert no_focus.focusPolicy() == Qt.FocusPolicy.NoFocus
        rt.root.close()

    def test_tabindex_zero_makes_focusable(self, qapp):
        rt = _rt('<Window><Text tabindex="0">x</Text></Window>', qapp)
        assert rt.root.findChild(QLabel).focusPolicy() == Qt.FocusPolicy.StrongFocus
        rt.root.close()


class TestToast:
    def test_toast_creates_floating_label(self, qapp):
        rt = _rt('<Window width="300" height="200"><Text>x</Text></Window>', qapp)
        rt.root.show()
        label = rt.toast("保存成功", "success")
        assert label is not None and label.text() == "保存成功"
        assert label.parent() is rt.root
        assert label.y() < rt.root.height()
        rt.root.close()

    def test_toasts_stack(self, qapp):
        rt = _rt('<Window width="300" height="240"><Text>x</Text></Window>', qapp)
        rt.root.show()
        first = rt.toast("一")
        second = rt.toast("二")
        assert first is not None and second is not None
        assert second.y() >= first.y(), "最新的在最下面，旧的往上叠"
        assert len(rt._toasts) == 2
        rt.root.close()

    def test_toast_kind_color(self, qapp):
        rt = _rt('<Window width="300" height="200"><Text>x</Text></Window>', qapp)
        rt.root.show()
        assert rt.theme.danger in rt.toast("炸了", "error").styleSheet()
        rt.root.close()
