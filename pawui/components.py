"""PawUI 组件库（Qt 后端）：把 AST 元素映射为 QWidget + QSS 自定义样式。

抗锯齿、圆角、悬停/聚焦态、IME 组字全部交给 Qt 原生处理。
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .animate import is_animation
from .nodes import Element
from .resolve import (
    collect_refs,
    is_template,
    resolve_handler,
    resolve_prop_value,
    resolve_raw,
)
from .theme import Theme, _blend

_ALIGN_MAP = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight,
}


def _truthy(value: Any) -> bool:
    """把 state / props 里的值统一判成真值。

    ``state`` 里存的可能是 bool，也可能是模板渲染出来的字符串，所以不能直接
    ``bool(value)`` —— ``bool("False")`` 恒为 True。
    """
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _css_bool(value: Any) -> bool:
    """CSS 里写 ``wrap: true`` / ``1`` / ``yes`` 都算真。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


class _ElidedLabel(QLabel):
    """支持 CSS ``ellipsis`` / ``line-height`` 的 QLabel。

    永远保存完整原文，``text()`` 返回的也是原文（不是富文本 HTML）；
    只有在渲染时才按当前宽度决定是否省略、或按 line-height 包成富文本。
    """

    def __init__(self, text: str = ""):
        super().__init__()
        self._full_text = text
        self._elide = False
        self._line_height = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._render()

    def _render(self) -> None:
        text = self._full_text
        if self._line_height:
            self.setTextFormat(Qt.TextFormat.RichText)
            text = _wrap_line_height(text, self._line_height)
        else:
            self.setTextFormat(Qt.TextFormat.PlainText)
            if self._elide and self.width() > 0:
                metrics = QFontMetrics(self.font())
                text = metrics.elidedText(
                    text, Qt.TextElideMode.ElideRight, max(0, self.width() - 2)
                )
        super().setText(text)

    def set_elide(self, enabled: bool) -> None:
        self._elide = bool(enabled)
        self._render()

    def set_line_height(self, value: str) -> None:
        self._line_height = value or ""
        self._render()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt 命名)
        self._full_text = text
        self._render()

    def text(self) -> str:
        return self._full_text

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        super().resizeEvent(event)
        # 没开省略号和行高时什么都不用重算 —— 不然每个 QLabel 每次 resize
        # 都要重设一遍文字，1000 行的列表光这一步就是几百毫秒
        if self._elide or self._line_height:
            self._render()


def apply_text_props(widget: QWidget, props: dict[str, Any]) -> None:
    """把 CSS 里的文本属性落到控件上 —— QSS 不认识这几个属性。

    支持 ``wrap`` / ``align`` / ``selectable`` / ``ellipsis``（QLabel 族）。
    ``line-height`` 由 ``Text`` 组件用富文本实现，不在这里处理。
    """
    if isinstance(widget, QLabel):
        if "wrap" in props:
            widget.setWordWrap(_css_bool(props["wrap"]))
        if "align" in props:
            flag = _ALIGN_MAP.get(str(props["align"]).strip().lower())
            if flag is not None:
                widget.setAlignment(flag | Qt.AlignmentFlag.AlignVCenter)
        if "selectable" in props:
            widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                if _css_bool(props["selectable"])
                else Qt.TextInteractionFlag.NoTextInteraction
            )
        if "ellipsis" in props and isinstance(widget, _ElidedLabel):
            widget.set_elide(_css_bool(props["ellipsis"]))
        if "line-height" in props and isinstance(widget, _ElidedLabel):
            widget.set_line_height(str(props["line-height"]))


def _wrap_line_height(text: str, value: str) -> str:
    """QLabel 没有 line-height，用富文本的 ``<div style="line-height:…">`` 实现。"""
    body = _html.escape(text).replace("\n", "<br/>")
    return f'<div style="line-height:{value}">{body}</div>'


def _as_item_list(value: Any) -> list[Any]:
    """把 items 属性统一成列表。

    支持真 list/tuple（``items="{$options}"``），也支持直接写在属性里的字面量
    ``items="[a, b, c]"`` / ``items="a, b, c"`` —— 以前字面量会被当成一个字符串，
    静默渲染成**空下拉框**，既不报错也看不到东西。
    """
    return _as_list(value)


def _box_values(value: Any) -> tuple[int, int, int, int] | None:
    """解析 CSS 简写盒模型值，返回 Qt 顺序的 ``(左, 上, 右, 下)``。

    支持 ``12`` / ``"4 8"`` / ``[4, 8, 12, 16]``，字符串按 CSS 的
    「上 / 右 / 下 / 左」顺序解释。
    """
    if value is None:
        return None
    if isinstance(value, str):
        tokens = value.replace(",", " ").split()
        try:
            nums = [int(t) for t in tokens]
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        nums = [int(value)]
    else:
        try:
            nums = [int(v) for v in value]
        except (TypeError, ValueError):
            return None
    if not nums:
        return None
    if len(nums) == 1:
        n = nums[0]
        return (n, n, n, n)
    if len(nums) == 2:
        return (nums[1], nums[0], nums[1], nums[0])
    if len(nums) == 3:
        return (nums[1], nums[0], nums[2], nums[1])
    return (nums[3], nums[0], nums[1], nums[2])


def _as_list(value: Any) -> list[Any]:
    """把字面量/真列表统一成 list。

    支持真 list/tuple（``items="{$options}"``），也支持直接写在属性里的字面量
    ``items="[a, b, c]"`` / ``items="a, b, c"`` —— 以前字面量会被当成一个字符串，
    静默渲染成**空下拉框**，既不报错也看不到东西。
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        if not text.strip():
            return []
        return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]
    return []


def _style_flat_button(btn: QPushButton, theme: Theme, bg: str, fg: str,
                       radius: int, size: int) -> None:
    """扁平按钮样式。Button 与 Dialog 的次级按钮共用，保证按钮跟着主题变色。"""
    hover = _blend(bg, "#ffffff", 0.14)
    press = _blend(bg, "#000000", 0.16)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"""
        QPushButton {{ background-color:{bg}; color:{fg}; border:none; border-radius:{radius}px;
            min-height:34px; padding:0 18px; font-weight:600; font-size:{size}px; }}
        QPushButton:hover {{ background-color:{hover}; }}
        QPushButton:pressed {{ background-color:{press}; }}
        QPushButton:disabled {{ background-color:{theme.border}; color:{theme.subtext}; }}
        """
    )


class FlowLayout(QLayout):
    """``flex-wrap: wrap`` 的等价物：子控件一行排不下就自动换行。

    Qt 没有内置流式布局（QBoxLayout 只能一行/一列到底），所以按经典的
    QLayout 子类写法自己实现 ``heightForWidth``。
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 8):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # -- QLayout 必需接口 --
    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 (Qt 命名)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def addStretch(self, _stretch: int = 1) -> None:  # noqa: N802
        """流式布局没有弹簧的概念，容器收尾时调过来直接忽略。"""

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() and line_height > 0:
                x = area.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class Component:
    is_container = False
    #: 组件自己解释 width / height（比如 Window 用它定窗口大小），
    #: 这类组件的通用盒模型尺寸就不该再插手。
    owns_size = False

    def __init__(self, runtime: Any, parent: Component | None, element: Element, scope: dict):
        self.runtime = runtime
        self.parent = parent
        self.element = element
        self.scope = scope
        self.props = element.props
        self.theme: Theme = runtime.theme
        self.widget: QWidget | None = None
        self.layout: Any = None
        self._children: list[Component] = []
        self._unwatch: list[Any] = []
        # 容器布局策略：`Container.build()` 会按属性重新赋值，但像 `Dialog`
        # 这种自己搭 QVBoxLayout、没走 `super().build()` 的子类不会 —— 而
        # `Container.add_child()` 无条件读这两个字段（Tabs 就会对子元素调它），
        # 所以在基类给默认值，别让子类漏初始化直接 AttributeError。
        self._justify: str = "start"
        self._cross_align: str = "start"
        # 组件自带的默认样式；用户 CSS 追加在它后面（同一张表里后写胜出）
        self._base_qss: str = ""
        self._base_qss_locked: bool = False
        self._margin_host: QWidget | None = None
        self._error_label: QWidget | None = None
        self._last_qss: str = ""

    def watch_state(self, key: str, fn: Any) -> None:
        unsubscribe = self.runtime.state.watch(key, fn)
        self._unwatch.append(unsubscribe)
        self.runtime._subscriptions.append(unsubscribe)

    def dispose_children(self) -> None:
        for child in self._children:
            child.dispose()
        self._children.clear()

    def dispose(self) -> None:
        self.dispose_children()
        for unsubscribe in self._unwatch:
            unsubscribe()
        self._unwatch.clear()
        if self._margin_host is not None:
            try:
                self._margin_host.deleteLater()
            except RuntimeError:  # 父控件先一步被销毁了
                pass
            self._margin_host = None

    def build(self) -> QWidget:
        raise NotImplementedError

    def validate(self) -> str | None:
        return None

    def error_text(self) -> str | None:
        """字段级校验：有错返回给用户看的文字，没问题返回 None。

        （``validate()`` 是旧名字，保留给外部实现用。）
        """
        return self.validate()

    def set_error(self, message: str | None) -> None:
        """把校验结果画到页面上：红色描边 + 控件下面一行错误文字。"""
        if self.widget is None:
            return
        self.runtime.show_field_error(self, message)

    def stretch(self) -> int:
        """flex-grow 等价物：``grow="2"`` 占两份，``expand`` 是 ``grow="1"`` 的别名。"""
        grow = self.opt_int("grow", 0)
        if grow:
            return grow
        return 1 if self.opt_bool("expand", False) else 0

    def apply_flex_policy(self) -> None:
        """``shrink="0"`` 时别让布局把控件压扁（Qt 没有真 shrink，用尺寸策略近似）。"""
        if self.widget is None or "shrink" not in self.props:
            return
        if self.opt_int("shrink", 1) > 0:
            return
        policy = self.widget.sizePolicy()
        policy.setHorizontalStretch(0)
        self.widget.setMinimumWidth(self.widget.sizeHint().width())
        self.widget.setSizePolicy(QSizePolicy.Policy.Fixed, policy.verticalPolicy())

    def margin(self) -> tuple[int, int, int, int] | None:
        """解析 ``margin``：单值、``"4 8"`` 或 ``"4 8 4 8"``（CSS 顺序）。"""
        raw = self.props.get("margin")
        if raw is None:
            return None
        return _box_values(resolve_prop_value(raw, self.scope, self.runtime))

    def placement(self) -> QWidget | None:
        """返回真正交给父布局摆放的控件。

        CSS 的外边距在 Qt 布局里没有对应概念（QSS 的 margin 是往内缩的），
        所以有 ``margin`` 时套一层只有边距的壳子 —— 控件身份不变，
        ``findChild`` / ``app.query()`` 拿到的仍是本体。
        """
        if self.widget is None:
            return None
        if self._margin_host is not None:
            return self._margin_host
        margins = self.margin()
        if not margins or not any(margins):
            return self.widget
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(*margins)
        lay.setSpacing(0)
        lay.addWidget(self.widget)
        self._margin_host = host
        return host

    def add_child(self, child: Component, index: int) -> None:
        """往容器里放一个子控件。Grid 之类会覆写它来改写落位方式。"""
        self.layout.addWidget(child.placement(), child.stretch())

    def finish_children(self) -> None:
        """子控件放完之后的收尾：线性布局补一个尾部弹簧，把内容顶到上方。"""
        if getattr(self, "add_trailing_stretch", True):
            self.layout.addStretch(1)

    def maybe_animate(self, delay_bonus: int = 0) -> None:
        kind = self.props.get("animate")
        if not kind or self.widget is None:
            return
        kind = str(resolve_prop_value(kind, self.scope, self.runtime))
        if not is_animation(kind):
            return
        self.runtime.queue_animation(
            self.widget,
            kind,
            self.opt_int("duration", 260),
            self.opt_int("delay", 0) + delay_bonus,
            self.opt_str("easing", "out-cubic"),
        )

    # -- 取值 --
    def content(self) -> str:
        return str(self.props.get("__content__", ""))

    def resolved_content(self) -> str:
        return str(resolve_prop_value(self.props.get("__content__", ""), self.scope, self.runtime))

    def opt_str(self, key: str, default: str = "") -> str:
        return str(resolve_prop_value(self.props.get(key, default), self.scope, self.runtime))

    def opt_int(self, key: str, default: int) -> int:
        v = resolve_prop_value(self.props.get(key, default), self.scope, self.runtime)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def opt_size(self, default: int | None = None) -> int:
        d = self.theme.font_size if default is None else default
        return self.opt_int("size", self.opt_int("font_size", d))

    def opt_bool(self, key: str, default: bool = False) -> bool:
        return _truthy(resolve_prop_value(self.props.get(key, default), self.scope, self.runtime))

    def opt_color(self, key: str, default: str) -> str:
        value = str(resolve_prop_value(self.props.get(key, default), self.scope, self.runtime))
        if value and not QColor(value).isValid():
            self.runtime.warn_unknown_color(value, self.element.tag, key)
        return value

    def padding(self) -> tuple[int, int, int, int]:
        v = resolve_prop_value(self.props.get("padding", self.theme.padding), self.scope, self.runtime)
        parsed = _box_values(v)
        if parsed is not None:
            return parsed
        p = self.theme.padding
        return (p, p, p, p)

    def bind_state(self, template: str, set_fn: Any) -> None:
        """state 变化时把**求值后的原始值**交给 set_fn。

        必须走 resolve_raw 而不是 resolve_template：后者渲染成字符串，于是
        ``bool("False")`` 恒为 True —— 复选框会在用户点掉之后被立刻按回去。
        """
        names = collect_refs(template, self.scope, self.runtime)
        for name in names:
            self.watch_state(
                name,
                lambda _, _template=template: set_fn(
                    resolve_raw(_template, self.scope, self.runtime)
                ),
            )

    def _bind_key(self) -> str:
        bind = self.props.get("bind", "")
        if not isinstance(bind, str):
            return ""
        key = bind.strip()
        if key.startswith("{"):
            key = key[1:]
        if key.endswith("}"):
            key = key[:-1]
        if key.startswith("$"):
            key = key[1:]
        return key.strip()

    def _push_state(self, key: str, value: Any) -> None:
        if getattr(self, "_suppress", False):
            return
        self.runtime.state.set(key, value)


class Window(Component):
    is_container = True
    owns_size = True
    # 根节点不补尾簧。Component.finish_children() 默认会补一个 stretch=1 的弹簧把内容
    # 顶到上方，但窗口是根，子元素（常见写法是一个没写 expand 的 <Column>）在根布局里
    # stretch 是 0，竞争不过弹簧，于是被压成 sizeHint 高、窗口下半屏全空。
    # 需要把内容顶到上方时，交给子元素自己的 justify / align 控制。
    add_trailing_stretch = False

    def build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        p = self.opt_int("padding", 0)
        left, top, right, bottom = (p, p, p, p)
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("spacing", self.theme.spacing))
        self.widget = root
        self.layout = lay
        return root


class Container(Component):
    is_container = True
    axis = "y"
    add_trailing_stretch = True

    def build(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box) if self.axis == "y" else QHBoxLayout(box)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("gap", self.opt_int("spacing", self.theme.spacing)))
        self._justify = str(self.opt_str("justify", "start")).strip().lower()
        self._cross_align = str(self.opt_str("align", "start")).strip().lower()
        bg = self.opt_color("bg", "")
        if bg:
            box.setStyleSheet(
                f"QWidget {{ background-color:{bg}; border-radius:{self.opt_int('radius', self.theme.radius)}px; }}"
            )
        self.widget = box
        self.layout = lay
        return box

    def add_child(self, child: Component, index: int) -> None:
        # justify=space-between / space-around：在子控件之间插弹簧
        if self._justify in ("space-between", "space-around", "center") and index > 0:
            self.layout.addStretch(1)
        elif self._justify in ("center", "end") and index == 0:
            self.layout.addStretch(1)
        self.layout.addWidget(child.widget, child.stretch())
        self._apply_cross_align(child)

    def _apply_cross_align(self, child: Component) -> None:
        if self._cross_align in ("", "start", "stretch", "stretch-child"):
            return
        if self.axis == "y":
            flag = {"center": Qt.AlignmentFlag.AlignHCenter,
                    "end": Qt.AlignmentFlag.AlignRight}.get(self._cross_align)
        else:
            flag = {"center": Qt.AlignmentFlag.AlignVCenter,
                    "end": Qt.AlignmentFlag.AlignBottom}.get(self._cross_align)
        if flag is not None and child.widget is not None:
            self.layout.setAlignment(child.widget, flag)

    def finish_children(self) -> None:
        if hasattr(self.layout, "addStretch"):
            self.layout.addStretch(1)


class Grid(Container):
    """网格容器：``<Grid columns="3" gap="12">``，子元素行优先自动排布。"""

    is_container = True
    axis = "y"
    add_trailing_stretch = False

    def build(self) -> QWidget:
        box = QWidget()
        lay = QGridLayout(box)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        gap = self.opt_int("gap", self.opt_int("spacing", self.theme.spacing))
        lay.setHorizontalSpacing(gap)
        lay.setVerticalSpacing(gap)
        bg = self.opt_color("bg", "")
        if bg:
            box.setStyleSheet(
                f"QWidget {{ background-color:{bg}; border-radius:{self.opt_int('radius', self.theme.radius)}px; }}"
            )
        self.widget = box
        self.layout = lay
        return box

    def add_child(self, child: Component, index: int) -> None:
        columns = max(1, self.opt_int("columns", 2))
        self.layout.addWidget(child.widget, index // columns, index % columns)

    def finish_children(self) -> None:
        return


class Column(Container):
    axis = "y"


class Row(Container):
    axis = "x"

    def build(self) -> QWidget:
        """``wrap="true"`` 时切到流式布局（等价于 ``flex-wrap: wrap``）。"""
        if not self.opt_bool("wrap", False):
            return super().build()
        box = QWidget()
        flow = FlowLayout(box, 0, self.opt_int("gap", self.opt_int("spacing", self.theme.spacing)))
        left, top, right, bottom = self.padding()
        flow.setContentsMargins(left, top, right, bottom)
        bg = self.opt_color("bg", "")
        if bg:
            box.setStyleSheet(
                f"QWidget {{ background-color:{bg};"
                f" border-radius:{self.opt_int('radius', self.theme.radius)}px; }}"
            )
        self._justify = str(self.opt_str("justify", "start")).strip().lower()
        self._cross_align = str(self.opt_str("align", "start")).strip().lower()
        self.widget = box
        self.layout = flow
        self._flow = True
        return box

    def add_child(self, child: Component, index: int) -> None:
        if getattr(self, "_flow", False):
            self.layout.addWidget(child.placement())
            return
        super().add_child(child, index)

    def finish_children(self) -> None:
        if getattr(self, "_flow", False):
            return
        super().finish_children()


class Text(Component):
    def build(self) -> QLabel:
        label = _ElidedLabel(self.resolved_content())
        fg = self.opt_color("color", self.opt_color("fg", self.theme.text))
        size = self.opt_size()
        bold = self.opt_bool("bold", False)
        italic = self.opt_bool("italic", False)
        style = f"color:{fg}; font-size:{size}px;"
        family = self.opt_str("font", "")
        if family:
            style += f' font-family:"{family}";'
        if bold:
            style += " font-weight:600;"
        if italic:
            style += " font-style:italic;"
        spacing = self.opt_str("letter_spacing", "")
        if spacing:
            style += f" letter-spacing:{spacing};"
        underline = self.opt_bool("underline", False)
        if underline:
            style += " text-decoration:underline;"
        # 必须包成 `QLabel { … }` 而不是裸声明：用户 <Style> 的规则是**按控件内联**
        # 追加到这段文本后面的（runtime._apply_user_css），而 Qt 只在「整段没有 {」
        # 时才按裸声明解析；一旦拼上 `.x { … }` 这类规则，前面这串裸声明就会被
        # 当成选择器，整张表解析失败 —— 表现为 Text 上的 class / id 样式全部失效。
        label.setStyleSheet(f"QLabel {{ {style} }}")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # 文本属性直接当 props 用（等价于在 <Style> 里写 .x { wrap: true }）
        apply_text_props(label, {
            "wrap": self._text_prop("wrap", False),
            "align": self.opt_str("align", ""),
            "selectable": self._text_prop("selectable", False),
            "ellipsis": self._text_prop("ellipsis", False),
            "line-height": self.opt_str("line_height", self.opt_str("line-height", "")),
        })
        self.widget = label
        content = self.props.get("__content__", "")
        if isinstance(content, str) and is_template(content):
            self.bind_state(content, lambda v: self.widget.setText(str(v)))
        return label

    def _text_prop(self, key: str, default: Any) -> Any:
        if key not in self.props:
            return default
        return resolve_prop_value(self.props[key], self.scope, self.runtime)


class Button(Component):
    def build(self) -> QPushButton:
        handler = resolve_handler(self.props.get("on_click", None), self.scope, self.runtime)
        theme = self.theme
        bg = self.opt_color("bg", theme.accent)
        fg = self.opt_color("fg", theme.background)
        radius = self.opt_int("radius", 17)
        size = self.opt_size()
        btn = QPushButton(self.resolved_content())
        disabled = self.opt_bool("disabled", False)
        btn.setEnabled(not disabled)
        _style_flat_button(btn, theme, bg, fg, radius, size)
        if handler:
            btn.clicked.connect(lambda: self.runtime.invoke(handler))
        self.widget = btn
        content = self.props.get("__content__", "")
        if isinstance(content, str) and is_template(content):
            self.bind_state(content, lambda v: self.widget.setText(str(v)))
        return btn


class Input(Component):
    def build(self) -> QLineEdit:
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        enter_handler = resolve_handler(self.props.get("on_enter", None), self.scope, self.runtime)
        edit = QLineEdit()
        edit.setPlaceholderText(self.opt_str("placeholder", ""))
        edit.setText(self._initial())
        family = self.opt_str("font", "")
        family_css = f' font-family:"{family}";' if family else ""
        edit.setStyleSheet(
            f"QLineEdit {{ background-color:{self.theme.surface}; color:{self.theme.text};"
            f" border:1px solid {self.theme.border}; border-radius:{self.opt_int('radius', 10)}px;"
            f" padding:7px 12px; font-size:{self.opt_size()}px;{family_css}"
            f" selection-background-color:{self.theme.accent};"
            f" selection-color:{self.theme.background}; }}"
            f" QLineEdit:focus {{ border:2px solid {self.theme.accent}; }}"
        )
        if self.opt_str("show", ""):
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        if handler:
            edit.textChanged.connect(lambda text: self.runtime.invoke(handler, text))
        if enter_handler:
            edit.returnPressed.connect(lambda: self.runtime.invoke(enter_handler, edit.text()))
        bind = self._bind_key()
        if bind:
            self._suppress = False
            edit.textChanged.connect(lambda text: self._push_state(bind, text))
        self.widget = edit
        register = getattr(self.runtime, "register_field", None)
        if register:
            register(self)
        value = self.props.get("value", "")
        if isinstance(value, str) and is_template(value):

            def _set(v: Any) -> None:
                self._suppress = True
                edit.setText(str(resolve_prop_value(v, self.scope, self.runtime)))
                self._suppress = False

            self.bind_state(value, _set)
        return edit

    def _validate_text(self, text: str) -> str | None:
        if self.opt_bool("required") and not text.strip():
            return self.opt_str("error", "This field is required")
        minimum = self.opt_int("min_length", 0)
        if minimum and len(text) < minimum:
            return self.opt_str("error", f"Minimum length is {minimum}")
        return None

    def error_text(self) -> str | None:
        return self._validate_text(self._input_widget().text())

    def _input_widget(self) -> QLineEdit:
        assert isinstance(self.widget, QLineEdit)
        return self.widget

    def _initial(self) -> str:
        return str(resolve_prop_value(self.props.get("value", ""), self.scope, self.runtime))


class ToggleSwitch(QAbstractButton):
    """iOS 风格开关。"""

    def __init__(self, checked: bool, accent: str, sub: str):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = QColor(accent)
        self._sub = QColor(sub)
        self.setFixedSize(46, 26)

    def sizeHint(self) -> QSize:
        return QSize(46, 26)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._accent if on else self._sub)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        d = rect.height() - 6
        x = rect.width() - d - 3 if on else 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(x, 3, d, d)


class Checkbox(Component):
    def build(self) -> QWidget:
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        theme = self.theme
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        toggle = ToggleSwitch(self.opt_bool("checked", False), theme.accent, theme.border)
        label = QLabel(self.resolved_content())
        label.setStyleSheet(f"color:{self.opt_color('fg', theme.text)}; font-size:{self.opt_size()}px;")
        row.addWidget(toggle)
        row.addWidget(label)
        row.addStretch(1)
        self.widget = wrap
        self._toggle = toggle
        if handler:
            toggle.toggled.connect(lambda checked: self.runtime.invoke(handler, checked))
        bind = self._bind_key()
        if bind:
            self._suppress = False
            toggle.toggled.connect(lambda checked: self._push_state(bind, checked))
        checked = self.props.get("checked", None)
        if isinstance(checked, str) and is_template(checked):
            def _set(v: Any) -> None:
                self._suppress = True
                toggle.setChecked(_truthy(resolve_prop_value(v, self.scope, self.runtime)))
                self._suppress = False
            self.bind_state(checked, _set)
        return wrap


class Divider(Component):
    def build(self) -> QFrame:
        f = QFrame()
        f.setObjectName("divider")
        f.setFixedHeight(self.opt_int("thickness", 2))
        f.setStyleSheet(
            f"QFrame#divider {{ background-color:{self.opt_color('color', self.theme.border)}; border:none; }}"
        )
        self.widget = f
        return f


class Spacer(Component):
    owns_size = True

    def build(self) -> QWidget:
        w = QWidget()
        w.setFixedSize(self.opt_int("width", 1), self.opt_int("height", 1))
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.widget = w
        return w


class Slider(Component):
    def build(self) -> QSlider:
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(self.opt_int("min", 0))
        slider.setMaximum(self.opt_int("max", 100))
        slider.setSingleStep(self.opt_int("step", 1))
        slider.setValue(self.opt_int("value", slider.minimum()))
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        accent = self.opt_color("accent", self.theme.accent)
        bg = self.opt_color("bg", self.theme.border)
        radius = self.opt_int("radius", 3)
        slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{ background:{bg}; height:6px; border-radius:{radius}px; }}
            QSlider::sub-page:horizontal {{ background:{accent}; border-radius:{radius}px; }}
            QSlider::handle:horizontal {{ background:#fff; width:16px; margin:-5px 0;
                border-radius:8px; border:2px solid {accent}; }}
            """
        )
        if handler:
            slider.valueChanged.connect(lambda v: self.runtime.invoke(handler, v))
        bind = self._bind_key()
        if bind:
            self._suppress = False
            slider.valueChanged.connect(lambda v: self._push_state(bind, v))
        self.widget = slider
        self._slider = slider
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):

            def _set(v: Any) -> None:
                self._suppress = True
                slider.setValue(int(resolve_prop_value(v, self.scope, self.runtime)))
                self._suppress = False

            self.bind_state(value, _set)
        return slider


class Progress(Component):
    owns_size = True

    _ALIGN = {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }

    def build(self) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, self.opt_int("max", 100))
        bar.setValue(self.opt_int("value", 0))
        show_text = self.opt_bool("text", False)
        bar.setTextVisible(show_text)
        # 显示百分比时必须给文字留高度：以前固定 10px，文字被裁掉还看着不居中
        bar.setFixedHeight(self.opt_int("height", 22 if show_text else 10))
        # QProgressBar 默认左对齐，这里默认居中，可用 align="left|center|right" 改
        bar.setAlignment(
            self._ALIGN.get(self.opt_str("align", "center"), Qt.AlignmentFlag.AlignCenter)
        )
        accent = self.opt_color("accent", self.theme.accent)
        bg = self.opt_color("bg", self.theme.surface)
        radius = self.opt_int("radius", 5)
        bar.setStyleSheet(
            f"""
            QProgressBar {{ background-color:{bg}; color:{self.opt_color('fg', self.theme.text)};
                border:none; border-radius:{radius}px;
                font-size:{self.opt_size()}px; font-weight:600; }}
            QProgressBar::chunk {{ background-color:{accent}; border-radius:{radius}px; }}
            """
        )
        self.widget = bar
        self._bar = bar
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, lambda v: bar.setValue(int(resolve_prop_value(v, self.scope, self.runtime))))
        return bar


class _ThemedComboBox(QComboBox):
    """下拉框：把系统默认那个又小又歪的箭头换成自绘的干净 chevron。

    QSS 画不出三角形（``border`` 三角那套在 Qt 里会渲染成方块），所以直接在
    ``paintEvent`` 里画两笔。颜色跟随主题的 subtext，切主题时会重画。
    """

    def __init__(self, arrow_color: str):
        super().__init__()
        self._arrow_color = QColor(arrow_color)

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._arrow_color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = self.width() - 15.0
        cy = self.height() / 2.0
        half_w, half_h = 4.2, 2.6
        painter.drawLine(
            QPointF(cx - half_w, cy - half_h), QPointF(cx, cy + half_h)
        )
        painter.drawLine(
            QPointF(cx, cy + half_h), QPointF(cx + half_w, cy - half_h)
        )


class Select(Component):
    def build(self) -> QComboBox:
        combo = _ThemedComboBox(self.theme.subtext)
        self._style_popup(combo)
        items = resolve_raw(self.props.get("items", []), self.scope, self.runtime)
        self._set_items(combo, items)
        value = self.props.get("value", "")
        current = str(resolve_prop_value(value, self.scope, self.runtime))
        # placeholder：没有初值 / 初值不在列表里时，显示一段灰色提示并保持「未选中」
        # （索引 -1）。一旦用户选了项，它自然消失。
        placeholder = self.opt_str("placeholder", "")
        if placeholder:
            combo.setPlaceholderText(placeholder)
        combo.setCurrentText(current)
        if placeholder and (not current or current not in [combo.itemText(i) for i in range(combo.count())]):
            combo.setCurrentIndex(-1)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, self._set_current)
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        if handler:
            combo.currentTextChanged.connect(lambda text: self.runtime.invoke(handler, text))
        bind = self._bind_key()
        if bind:
            combo.currentTextChanged.connect(lambda text: self._push_state(bind, text))
        items_prop = self.props.get("items", None)
        if isinstance(items_prop, str) and is_template(items_prop):
            for name in collect_refs(items_prop, self.scope, self.runtime):
                self.watch_state(name, lambda _: self._set_items(combo, resolve_raw(items_prop, self.scope, self.runtime)))
        self.widget = combo
        return combo

    def _set_current(self, value: Any) -> None:
        """state → 下拉框，同样压住回声（``currentTextChanged`` 会推回 state）。"""
        assert isinstance(self.widget, QComboBox)
        self._suppress = True
        try:
            self.widget.setCurrentText(str(resolve_prop_value(value, self.scope, self.runtime)))
        finally:
            self._suppress = False

    def _style_popup(self, combo: QComboBox) -> None:
        """给下拉弹出层的外框上色。

        弹出层是一个独立的顶层 QFrame（``combo.view().window()``），全局 QSS 里
        ``QComboBox QAbstractItemView`` 只管得到内层列表，外框会保持系统原生 3D
        边框 —— 圆角列表套在方框里，两层边框打架。这里把外框一起涂掉。
        """
        view = combo.view()
        popup = view.window() if view is not None else None
        if popup is None or popup is combo:
            return
        popup.setObjectName("pawuiComboPopup")
        popup.setStyleSheet(
            f"#pawuiComboPopup {{ background-color:{self.theme.surface};"
            f" border:1px solid {self.theme.border}; }}"
        )

    @staticmethod
    def _set_items(combo: QComboBox, items: Any) -> None:
        current = combo.currentText()
        values = [str(v) for v in _as_item_list(items)]
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(values)
        if current in values:
            combo.setCurrentText(current)
        combo.blockSignals(False)


class Dialog(Container):
    def build(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("spacing", self.theme.spacing))
        title = self.opt_str("title", "")
        if title:
            label = QLabel(title)
            label.setStyleSheet(f"color:{self.theme.text}; font-size:18px; font-weight:600;")
            lay.addWidget(label)
        buttons = QHBoxLayout()
        cancel = self.opt_str("cancel", "Cancel")
        accept = self.opt_str("accept", "OK")
        theme = self.theme
        btn_size = self.opt_size()
        if cancel:
            button = QPushButton(cancel)
            _style_flat_button(button, theme, theme.surface, theme.text,
                               self.opt_int("button_radius", 10), btn_size)
            handler = resolve_handler(self.props.get("on_reject"), self.scope, self.runtime)
            if handler:
                button.clicked.connect(lambda: self.runtime.invoke(handler))
            buttons.addWidget(button)
        if accept:
            button = QPushButton(accept)
            _style_flat_button(button, theme, theme.accent, theme.background,
                               self.opt_int("button_radius", 10), btn_size)
            handler = resolve_handler(self.props.get("on_accept"), self.scope, self.runtime)
            if handler:
                button.clicked.connect(lambda: self.runtime.invoke(handler))
            buttons.addWidget(button)
        lay.addLayout(buttons)
        panel.setStyleSheet(
            f"QWidget {{ background:{self.opt_color('bg', self.theme.surface)};"
            f" border-radius:{self.opt_int('radius', 12)}px; }}"
        )
        # Dialog 自己搭布局、没走 Container.build()，这里补上容器级别的策略字段，
        # 否则 add_child() 只能拿到基类默认值，Dialog 上写的 justify / align 会失效。
        self._justify = str(self.opt_str("justify", "start")).strip().lower()
        self._cross_align = str(self.opt_str("align", "start")).strip().lower()
        panel.setVisible(self.opt_bool("open", True))
        self.widget = panel
        self.layout = lay
        open_prop = self.props.get("open")
        if isinstance(open_prop, str) and is_template(open_prop):
            self.bind_state(open_prop, lambda v: panel.setVisible(str(v).lower() in ("1", "true", "yes", "on")))
        return panel


class Menu(Component):
    def build(self) -> QToolButton:
        button = QToolButton()
        button.setText(self.opt_str("label", "Menu"))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        radius = self.opt_int("radius", 10)
        button.setStyleSheet(
            f"""
            QToolButton {{ background-color:{self.opt_color('bg', self.theme.surface)};
                color:{self.opt_color('fg', self.theme.text)}; border:1px solid {self.theme.border};
                border-radius:{radius}px; padding:6px 14px; font-size:{self.opt_size()}px; }}
            QToolButton:hover {{ border-color:{self.theme.accent}; }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
            """
        )
        menu = QMenu(button)
        self._set_items(menu, resolve_raw(self.props.get("items", []), self.scope, self.runtime))
        handler = resolve_handler(self.props.get("on_select"), self.scope, self.runtime)
        bind = self._bind_key()
        if handler or bind:
            menu.triggered.connect(lambda action: self._select(action.text(), handler, bind))
        items = self.props.get("items")
        if isinstance(items, str) and is_template(items):
            for name in collect_refs(items, self.scope, self.runtime):
                self.watch_state(name, lambda _: self._set_items(menu, resolve_raw(items, self.scope, self.runtime)))
        button.setMenu(menu)
        self.widget = button
        return button

    def _select(self, text: str, handler: Any, bind: str) -> None:
        if handler:
            self.runtime.invoke(handler, text)
        if bind:
            self._push_state(bind, text)

    @staticmethod
    def _set_items(menu: QMenu, items: Any) -> None:
        menu.clear()
        for item in _as_item_list(items):
            menu.addAction(str(item))


class Form(Container):
    """表单容器：``app.submit()`` 会先跑校验，再决定要不要调 ``on_submit``。

    错误直接画在页面上：字段下面一行红字 + 表单顶部一条汇总，而不是像以前那样
    悄悄躺在 ``app.validation_errors`` 里没人看得见。
    """

    def build(self) -> QWidget:
        box = super().build()
        summary = QLabel("")
        summary.setWordWrap(True)
        summary.setVisible(False)
        self._summary = summary
        self.layout.insertWidget(0, summary)
        return box

    def submit(self) -> bool:
        handler = resolve_handler(self.props.get("on_submit"), self.scope, self.runtime)
        if not self.runtime.validate():
            errors = list(self.runtime.validation_errors)
            self._summary.setText(" · ".join(errors))
            self._summary.setStyleSheet(
                f"color:{self.runtime.theme.danger}; font-size:{self.opt_size(12)}px;"
            )
            self._summary.setVisible(True)
            return False
        self._summary.setVisible(False)
        if handler:
            self.runtime.invoke(handler)
        return True


class Tabs(Component):
    is_container = False

    def build(self) -> QTabWidget:
        tabs = QTabWidget()
        bg = self.opt_color("bg", self.theme.background)
        radius = self.opt_int("radius", 8)
        tabs.setStyleSheet(
            f"""
            QTabBar::tab {{ background:{self.theme.surface}; color:{self.theme.subtext};
                padding:8px 18px; border:none; border-top-left-radius:{radius}px;
                border-top-right-radius:{radius}px; }}
            QTabBar::tab:selected {{ background:{bg}; color:{self.theme.text}; }}
            QTabWidget::pane {{ border:1px solid {self.theme.border};
                border-radius:0 0 {radius}px {radius}px; }}
            """
        )
        self.widget = tabs
        self.layout = None  # 子元素由 _build_children 直接 addTab 到 widgets
        self._tabs = tabs
        for child in self.element.children:
            page = QWidget()
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(12, 12, 12, 12)
            label = str(resolve_prop_value(child.props.get("label", "Tab"), self.scope, self.runtime))
            packed = []
            if child.tag == "Tab":
                for inner in child.children:
                    inner_comp = self.runtime._build_element(inner, self, self.scope)
                    if inner_comp.widget is not None:
                        page_lay.addWidget(inner_comp.widget, inner_comp.stretch())
                        packed.append(inner_comp)
            else:
                child_comp = self.runtime._build_element(child, self, self.scope)
                if child_comp.widget is not None:
                    page_lay.addWidget(child_comp.widget, child_comp.stretch())
                    packed.append(child_comp)
            # 只有「页签内没有子元素要伸展」时才补尾簧，否则会和它抢空间（撑不满）。
            if not any(c.stretch() for c in packed):
                page_lay.addStretch(1)
            self._tabs.addTab(page, label)
        return tabs


class Image(Component):
    owns_size = True

    def build(self) -> QLabel:
        label = QLabel()
        src = self.opt_str("src", "")
        path = Path(src)
        if path.is_file():
            pixmap = QPixmap(str(path))
        else:
            pixmap = QPixmap(src)
        if pixmap.isNull() and src:
            from .errors import RenderError
            raise RenderError(f"image not found: {src}", self.element.pos)
        if self.opt_bool("cover", False) and not pixmap.isNull():
            pixmap = pixmap.scaled(
                self.opt_int("width", 0),
                self.opt_int("height", 0) or pixmap.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        elif not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(
                self.opt_int("width", pixmap.width()),
                Qt.TransformationMode.SmoothTransformation,
            )
        if not pixmap.isNull():
            label.setPixmap(pixmap)
        self.widget = label
        self._pixmap = pixmap
        return label


class Tooltip(Component):
    # 注意：Tooltip 在 build() 里自己构建子节点（因为要逐个挂 setToolTip），
    # 所以它对运行时来说**不是**容器 —— 否则子节点会被构建两次。
    is_container = False

    def build(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        hover = self.resolved_content().strip()
        for child in self.element.children:
            child_comp = self.runtime._build_element(child, self, self.scope)
            sub = child_comp.widget
            if isinstance(sub, QWidget) and (hover or self.opt_str("text", "")):
                sub.setToolTip(hover or self.opt_str("text", ""))
            lay.addWidget(sub)
        self.widget = wrap
        self.layout = lay
        return wrap


class TextArea(Component):
    owns_size = True

    def build(self) -> QPlainTextEdit:
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        edit = QPlainTextEdit()
        edit.setPlaceholderText(self.opt_str("placeholder", ""))
        initial = resolve_prop_value(self.props.get("value", ""), self.scope, self.runtime)
        edit.setPlainText(str(initial or ""))
        edit.setReadOnly(self.opt_bool("readonly", False))
        h = self.opt_int("height", 0)
        if h:
            edit.setFixedHeight(h)
        family = self.opt_str("font", "")
        family_css = f' font-family:"{family}";' if family else ""
        edit.setStyleSheet(
            f"QPlainTextEdit {{ background-color:{self.theme.surface}; color:{self.theme.text};"
            f" border:1px solid {self.theme.border}; border-radius:{self.opt_int('radius', 10)}px;"
            f" padding:8px 12px; font-size:{self.opt_size()}px;{family_css} }}"
            f" QPlainTextEdit:focus {{ border:2px solid {self.theme.accent}; }}"
        )
        if handler:
            # _suppress 守卫：state 回填触发 setPlainText -> textChanged -> 又回调写回 state
            # 会成环（QPlainTextEdit 内容不变也发 textChanged）。回填期间必须压住。
            edit.textChanged.connect(
                lambda: None
                if getattr(self, "_suppress", False)
                else self.runtime.invoke(handler, edit.toPlainText())
            )
        bind = self._bind_key()
        if bind:
            self._suppress = False
            edit.textChanged.connect(lambda: self._push_state(bind, edit.toPlainText()))
        self.widget = edit
        register = getattr(self.runtime, "register_field", None)
        if register:
            register(self)
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, self._set_text)
        return edit

    def _set_text(self, value: Any) -> None:
        """state → 控件。**必须压住回声**。

        ``QPlainTextEdit.setPlainText`` 在部分 Qt 版本下即使内容没变也会发
        ``textChanged``（它总是先清空再插入）。于是 state → setPlainText →
        textChanged → 推回 state → 监听器又 setPlainText …… 直接撞穿递归深度，
        而且异常扔在 Qt 事件循环里，用户侧只看到界面突然卡死。
        """
        assert isinstance(self.widget, QPlainTextEdit)
        self._suppress = True
        try:
            self.widget.setPlainText(str(resolve_prop_value(value, self.scope, self.runtime)))
        finally:
            self._suppress = False

    def error_text(self) -> str | None:
        assert isinstance(self.widget, QPlainTextEdit)
        text = self.widget.toPlainText()
        if self.opt_bool("required") and not text.strip():
            return self.opt_str("error", "This field is required")
        minimum = self.opt_int("min_length", 0)
        if minimum and len(text) < minimum:
            return self.opt_str("error", f"Minimum length is {minimum}")
        return None


class Scroll(Component):
    is_container = True
    axis = "y"

    def build(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        bg = self.opt_color("bg", "")
        if bg:
            scroll.setStyleSheet(f"QScrollArea {{ background:{bg}; border:none; }}")
        inner = QWidget()
        lay = QHBoxLayout(inner) if self.opt_str("axis", "y") == "x" else QVBoxLayout(inner)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("spacing", self.theme.spacing))
        scroll.setWidget(inner)
        self.widget = scroll
        self.layout = lay
        self._inner = inner
        return scroll


class Web(Component):
    def build(self) -> QWidget:
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            from .errors import RenderError
            raise RenderError("Web component requires PySide6-Addons (pip install PySide6-Addons)", self.element.pos)
        view = QWebEngineView()
        bg = self.opt_color("bg", self.theme.background)
        view.setStyleSheet(f"QWebEngineView {{ background:{bg}; border:none; }}")
        src = resolve_prop_value(self.props.get("src", ""), self.scope, self.runtime)
        html = self.props.get("html", "")
        if isinstance(html, str) and is_template(html):
            html = resolve_prop_value(html, self.scope, self.runtime)
        if src:
            from PySide6.QtCore import QUrl
            view.setUrl(QUrl(str(src)))
        elif html:
            view.setHtml(str(html))
        self.widget = view
        self._view = view
        return view


BUILTINS: dict[str, type[Component]] = {
    "Window": Window,
    "Column": Column,
    "Row": Row,
    "Grid": Grid,
    "Text": Text,
    "Button": Button,
    "Input": Input,
    "Checkbox": Checkbox,
    "Divider": Divider,
    "Spacer": Spacer,
    "Slider": Slider,
    "Progress": Progress,
    "Select": Select,
    "Dialog": Dialog,
    "Menu": Menu,
    "Form": Form,
    "Tabs": Tabs,
    "Image": Image,
    "Tooltip": Tooltip,
    "TextArea": TextArea,
    "Scroll": Scroll,
    "Web": Web,
}
