"""Tests for the PawUI animate module."""

import sys

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QLabel

from pawui.animate import _EASINGS, _KINDS, _SLIDE, easing, is_animation
from pawui.runtime import Runtime


class TestEasing:
    def test_known_easings(self):
        for name in _EASINGS:
            curve = easing(name)
            assert curve is not None

    def test_unknown_easing_defaults_to_out_cubic(self):
        from PySide6.QtCore import QEasingCurve
        curve = easing("unknown")
        assert curve == QEasingCurve.Type.OutCubic


class TestIsAnimation:
    def test_known_animations(self):
        for kind in _KINDS:
            assert is_animation(kind) is True

    def test_unknown_animation(self):
        assert is_animation("unknown") is False

    def test_empty_string(self):
        assert is_animation("") is False


class TestSlideConstants:
    def test_slide_up(self):
        dx, dy = _SLIDE["slide-up"]
        assert dx == 0
        assert dy == 22

    def test_slide_down(self):
        dx, dy = _SLIDE["slide-down"]
        assert dx == 0
        assert dy == -22

    def test_slide_left(self):
        dx, dy = _SLIDE["slide-left"]
        assert dx == 22
        assert dy == 0

    def test_slide_right(self):
        dx, dy = _SLIDE["slide-right"]
        assert dx == -22
        assert dy == 0


class TestEntranceSurvivesRebuild:
    """延迟入场动画不能去碰已经被销毁的控件。

    复现路径：``animate="…" delay="…"`` 的控件在延迟窗口内被销毁
    （``<If>`` / ``<For>`` 局部刷新、``app.refresh()`` 全量重建、``pawui watch``），
    延迟回调再访问 ``widget.pos()`` / ``group.start()`` 就会抛
    ``RuntimeError: libshiboken: Internal C++ object … already deleted``。
    这个异常发生在 Qt 事件循环里，用户代码无法 try/except。
    """

    SOURCE = """
    <Window>
      <Column>
        <If condition="{{$flag}}">
          <Text animate="{kind}" delay="30">hello</Text>
          <Text animate="{kind}" delay="30">world</Text>
        </If>
      </Column>
    </Window>
    """

    @staticmethod
    def _pump(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    @pytest.mark.parametrize("kind", ["fade", "slide-up", "reveal"])
    @pytest.mark.parametrize("trigger", ["state", "refresh"])
    def test_widget_destroyed_during_delay(self, qapp, monkeypatch, kind, trigger):
        # PySide6 把槽函数里未捕获的异常交给 sys.excepthook
        errors: list = []
        monkeypatch.setattr(sys, "excepthook", lambda *args: errors.append(args))

        rt = Runtime(self.SOURCE.format(kind=kind))
        rt.state.set("flag", True)
        rt._prepare()
        rt._build_tree()
        assert len(rt.root.findChildren(QLabel)) == 2

        def destroy():
            if trigger == "state":
                rt.state.set("flag", False)
            else:
                rt.refresh()

        QTimer.singleShot(5, destroy)  # 30ms 延迟还没到就销毁
        self._pump(300)

        assert errors == []
        rt.root.close()
