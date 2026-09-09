"""PawUI 动画：声明式入场动画 + 缓动曲线。

用法（在 .paw 里）：
    <Card animate="slide-up" duration="320" delay="60" easing="out-back"/>
    <Column stagger="60"> ... </Column>   # 子元素逐个入场
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QTimer,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

_EASINGS = {
    "linear": QEasingCurve.Type.Linear,
    "in-cubic": QEasingCurve.Type.InCubic,
    "out-cubic": QEasingCurve.Type.OutCubic,
    "in-out-cubic": QEasingCurve.Type.InOutCubic,
    "out-quad": QEasingCurve.Type.OutQuad,
    "out-quart": QEasingCurve.Type.OutQuart,
    "out-back": QEasingCurve.Type.OutBack,
    "out-elastic": QEasingCurve.Type.OutElastic,
}

_SLIDE = {
    "slide-up": (0, 22),
    "slide-down": (0, -22),
    "slide-left": (22, 0),
    "slide-right": (-22, 0),
}

_KINDS = {"fade", "reveal", "slide-up", "slide-down", "slide-left", "slide-right"}


def easing(name: str) -> QEasingCurve.Type:
    return _EASINGS.get(name, QEasingCurve.Type.OutCubic)


def is_animation(kind: str) -> bool:
    return kind in _KINDS


def entrance(widget: QWidget, kind: str, duration: int = 260, delay: int = 0,
             curve: str = "out-cubic") -> QParallelAnimationGroup:
    """给一个控件做入场动画：淡入 + 可选位移/高度展开。"""
    group = QParallelAnimationGroup(widget)

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    fade = QPropertyAnimation(effect, b"opacity")
    fade.setDuration(duration)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(easing(curve))
    group.addAnimation(fade)

    pos_anim = None
    height_anim = None
    if kind in _SLIDE:
        pos_anim = QPropertyAnimation(widget, b"pos")
        pos_anim.setDuration(duration)
        pos_anim.setEasingCurve(easing(curve))
        group.addAnimation(pos_anim)
    elif kind == "reveal":
        height_anim = QPropertyAnimation(widget, b"maximumHeight")
        height_anim.setDuration(duration)
        height_anim.setEasingCurve(easing(curve))
        group.addAnimation(height_anim)

    def _start() -> None:
        if pos_anim is not None:
            end = widget.pos()
            dx, dy = _SLIDE[kind]
            pos_anim.setStartValue(end + QPoint(dx, dy))
            pos_anim.setEndValue(end)
        if height_anim is not None:
            height_anim.setStartValue(0)
            height_anim.setEndValue(max(widget.sizeHint().height(), widget.height()))
        group.start()

    QTimer.singleShot(max(0, delay), _start)
    return group


def fade_window(window: QWidget, duration: int = 200) -> QPropertyAnimation:
    """主题切换时给窗口来一下淡入。"""
    anim = QPropertyAnimation(window, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(0.55)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    return anim
