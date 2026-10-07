"""PawUI 组件库第二批：表单、数据、展示、媒体、绘图。

第一批在 ``components.py``（容器 / 文本 / 按钮 / 输入 / 下拉 / 进度……），
这里放的是 0.1.3 补上的那一堆，让「HTML 能做的 PawUI 也能做」不只是口号：

* 表单类：``RadioGroup`` / ``Radio`` / ``Segmented`` / ``NumberInput`` /
  ``DatePicker`` / ``TimePicker`` / ``FilePicker``
* 展示类：``Badge`` / ``Avatar`` / ``Skeleton`` / ``Spinner`` / ``Link`` /
  ``CodeBlock`` / ``Markdown``
* 结构类：``Accordion`` / ``Panel`` / ``SplitPane`` / ``List``
* 数据类：``Table``
* 绘图类：``Canvas``（QPainter 直绘，PythonScript 里拿画笔自己画）
* 杂项：``Shortcut``

最后 ``BUILTINS`` 把两批合并成一张注册表，``runtime`` 只认这一个。
"""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QDate, QDateTime, Qt, QTime, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QDateTimeEdit,
    QDial,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from .components import (
    BUILTINS as _BASE_BUILTINS,
)
from .components import (
    Column,
    Component,
    Container,
    _as_item_list,
    _blend,
    _style_flat_button,
)
from .errors import RenderError
from .resolve import (
    collect_refs,
    is_template,
    resolve_handler,
    resolve_prop_value,
    resolve_raw,
)


def _tag(widget: QWidget, name: str) -> None:
    widget.setProperty("pw-tag", name)


def _mono_font(size: int) -> QFont:
    font = QFont("Cascadia Mono")
    if not font.exactMatch():
        font = QFont("Consolas")
    font.setPointSize(max(7, size - 1))
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class Radio(Component):
    """单选按钮。单独写就是个孤立的按钮，配 ``<RadioGroup>`` 才有互斥。"""

    def value_name(self) -> str:
        explicit = self.opt_str("value", "")
        return explicit or self.resolved_content()

    def build(self) -> QRadioButton:
        button = QRadioButton(self.resolved_content())
        button.setProperty("pw-value", self.value_name())
        button.setChecked(self.opt_bool("checked", False))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        accent = self.opt_color("accent", self.theme.accent)
        button.setStyleSheet(
            f"QRadioButton {{ color:{self.opt_color('fg', self.theme.text)};"
            f" font-size:{self.opt_size()}px; spacing:8px; }}"
            f"QRadioButton::indicator {{ width:16px; height:16px; border-radius:9px;"
            f" border:2px solid {self.theme.border}; background:{self.theme.surface}; }}"
            f"QRadioButton::indicator:checked {{ border:5px solid {accent};"
            f" background:{self.theme.surface}; }}"
        )
        self.widget = button
        return button


class RadioGroup(Container):
    """互斥选项组：子节点写 ``<Radio value="a">A</Radio>``。"""

    def build(self) -> QWidget:
        box = super().build()
        self._group = QButtonGroup(box)
        self._group.setExclusive(True)
        return box

    def add_child(self, child: Component, index: int) -> None:
        widget = child.placement()
        if isinstance(widget, QAbstractButton):
            self._group.addButton(widget, index)
        self.layout.addWidget(widget, child.stretch())

    def finish_children(self) -> None:
        if hasattr(self.layout, "addStretch"):
            self.layout.addStretch(1)
        handler = resolve_handler(self.props.get("on_change"), self.scope, self.runtime)
        bind = self._bind_key()
        if handler or bind:
            self._group.idClicked.connect(
                lambda index: self._picked(index, handler, bind)
            )
        wanted = self.opt_str("value", "")
        if wanted:
            self._check_value(wanted)
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            for name in collect_refs(value, self.scope, self.runtime):
                self.watch_state(
                    name,
                    lambda _: self._check_value(
                        str(resolve_prop_value(value, self.scope, self.runtime))
                    ),
                )

    def _check_value(self, wanted: str) -> None:
        for button in self._group.buttons():
            if str(button.property("pw-value")) == wanted:
                button.setChecked(True)
                return

    def _picked(self, index: int, handler: Any, bind: str) -> None:
        button = self._group.button(index)
        if button is None:
            return
        value = str(button.property("pw-value"))
        if handler:
            self.runtime.invoke(handler, value)
        if bind:
            self._push_state(bind, value)


class Segmented(Component):
    """分段控件（iOS 那种）：一排互斥的小按钮，比下拉框顺手。"""

    def build(self) -> QWidget:
        box = QWidget()
        box.setProperty("pw-tag", "Segmented")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(3)
        radius = self.opt_int("radius", self.theme.radius_sm)
        items = [str(v) for v in _as_item_list(resolve_raw(self.props.get("items", []), self.scope, self.runtime))]
        value = self.opt_str("value", "")
        group = QButtonGroup(box)
        group.setExclusive(True)
        self._group = group
        self._buttons: dict[str, QPushButton] = {}
        theme = self.theme
        for index, label in enumerate(items):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            _style_flat_button(
                button, theme, theme.surface, theme.text, radius, self.opt_size()
            )
            button.setChecked(label == value or (not value and index == 0))
            button.setStyleSheet(
                button.styleSheet()
                + f"""
                QPushButton:checked {{ background-color:{theme.accent}; color:{theme.background}; }}
                QPushButton {{ min-height:26px; padding:0 12px; }}
                """
            )
            group.addButton(button, index)
            lay.addWidget(button)
            self._buttons[label] = button
        box.setStyleSheet(
            f"QWidget[pw-tag=\"Segmented\"] {{ background-color:{theme.background};"
            f" border-radius:{radius + self.theme.space_xs}px; }}"
        )
        handler = resolve_handler(self.props.get("on_change"), self.scope, self.runtime)
        bind = self._bind_key()
        if handler or bind:
            group.idClicked.connect(lambda index: self._picked(index, items, handler, bind))
        box.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.widget = box
        return box

    def _picked(self, index: int, items: list[str], handler: Any, bind: str) -> None:
        if index < 0 or index >= len(items):
            return
        value = items[index]
        if handler:
            self.runtime.invoke(handler, value)
        if bind:
            self._push_state(bind, value)


class NumberInput(Component):
    """数字输入框（带上下微调）。``decimals`` 大于 0 时切成小数输入。"""

    def build(self) -> QSpinBox:
        box = QSpinBox()
        box.setRange(self.opt_int("min", 0), self.opt_int("max", 999999))
        box.setSingleStep(self.opt_int("step", 1))
        box.setValue(self.opt_int("value", self.opt_int("min", 0)))
        box.setStyleSheet(
            f"QSpinBox {{ background-color:{self.theme.surface}; color:{self.theme.text};"
            f" border:1px solid {self.theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px;"
            f" padding:6px 10px; font-size:{self.opt_size()}px; }}"
            f"QSpinBox:focus {{ border:2px solid {self.theme.accent}; }}"
        )
        handler = resolve_handler(self.props.get("on_change"), self.scope, self.runtime)
        if handler:
            box.valueChanged.connect(lambda value: self.runtime.invoke(handler, value))
        bind = self._bind_key()
        if bind:
            self._suppress = False
            box.valueChanged.connect(lambda value: self._push_state(bind, value))
        self.widget = box
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, lambda v: box.setValue(int(resolve_prop_value(v, self.scope, self.runtime))))
        return box


class DatePicker(Component):
    """日期选择器。``value`` 用 ISO 字符串（``2026-09-27``）。"""

    def build(self) -> QWidget:
        from PySide6.QtWidgets import QDateEdit

        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat(self.opt_str("format", "yyyy-MM-dd"))
        raw = self.opt_str("value", "")
        date = QDate.fromString(raw, "yyyy-MM-dd")
        edit.setDate(date if date.isValid() else QDate.currentDate())
        edit.setStyleSheet(
            f"QDateEdit {{ background-color:{self.theme.surface}; color:{self.theme.text};"
            f" border:1px solid {self.theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px;"
            f" padding:6px 10px; font-size:{self.opt_size()}px; }}"
        )
        handler = resolve_handler(self.props.get("on_change"), self.scope, self.runtime)
        if handler:
            edit.dateChanged.connect(
                lambda date: self.runtime.invoke(handler, date.toString("yyyy-MM-dd"))
            )
        bind = self._bind_key()
        if bind:
            self._suppress = False
            edit.dateChanged.connect(
                lambda date: self._push_state(bind, date.toString("yyyy-MM-dd"))
            )
        self.widget = edit
        return edit


class TimePicker(Component):
    """时间选择器。``value`` 用 ``HH:mm``。"""

    def build(self) -> QWidget:
        from PySide6.QtWidgets import QTimeEdit

        edit = QTimeEdit()
        edit.setDisplayFormat(self.opt_str("format", "HH:mm"))
        time = QTime.fromString(self.opt_str("value", ""), "HH:mm")
        edit.setTime(time if time.isValid() else QTime.currentTime())
        edit.setStyleSheet(
            f"QTimeEdit {{ background-color:{self.theme.surface}; color:{self.theme.text};"
            f" border:1px solid {self.theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px;"
            f" padding:6px 10px; font-size:{self.opt_size()}px; }}"
        )
        handler = resolve_handler(self.props.get("on_change"), self.scope, self.runtime)
        if handler:
            edit.timeChanged.connect(
                lambda time: self.runtime.invoke(handler, time.toString("HH:mm"))
            )
        self.widget = edit
        return edit


class FilePicker(Component):
    """选文件 / 选目录 / 保存文件：一个按钮 + 系统对话框，选完把路径交给 handler。"""

    def build(self) -> QPushButton:
        label = self.opt_str("label", self.resolved_content() or "选择文件…")
        button = QPushButton(label)
        theme = self.theme
        _style_flat_button(
            button, theme, self.opt_color("bg", theme.surface),
            self.opt_color("fg", theme.text), self.opt_int("radius", self.theme.radius_md), self.opt_size(),
        )
        handler = resolve_handler(self.props.get("on_pick"), self.scope, self.runtime)
        button.clicked.connect(lambda: self._pick(handler))
        self.widget = button
        self._button = button
        return button

    def _pick(self, handler: Any) -> None:
        mode = self.opt_str("mode", "open").strip().lower()
        filters = self.opt_str("filter", "All files (*)")
        start = self.opt_str("start", "")
        picked = ""
        if mode in ("dir", "directory", "folder"):
            picked = QFileDialog.getExistingDirectory(self._button, self.opt_str("title", "选择目录"), start)
        elif mode in ("save", "write"):
            picked, _ = QFileDialog.getSaveFileName(self._button, self.opt_str("title", "保存文件"), start, filters)
        else:
            picked, _ = QFileDialog.getOpenFileName(self._button, self.opt_str("title", "选择文件"), start, filters)
        if not picked:
            return
        if handler:
            self.runtime.invoke(handler, picked)
        bind = self._bind_key()
        if bind:
            self._push_state(bind, picked)


class Badge(Component):
    """小标签 / 状态点：``<Badge text="NEW" bg="danger"/>``。"""

    def build(self) -> QLabel:
        label = QLabel(self.opt_str("text", self.resolved_content()))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme = self.theme
        bg = self.opt_color("bg", theme.accent)
        fg = self.opt_color("fg", theme.background)
        label.setStyleSheet(
            f"QLabel {{ background-color:{bg}; color:{fg};"
            f" border-radius:{self.opt_int('radius', self.theme.radius_sm)}px;"
            f" padding:2px 9px; font-size:{self.opt_int('size', theme.font_size - 1)}px;"
            f" font-weight:600; }}"
        )
        label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.widget = label
        return label


class _AvatarWidget(QWidget):
    """圆形头像：有图就裁圆，没图就用首字母 + 底色。"""

    def __init__(self, size: int, initials: str, bg: str, fg: str):
        super().__init__()
        self._size = size
        self._initials = initials
        self._bg = QColor(bg)
        self._fg = QColor(fg)
        self._pixmap: QPixmap | None = None
        self.setFixedSize(size, size)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self._size * 2,
            self._size * 2,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmap = scaled
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, self._size, self._size)
        painter.setClipPath(path)
        if self._pixmap is not None:
            painter.drawPixmap(0, 0, self._pixmap)
        else:
            painter.fillRect(self.rect(), self._bg)
            painter.setPen(self._fg)
            font = painter.font()
            font.setPointSize(max(8, self._size // 3))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._initials)


class Avatar(Component):
    owns_size = True

    def build(self) -> _AvatarWidget:
        widget = _AvatarWidget(
            self.opt_int("size", 40),
            self.opt_str("initials", self.resolved_content()[:2].upper()),
            self.opt_color("bg", self.theme.accent),
            self.opt_color("fg", self.theme.background),
        )
        src = self.opt_str("src", "")
        if src:
            pixmap = QPixmap(src)
            if pixmap.isNull():
                raise RenderError(f"avatar image not found: {src}", self.element.pos)
            widget.set_pixmap(pixmap)
        self.widget = widget
        return widget


class _SkeletonWidget(QWidget):
    """骨架屏：一块会呼吸的灰条，加载时占位用。"""

    def __init__(self, color: str, radius: int):
        super().__init__()
        self._color = QColor(color)
        self._radius = radius
        self._alpha = 255
        self._timer: QTimer | None = None

    def start(self) -> None:
        if self._timer is not None:
            return
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._timer.start(40)

    def _pulse(self) -> None:
        self._alpha = 120 if self._alpha > 200 else 240
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlpha(self._alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)


class Skeleton(Component):
    owns_size = True

    def build(self) -> _SkeletonWidget:
        widget = _SkeletonWidget(
            self.opt_color("bg", self.theme.border), self.opt_int("radius", self.theme.radius_sm)
        )
        widget.setFixedSize(
            self.opt_int("width", 120),
            self.opt_int("height", self.opt_int("size", 12)),
        )
        if self.opt_bool("animate", True):
            widget.start()
        self.widget = widget
        return widget


class _SpinnerWidget(QWidget):
    """转圈加载指示器（自绘，不依赖 GIF）。"""

    def __init__(self, size: int, color: str, width: float):
        super().__init__()
        self._size = size
        self._color = QColor(color)
        self._width = width
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spin)
        self._timer.start(28)

    def _spin(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._size / 2, self._size / 2)
        painter.rotate(self._angle)
        pen = QPen(self._color, self._width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = self._size / 2 - self._width
        painter.drawArc(
            int(-rect), int(-rect), int(rect * 2), int(rect * 2), 0, 280 * 16
        )


class Spinner(Component):
    owns_size = True

    def build(self) -> _SpinnerWidget:
        widget = _SpinnerWidget(
            self.opt_int("size", 22),
            self.opt_color("color", self.theme.accent),
            float(self.opt_int("thickness", 3)),
        )
        self.widget = widget
        return widget


class Link(Component):
    """可点文字链接：``<Link href="https://…">官网</Link>``。"""

    def build(self) -> QLabel:
        href = self.opt_str("href", "#")
        label = QLabel(f'<a href="{href}" style="color:{self.opt_color("fg", self.theme.accent)};'
                       f' text-decoration:none;">{self.resolved_content()}</a>')
        label.setOpenExternalLinks(self.opt_bool("external", True))
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        label.setStyleSheet(f"QLabel {{ font-size:{self.opt_size()}px; }}")
        handler = resolve_handler(self.props.get("on_click"), self.scope, self.runtime)
        if handler:
            label.linkActivated.connect(lambda _url: self.runtime.invoke(handler, href))
        self.widget = label
        return label


class CodeBlock(Component):
    """代码块：等宽字体、可选中、可选行号。"""

    def build(self) -> QPlainTextEdit:
        edit = QPlainTextEdit(self.resolved_content())
        edit.setReadOnly(True)
        edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        edit.setFont(_mono_font(self.opt_size()))
        if self.opt_bool("numbers", False):
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lines = self.resolved_content().rstrip("\n").count("\n") + 1
        edit.setFixedHeight(self.opt_int("height", min(360, 18 * lines + 20)))
        edit.setStyleSheet(
            f"QPlainTextEdit {{ background-color:{self.opt_color('bg', self.theme.background)};"
            f" color:{self.opt_color('fg', self.theme.text)};"
            f" border:1px solid {self.theme.border};"
            f" border-radius:{self.opt_int('radius', self.theme.radius_md)}px; padding:10px 12px; }}"
        )
        self.widget = edit
        return edit


def mini_markdown(text: str) -> str:
    """极简 Markdown → HTML（Qt 的富文本只吃 HTML 子集，够用就行）。"""
    import html as _html

    out: list[str] = []
    in_code = False
    in_list = False
    for raw in (text or "").split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if in_list:
                out.append("</ul>")
                in_list = False
            if in_code:
                out.append("</pre>")
            else:
                out.append('<pre style="background:#00000010;">')
            in_code = not in_code
            continue
        if in_code:
            out.append(_html.escape(line) or "&nbsp;")
            continue
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<br/>")
            continue
        if re.match(r"^-{3,}$", stripped):
            out.append("<hr/>")
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(heading.group(1))
            size = max(12, 22 - (level - 1) * 2)
            out.append(f'<div style="font-size:{size}px; font-weight:600;">{_inline(heading.group(2))}</div>')
            continue
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped) or re.match(r"^\d+\.\s+(.*)$", stripped)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(bullet.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if stripped.startswith("&gt;") or stripped.startswith(">"):
            out.append(f"<blockquote>{_inline(stripped.lstrip('> '))}</blockquote>")
        else:
            out.append(f"<div>{_inline(stripped)}</div>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "".join(out)


def _inline(text: str) -> str:
    """行内标记：粗体 / 斜体 / 行内代码 / 链接。"""
    text = re.sub(r"`([^`]+)`",
                  r'<code style="background:#00000012;">\1</code>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


class Markdown(Component):
    """Markdown 渲染（``{$doc}`` 直接丢进来就行）。"""

    def build(self) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setOpenExternalLinks(True)
        label.setText(mini_markdown(self.resolved_content()))
        label.setStyleSheet(
            f"QLabel {{ color:{self.opt_color('fg', self.theme.text)};"
            f" font-size:{self.opt_size()}px; }}"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.widget = label
        content = self.props.get("__content__", "")
        if isinstance(content, str) and is_template(content):
            self.bind_state(
                content, lambda v: label.setText(mini_markdown(str(v)))
            )
        return label


class Panel(Component):
    """可折叠面板：``<Panel title="高级设置">…</Panel>``。"""

    is_container = True

    def build(self) -> QWidget:
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QToolButton()
        header.setCheckable(True)
        header.setChecked(self.opt_bool("open", False))
        header.setText(("▾  " if header.isChecked() else "▸  ") + self.opt_str("title", "Panel"))
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(
            f"QToolButton {{ background-color:{self.opt_color('bg', self.theme.surface)};"
            f" color:{self.theme.text}; border:none; padding:10px 12px;"
            f" font-size:{self.opt_size()}px; font-weight:600; text-align:left;"
            f" border-radius:{self.opt_int('radius', self.theme.radius_md)}px; }}"
            f"QToolButton:hover {{ background-color:{self.theme.hover}; }}"
        )
        self._header = header
        body = QWidget()
        lay = QVBoxLayout(body)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("spacing", self.theme.spacing))
        body.setVisible(header.isChecked())
        self._body = body
        outer.addWidget(header)
        outer.addWidget(body)
        header.toggled.connect(self._toggle)
        apply_shadow(box, self.theme, self.opt_bool("shadow", bool(self.theme.shadow)))
        self.widget = box
        self.layout = lay
        return box

    def _toggle(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self._header.setText(
            ("▾  " if checked else "▸  ") + self.opt_str("title", "Panel")
        )
        handler = resolve_handler(self.props.get("on_toggle"), self.scope, self.runtime)
        if handler:
            self.runtime.invoke(handler, checked)

    def finish_children(self) -> None:
        # Panel 是 Component 而不是 Container（身体自己管），所以手动补弹簧
        if hasattr(self.layout, "addStretch"):
            self.layout.addStretch(1)


class Accordion(Container):
    """手风琴：装一组 ``<Panel>``；``multiple="false"`` 时同时只开一个。"""

    def finish_children(self) -> None:
        Column.finish_children(self)
        if self.opt_bool("multiple", True):
            return
        panels = [child for child in self._children if isinstance(child, Panel)]
        for panel in panels:
            panel._header.toggled.connect(
                lambda checked, opened=panel: self._exclusive(opened, checked)
            )
        # 初始状态也要守着：文件里给多个 Panel 写了 open="true" 时只留第一个
        for panel in panels[1:]:
            if panel._header.isChecked():
                panel._header.setChecked(False)

    def _exclusive(self, opened: Panel, checked: bool) -> None:
        if not checked:
            return
        for child in self._children:
            if isinstance(child, Panel) and child is not opened:
                child._header.setChecked(False)


class SplitPane(Component):
    """可拖拽分栏：两个子节点，``ratio`` 控制初始比例。"""

    is_container = True

    def build(self) -> QSplitter:
        splitter = QSplitter(
            Qt.Orientation.Horizontal
            if self.opt_str("axis", "x") == "x"
            else Qt.Orientation.Vertical
        )
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(self.opt_int("handle", 6))
        self.widget = splitter
        self.layout = None  # 子节点直接挂到 splitter 上
        return splitter

    def add_child(self, child: Component, index: int) -> None:
        placement = child.placement()
        if placement is not None and self.widget is not None:
            self.widget.addWidget(placement)  # type: ignore[attr-defined]

    def finish_children(self) -> None:
        splitter = self.widget
        if splitter is None or splitter.count() < 2:  # type: ignore[attr-defined]
            return
        total = self.opt_int("width", 0) or self.opt_int("size", 600)
        ratio = float(self.opt_str("ratio", "0.5") or 0.5)
        first = int(total * ratio)
        splitter.setSizes([first, max(1, total - first)])  # type: ignore[attr-defined]


class List(Component):
    """可选列表：``<List items="{$rows}" value="{$picked}" on_select="fn"/>``。"""

    def build(self) -> QListWidget:
        view = QListWidget()
        view.setStyleSheet(
            f"QListWidget {{ background-color:{self.opt_color('bg', self.theme.surface)};"
            f" color:{self.theme.text}; border:1px solid {self.theme.border};"
            f" border-radius:{self.opt_int('radius', self.theme.radius_md)}px; padding:4px;"
            f" font-size:{self.opt_size()}px; outline:none; }}"
            f"QListWidget::item {{ padding:7px 10px; border-radius:{self.theme.radius_sm}px; }}"
            f"QListWidget::item:selected {{ background-color:{self.theme.accent};"
            f" color:{self.theme.background}; }}"
            f"QListWidget::item:hover {{ background-color:{self.theme.hover}; }}"
        )
        view.setFixedHeight(self.opt_int("height", 180))
        self._set_items(view, resolve_raw(self.props.get("items", []), self.scope, self.runtime))
        wanted = self.opt_str("value", "")
        if wanted:
            self._select(view, wanted)
        handler = resolve_handler(self.props.get("on_select"), self.scope, self.runtime)
        bind = self._bind_key()
        if handler or bind:
            view.itemClicked.connect(lambda item: self._picked(item, handler, bind))
        items = self.props.get("items", None)
        if isinstance(items, str) and is_template(items):
            for name in collect_refs(items, self.scope, self.runtime):
                self.watch_state(
                    name,
                    lambda _: self._set_items(
                        view, resolve_raw(items, self.scope, self.runtime)
                    ),
                )
        self.widget = view
        return view

    @staticmethod
    def _set_items(view: QListWidget, items: Any) -> None:
        current = view.currentItem().text() if view.currentItem() is not None else ""
        view.clear()
        for item in _as_item_list(items):
            view.addItem(QListWidgetItem(str(item)))
        if current:
            List._select(view, current)

    @staticmethod
    def _select(view: QListWidget, wanted: str) -> None:
        for index in range(view.count()):
            item = view.item(index)
            if item is not None and item.text() == wanted:
                view.setCurrentItem(item)
                return

    def _picked(self, item: QListWidgetItem, handler: Any, bind: str) -> None:
        if handler:
            self.runtime.invoke(handler, item.text())
        if bind:
            self._push_state(bind, item.text())


def _cell_text(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return ""
    return str(value)


def _row_values(row: Any, columns: list[str]) -> list[str]:
    """一行数据既可以是 list/tuple，也可以是 dict（按列名取值）。"""
    if isinstance(row, dict):
        return [_cell_text(row.get(column, "")) for column in columns]
    if isinstance(row, (list, tuple)):
        return [_cell_text(v) for v in row]
    return [_cell_text(row)]


def _parse_rows(value: Any) -> list:
    """``rows`` 支持三种写法：state 引用（已经是 list）、JSON 字符串、逗号分隔。"""
    import json

    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return [[part.strip()] for part in text.strip("[]").split(",") if part.strip()]
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    return []


class Table(Component):
    """数据表格：列头、排序、行选择，``rows`` 支持 ``[{"name": …}, …]``。"""

    def build(self) -> QTableWidget:
        columns = [str(c) for c in _as_item_list(self.props.get("columns", []))]
        rows = _parse_rows(resolve_raw(self.props.get("rows", []), self.scope, self.runtime))
        table = QTableWidget()
        self._columns = columns
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        self._fill(table, rows)
        table.setSortingEnabled(self.opt_bool("sortable", True))
        table.verticalHeader().setVisible(self.opt_bool("index", False))
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(self.opt_bool("striped", True))
        table.setFixedHeight(self.opt_int("height", 240))
        self._style_table(table)
        handler = resolve_handler(self.props.get("on_select"), self.scope, self.runtime)
        if handler:
            table.itemSelectionChanged.connect(lambda: self._row_picked(table, handler))
        rows_prop = self.props.get("rows", None)
        if isinstance(rows_prop, str) and is_template(rows_prop):
            for name in collect_refs(rows_prop, self.scope, self.runtime):
                self.watch_state(
                    name,
                    lambda _: self._fill(
                        table,
                        _parse_rows(resolve_raw(rows_prop, self.scope, self.runtime)),
                    ),
                )
        self.widget = table
        return table

    def _style_table(self, table: QTableWidget) -> None:
        theme = self.theme
        radius = self.opt_int("radius", self.theme.radius_md)
        # 斑马纹行必须显式给色：Qt 默认落回 QPalette::AlternateBase（平台浅色 #f7f7f7），
        # 在深色主题下会变成「白底白字」。用 surface/background 之间的插值。
        alternate = _blend(theme.surface, theme.background, 0.5)
        table.setStyleSheet(
            f"QTableWidget {{ background-color:{theme.surface}; color:{theme.text};"
            f" alternate-background-color:{alternate};"
            f" gridline-color:{theme.border}; border:1px solid {theme.border};"
            f" border-radius:{radius}px; font-size:{self.opt_size()}px; outline:none; }}"
            f"QTableWidget::item {{ padding:6px 8px; }}"
            f"QTableWidget::item:selected {{ background-color:{theme.accent};"
            f" color:{theme.background}; }}"
            f"QHeaderView::section {{ background-color:{theme.background}; color:{theme.subtext};"
            f" padding:7px 8px; border:none; border-bottom:1px solid {theme.border};"
            f" font-weight:600; }}"
            f"QTableCornerButton::section {{ background-color:{theme.background}; border:none; }}"
        )

    def _fill(self, table: QTableWidget, rows: list) -> None:
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = _row_values(row, self._columns)
            for c in range(len(self._columns)):
                text = values[c] if c < len(values) else ""
                item = QTableWidgetItem(text)
                if self.opt_bool("sortable", True) and text.replace(".", "", 1).isdigit():
                    item.setData(Qt.ItemDataRole.DisplayRole, float(text))
                table.setItem(r, c, item)
        table.setSortingEnabled(self.opt_bool("sortable", True))

    def _row_picked(self, table: QTableWidget, handler: Any) -> None:
        indexes = table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        values: list[str] = []
        for c in range(table.columnCount()):
            cell = table.item(row, c)
            values.append(cell.text() if cell is not None else "")
        self.runtime.invoke(handler, values)


class Painter:
    """给 PythonScript 用的画笔门面。

    Qt 的 ``QPainter`` 要自己配对 ``setPen`` / ``setBrush``，这里包一层，
    画线画矩形只写一行，参数也按 CSS 的习惯来（颜色在前、宽度可省）。
    """

    __slots__ = ("_p", "_w", "_h")

    def __init__(self, painter: QPainter, width: int, height: int):
        self._p = painter
        self._w = width
        self._h = height

    # -- 尺寸 --
    @property
    def width(self) -> int:
        return self._w

    @property
    def height(self) -> int:
        return self._h

    def size(self) -> tuple[int, int]:
        return (self._w, self._h)

    # -- 颜色 --
    def clear(self, color: str) -> None:
        self._p.fillRect(0, 0, self._w, self._h, QColor(color))

    def pen(self, color: str = "#000000", width: int = 1, dashed: bool = False) -> None:
        pen = QPen(QColor(color), width)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        self._p.setPen(pen)

    def brush(self, color: str | None) -> None:
        self._p.setBrush(Qt.BrushStyle.NoBrush if color is None else QColor(color))

    # -- 图形 --
    def line(self, x1: int, y1: int, x2: int, y2: int,
             color: str = "#000000", width: int = 1) -> None:
        self.pen(color, width)
        self._p.drawLine(int(x1), int(y1), int(x2), int(y2))

    def rect(self, x: int, y: int, w: int, h: int, radius: int = 0,
             fill: str | None = None, stroke: str | None = None,
             width: int = 1) -> None:
        self.brush(fill)
        self.pen(stroke or "#00000000", width)
        if radius:
            self._p.drawRoundedRect(int(x), int(y), int(w), int(h), radius, radius)
        else:
            self._p.drawRect(int(x), int(y), int(w), int(h))

    def circle(self, cx: int, cy: int, r: int,
               fill: str | None = None, stroke: str | None = None,
               width: int = 1) -> None:
        self.brush(fill)
        self.pen(stroke or "#00000000", width)
        self._p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

    def arc(self, cx: int, cy: int, r: int, start: int, span: int,
            color: str = "#000000", width: int = 2) -> None:
        self.pen(color, width)
        self._p.drawArc(
            int(cx - r), int(cy - r), int(r * 2), int(r * 2), int(start * 16), int(span * 16)
        )

    def polygon(self, points: list, fill: str | None = None,
                stroke: str | None = None, width: int = 1) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        self.brush(fill)
        self.pen(stroke or "#00000000", width)
        self._p.drawPolygon(QPolygonF([QPointF(float(x), float(y)) for x, y in points]))

    def text(self, x: int, y: int, text: str, size: int = 12,
             color: str = "#000000", bold: bool = False,
             align: str = "left") -> None:
        font = self._p.font()
        font.setPointSize(max(6, size - 1))
        font.setBold(bold)
        self._p.setFont(font)
        self.pen(color, 1)
        flags = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(str(align).lower(), Qt.AlignmentFlag.AlignLeft)
        self._p.drawText(int(x), int(y) + size, text)
        del flags

    def image(self, src: str, x: int, y: int,
              w: int | None = None, h: int | None = None) -> None:
        pixmap = QPixmap(src)
        if pixmap.isNull():
            return
        if w and h:
            pixmap = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self._p.drawPixmap(int(x), int(y), pixmap)


class _CanvasWidget(QWidget):
    """真正画东西的控件：把 QPainter 包成 Painter 再交给用户的绘制函数。"""

    def __init__(self, width: int, height: int, background: str):
        super().__init__()
        self.setFixedSize(width, height)
        self._background = background
        self._on_draw: Any = None
        self._on_press: Any = None

    def set_handlers(self, on_draw: Any, on_press: Any) -> None:
        self._on_draw = on_draw
        self._on_press = on_press

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._background))
        if self._on_draw is not None:
            try:
                self._on_draw(Painter(painter, self.width(), self.height()))
            except Exception as error:  # noqa: BLE001
                import sys
                print(f"PawUI: canvas draw failed: {error}", file=sys.stderr)
        painter.end()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 (Qt 命名)
        if self._on_press is not None:
            self._on_press(int(event.position().x()), int(event.position().y()))


class Canvas(Component):
    """自绘图区：``<Canvas width="320" height="200" on_draw="paint"/>``。

    在 PythonScript 里定义 ``def paint(p): p.line(...)`` 就行，参数是
    :class:`Painter`，画完调 ``app.query('#cv').widget.update()`` 重画。
    """

    owns_size = True

    def build(self) -> _CanvasWidget:
        widget = _CanvasWidget(
            self.opt_int("width", 320),
            self.opt_int("height", 200),
            self.opt_color("bg", self.theme.surface),
        )
        widget.set_handlers(
            resolve_handler(self.props.get("on_draw"), self.scope, self.runtime),
            resolve_handler(self.props.get("on_press"), self.scope, self.runtime),
        )
        self.widget = widget
        return widget


class VirtualList(Component):
    """只渲染可见行的长列表（真正的虚拟滚动）。

    ``<For>`` 是老老实实把每一行都建成控件 —— 1000 行就是 3000 个 QWidget，
    实测 1.3 秒，滚起来也沉。``<VirtualList>`` 只建视口里那十几行，滚动时
    换掉可见的那一段：行数变成 1 万、10 万，建树时间都是常数。

    ::

        <VirtualList rows="{$rows}" row_height="34" height="420">
          <Row><Text>{$item}</Text><Badge text="{$index}"/></Row>
        </VirtualList>

    行模板是唯一的子元素；``each`` 可以改绑定的变量名（默认 ``item``）。
    """

    is_container = False

    def build(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        self._each = self.opt_str("each", "item") or "item"
        self._row_height = max(8, self.opt_int("row_height", 34))
        self._template = self.element.children[0] if self.element.children else None
        self._rows_built: list[Component] = []
        self._first = -1
        self._count = 0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }}"
            f"QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}"
            f"QScrollBar::handle:vertical {{ background:{self.theme.border};"
            f" border-radius:{self.theme.radius_sm}px; min-height:30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
        )
        content = QWidget()
        content.setProperty("pw-tag", "VirtualContent")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(self.opt_int("gap", 0))
        scroll.setWidget(content)
        scroll.setFixedHeight(self.opt_int("height", 400))
        scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self.widget = scroll
        self._scroll = scroll
        self._content = content
        self._lay = lay
        self._data = self._resolve_rows()
        self._render(0, force=True)
        self._watch_rows()
        return scroll

    # -- 数据 --
    def _resolve_rows(self) -> list:
        rows = resolve_raw(self.props.get("rows", []), self.scope, self.runtime)
        if rows is None:
            return []
        if isinstance(rows, dict):
            return list(rows.items())
        if isinstance(rows, str):
            return [part.strip() for part in rows.split(",") if part.strip()]
        try:
            return list(rows)
        except TypeError:
            return [rows]

    def _watch_rows(self) -> None:
        rows_prop = self.props.get("rows", None)
        if not (isinstance(rows_prop, str) and is_template(rows_prop)):
            return
        for name in collect_refs(rows_prop, self.scope, self.runtime):
            self.watch_state(name, lambda _: self.refresh_rows())

    def refresh_rows(self) -> None:
        """数据变了：重算条数，保持滚动位置不跳。"""
        self._data = self._resolve_rows()
        self._first = -1
        value = self._scroll.verticalScrollBar().value()
        self._render(value // self._row_height, force=True)

    # -- 渲染 --
    def _visible_span(self, first: int) -> tuple[int, int]:
        viewport = max(1, self._scroll.viewport().height() // self._row_height)
        last = min(self._count, first + viewport + 2)
        return first, last

    def _on_scroll(self, value: int) -> None:
        first = max(0, int(value) // self._row_height)
        if abs(first - self._first) >= 1:
            self._render(first)

    def _render(self, first: int, force: bool = False) -> None:
        self._count = len(self._data)
        self._content.setFixedHeight(self._count * self._row_height)
        first = max(0, min(first, max(0, self._count - 1)))
        if not force and first == self._first:
            return
        self._first = first
        for comp in self._rows_built:
            comp.dispose()
            if comp.widget is not None and isValid(comp.widget):
                self._lay.removeWidget(comp.widget)
                comp.widget.setParent(None)
                comp.widget.deleteLater()
        self._rows_built = []
        if self._template is None:
            return
        start, end = self._visible_span(first)
        self._lay.setContentsMargins(0, start * self._row_height, 0,
                                     max(0, (self._count - end) * self._row_height))
        for index in range(start, end):
            scope = dict(self.scope)
            scope[self._each] = self._data[index]
            scope["index"] = index
            comp = self.runtime._build_element(self._template, self, scope)
            comp._children  # 保持引用关系，dispose 时能连带清理
            self._rows_built.append(comp)
            placement = comp.placement() or comp.widget
            if placement is not None:
                self._lay.addWidget(placement)


class Shortcut(Component):
    """快捷键：``<Shortcut keys="Ctrl+S" on_press="save"/>``（不占视觉位置）。"""

    def build(self) -> QWidget:
        holder = QWidget()
        holder.setFixedSize(0, 0)
        keys = self.opt_str("keys", "")
        handler = resolve_handler(self.props.get("on_press"), self.scope, self.runtime)
        if keys and handler:
            shortcut = QShortcut(QKeySequence(keys), holder)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda: self.runtime.invoke(handler))
            self._shortcut = shortcut
        self.widget = holder
        return holder


def apply_shadow(widget: QWidget, theme: Any, enabled: bool | None = None) -> None:
    """给控件加投影（Qt 没有 CSS 的 box-shadow，用 QGraphicsDropShadowEffect 代替）。

    ``enabled`` 为 None 时看 ``theme.shadow``；容器只要不显式关掉就会按主题来。
    注意：一个控件只能挂一个 graphicsEffect，所以这里不做叠加。
    """
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    if enabled is None:
        enabled = bool(getattr(theme, "shadow", False))
    if not enabled:
        return
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(int(getattr(theme, "shadow_blur", 28)))
    effect.setOffset(0, int(getattr(theme, "shadow_offset_y", 6)))
    color = str(getattr(theme, "shadow_color", "#00000033"))
    qc = QColor(color)
    if not qc.isValid():
        # #rrggbbaa 形式 QColor 不认，手动拆 alpha
        try:
            hexpart = color.lstrip("#")
            if len(hexpart) == 8:
                qc = QColor("#" + hexpart[:6])
                qc.setAlpha(int(hexpart[6:8], 16))
            else:
                qc = QColor(0, 0, 0, 51)
        except ValueError:
            qc = QColor(0, 0, 0, 51)
    effect.setColor(qc)
    widget.setGraphicsEffect(effect)


class Alert(Component):
    """行内提示条：``<Alert kind="warning" title="注意">正文</Alert>``。

    ``kind`` 取 info / success / warning / error，条带颜色和图标跟着变。
    比 ``app.toast()`` 安静 —— 它留在页面里，不飘走。
    """

    #: kind -> 图标。颜色取自主题（accent/success/warning/danger），
    #: 与 app.toast() 的 TOAST_COLORS 一一对应，同一种 kind 到哪儿都是一个色。
    GLYPHS = {
        "info": "i",
        "success": "✓",
        "warning": "!",
        "error": "×",
        "danger": "×",
    }

    def build(self) -> QWidget:
        kind = self.opt_str("kind", "info").strip().lower()
        glyph = self.GLYPHS.get(kind, self.GLYPHS["info"])
        token = {"success": "success", "warning": "warning",
                 "error": "danger", "danger": "danger"}.get(kind, "accent")
        accent = self.opt_color("accent", getattr(self.theme, token, self.theme.accent))
        theme = self.theme
        radius = self.opt_int("radius", self.theme.radius_md)

        box = QWidget()
        box.setProperty("pw-tag", "Alert")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)

        icon = QLabel(glyph)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(20, 20)
        icon.setStyleSheet(
            f"QLabel {{ background:{accent}; color:{theme.background};"
            f" border-radius:{self.theme.radius_sm}px; font-weight:700; font-size:12px; }}"
        )
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)
        title = self.opt_str("title", "")
        if title:
            head = QLabel(title)
            head.setStyleSheet(f"color:{theme.text}; font-weight:600; font-size:{self.opt_size(13)}px;")
            head.setWordWrap(True)
            body.addWidget(head)
        text = self.resolved_content().strip() or self.opt_str("text", "")
        if text:
            para = QLabel(text)
            para.setWordWrap(True)
            para.setStyleSheet(f"color:{theme.subtext}; font-size:{self.opt_size(12)}px;")
            body.addWidget(para)
        lay.addLayout(body, 1)

        box.setStyleSheet(
            f"QWidget[pw-tag=\"Alert\"] {{ background-color:{_blend(theme.surface, accent, 0.12)};"
            f" border:1px solid {_blend(theme.surface, accent, 0.45)};"
            f" border-left:3px solid {accent}; border-radius:{radius}px; }}"
        )
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        apply_shadow(box, theme, self.opt_bool("shadow", bool(theme.shadow)) if "shadow" in self.props else None)
        self.widget = box
        return box


class GroupBox(Component):
    """带标题边框的分组容器：``<GroupBox title="高级">…</GroupBox>``。"""

    is_container = True
    axis = "y"

    def build(self) -> QWidget:
        box = QGroupBox(self.opt_str("title", ""))
        lay = QVBoxLayout(box)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left or 12, (top or 10) + 6, right or 12, bottom or 12)
        lay.setSpacing(self.opt_int("gap", self.opt_int("spacing", self.theme.spacing)))
        theme = self.theme
        box.setStyleSheet(
            f"QGroupBox {{ background-color:{self.opt_color('bg', theme.surface)};"
            f" border:1px solid {theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px;"
            f" margin-top:10px; padding-top:6px;"
            f" color:{theme.text}; font-size:{self.opt_size()}px; }}"
            f" QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left;"
            f" left:12px; padding:0 4px; color:{theme.subtext}; font-weight:600; }}"
        )
        self._justify = str(self.opt_str("justify", "start")).strip().lower()
        self._cross_align = str(self.opt_str("align", "start")).strip().lower()
        if self.opt_bool("shadow", False):
            apply_shadow(box, self.theme, True)
        self.widget = box
        self.layout = lay
        return box

    def finish_children(self) -> None:
        if hasattr(self.layout, "addStretch"):
            self.layout.addStretch(1)


class DoubleInput(Component):
    """浮点数输入：``<DoubleInput min="0" max="1" step="0.01" value="{$ratio}"/>``。"""

    def build(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(self.opt_float("min", 0.0), self.opt_float("max", 100.0))
        spin.setSingleStep(self.opt_float("step", 0.1))
        spin.setDecimals(self.opt_int("decimals", 2))
        value = self.props.get("value", None)
        if value is not None:
            try:
                spin.setValue(float(resolve_prop_value(value, self.scope, self.runtime)))
            except (TypeError, ValueError):
                pass
        spin.setReadOnly(self.opt_bool("readonly", False))
        _style_spinbox(spin, self.theme, self.opt_size(), self.opt_int("radius", self.theme.radius_md))
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        if handler:
            spin.valueChanged.connect(
                lambda v: None
                if getattr(self, "_suppress", False)
                else self.runtime.invoke(handler, v)
            )
        bind = self._bind_key()
        if bind:
            self._suppress = False
            spin.valueChanged.connect(lambda v: self._push_state(bind, v))
        if isinstance(value, str) and is_template(value):
            def _set(v: Any) -> None:
                self._suppress = True
                try:
                    spin.setValue(float(resolve_prop_value(v, self.scope, self.runtime)))
                except (TypeError, ValueError):
                    pass
                finally:
                    self._suppress = False
            self.bind_state(value, _set)
        self.widget = spin
        return spin


class DateTimePicker(Component):
    """日期 + 时间：``<DateTimePicker value="{$when}" on_change="on_when"/>``。

    值用 ISO 字符串（``2026-09-27T13:45``），比 ``<DatePicker>`` + ``<TimePicker>``
    少一个控件。
    """

    def build(self) -> QDateTimeEdit:
        edit = QDateTimeEdit()
        fmt = self.opt_str("format", "yyyy-MM-dd HH:mm")
        edit.setDisplayFormat(fmt)
        edit.setCalendarPopup(self.opt_bool("calendar", True))
        raw = self.opt_str("value", "")
        if raw:
            parsed = QDateTime.fromString(raw, Qt.DateFormat.ISODate)
            if not parsed.isValid():
                parsed = QDateTime.fromString(raw, fmt)
            if parsed.isValid():
                edit.setDateTime(parsed)
        _style_dt_edit(edit, self.theme, self.opt_size(), self.opt_int("radius", self.theme.radius_md))
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        if handler:
            edit.dateTimeChanged.connect(
                lambda _v: None
                if getattr(self, "_suppress", False)
                else self.runtime.invoke(handler, edit.dateTime().toString(Qt.DateFormat.ISODate))
            )
        bind = self._bind_key()
        if bind:
            self._suppress = False
            edit.dateTimeChanged.connect(
                lambda _v: self._push_state(bind, edit.dateTime().toString(Qt.DateFormat.ISODate))
            )
        self.widget = edit
        return edit


class Dial(Component):
    """旋钮：``<Dial min="0" max="100" value="{$vol}" on_change="on_vol"/>``。"""

    def build(self) -> QWidget:
        dial = QDial()
        dial.setRange(self.opt_int("min", 0), self.opt_int("max", 100))
        dial.setSingleStep(self.opt_int("step", 1))
        dial.setNotchesVisible(self.opt_bool("notches", True))
        dial.setValue(self.opt_int("value", 0))
        size = self.opt_int("size", 64)
        dial.setFixedSize(size, size)
        theme = self.theme
        dial.setStyleSheet(
            f"QDial {{ background-color:{theme.surface}; }}"
        )
        label = None
        if self.opt_bool("text", False):
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(4)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(dial, 0, Qt.AlignmentFlag.AlignCenter)
            label = QLabel(str(dial.value()))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(f"color:{theme.subtext}; font-size:{self.opt_size(12)}px;")
            lay.addWidget(label)
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        if handler or label is not None:
            def _on(v: int) -> None:
                if label is not None:
                    label.setText(str(v))
                if handler and not getattr(self, "_suppress", False):
                    self.runtime.invoke(handler, v)
            dial.valueChanged.connect(_on)
        bind = self._bind_key()
        if bind:
            self._suppress = False
            dial.valueChanged.connect(lambda v: self._push_state(bind, v))
        self.widget = box if label is not None else dial
        return self.widget


class LCD(Component):
    """数字显示：``<LCD value="{$count}" digits="4"/>``。"""

    def build(self) -> QLCDNumber:
        lcd = QLCDNumber(self.opt_int("digits", 4))
        lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        theme = self.theme
        color = self.opt_color("color", theme.accent)
        lcd.setStyleSheet(f"QLCDNumber {{ background-color:{theme.surface}; color:{color};"
                          f" border:1px solid {theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px; }}")
        try:
            lcd.display(int(self.opt_int("value", 0)))
        except (TypeError, ValueError):
            lcd.display(0)
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            def _set(v: Any) -> None:
                try:
                    lcd.display(int(resolve_prop_value(v, self.scope, self.runtime)))
                except (TypeError, ValueError):
                    pass
            self.bind_state(value, _set)
        self.widget = lcd
        return lcd


class ColorPicker(Component):
    """颜色选择：``<ColorPicker value="{$color}" on_change="on_color"/>``。

    显示一个色块，点开是系统取色器；值用 ``#rrggbb``。
    """

    def build(self) -> QPushButton:
        button = QPushButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        size = self.opt_int("size", 34)
        radius = self.opt_int("radius", self.theme.radius_md)
        button.setFixedSize(size * 2, size)
        self._color = self.opt_str("value", "#ffffff") or "#ffffff"
        theme = self.theme
        button.setStyleSheet(
            f"QPushButton {{ background:{self._color}; border:1px solid {theme.border};"
            f" border-radius:{radius}px; }}"
            f"QPushButton:hover {{ border-color:{theme.accent}; }}"
        )
        handler = resolve_handler(self.props.get("on_change", None), self.scope, self.runtime)
        bind = self._bind_key()

        def _pick() -> None:
            chosen = QColorDialog.getColor(QColor(self._color), button, self.opt_str("title", ""))
            if not chosen.isValid():
                return
            self._apply(chosen.name())
            if handler:
                self.runtime.invoke(handler, chosen.name())
            if bind:
                self._push_state(bind, chosen.name())

        button.clicked.connect(_pick)
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, lambda v: self._apply(str(resolve_prop_value(v, self.scope, self.runtime))))
        self.widget = button
        return button

    def _apply(self, value: str) -> None:
        self._color = value or "#ffffff"
        theme = self.theme
        radius = self.opt_int("radius", self.theme.radius_md)
        assert isinstance(self.widget, QPushButton)
        self.widget.setStyleSheet(
            f"QPushButton {{ background:{self._color}; border:1px solid {theme.border};"
            f" border-radius:{radius}px; }}"
            f"QPushButton:hover {{ border-color:{theme.accent}; }}"
        )


class Tree(Component):
    """树形列表：``<Tree items="{$nodes}" on_select="on_pick"/>``。

    ``items`` 接受嵌套结构：``[{"label": "根", "items": [...]}]``，
    也接受扁平字符串列表（都挂在顶层）。
    """

    def build(self) -> QTreeWidget:
        tree = QTreeWidget()
        headers = self.opt_str("headers", "")
        if headers:
            tree.setHeaderLabels([h.strip() for h in headers.split(",")])
        else:
            tree.setHeaderHidden(True)
        tree.setIndentation(self.opt_int("indent", 16))
        height = self.opt_int("height", 0)
        if height:
            tree.setFixedHeight(height)
        theme = self.theme
        tree.setStyleSheet(
            f"QTreeWidget {{ background-color:{theme.surface}; color:{theme.text};"
            f" border:1px solid {theme.border}; border-radius:{self.opt_int('radius', self.theme.radius_md)}px;"
            f" font-size:{self.opt_size()}px; outline:none; }}"
            f"QTreeWidget::item {{ padding:5px 4px; }}"
            f"QTreeWidget::item:selected {{ background-color:{theme.accent}; color:{theme.background}; }}"
            f"QHeaderView::section {{ background-color:{theme.background}; color:{theme.subtext};"
            f" padding:6px 8px; border:none; border-bottom:1px solid {theme.border}; font-weight:600; }}"
        )
        self._fill(tree, resolve_raw(self.props.get("items", []), self.scope, self.runtime))
        handler = resolve_handler(self.props.get("on_select", None), self.scope, self.runtime)
        bind = self._bind_key()
        if handler or bind:
            tree.itemSelectionChanged.connect(lambda: self._picked(tree, handler, bind))
        items_prop = self.props.get("items", None)
        if isinstance(items_prop, str) and is_template(items_prop):
            for name in collect_refs(items_prop, self.scope, self.runtime):
                self.watch_state(
                    name,
                    lambda _: self._fill(tree, resolve_raw(items_prop, self.scope, self.runtime)),
                )
        self.widget = tree
        return tree

    @staticmethod
    def _fill(tree: QTreeWidget, items: Any) -> None:
        tree.clear()
        def add(parent: Any, nodes: Any) -> None:
            if not isinstance(nodes, (list, tuple)):
                return
            for node in nodes:
                if isinstance(node, dict):
                    label = str(node.get("label", node.get("text", "")))
                    children = node.get("items", node.get("children", []))
                else:
                    label, children = str(node), []
                item = QTreeWidgetItem([label])
                if parent is None:
                    tree.addTopLevelItem(item)
                else:
                    parent.addChild(item)
                add(item, children)
        add(None, items)
        tree.expandAll()

    def _picked(self, tree: QTreeWidget, handler: Any, bind: str) -> None:
        selected = tree.selectedItems()
        if not selected:
            return
        text = selected[0].text(0)
        if handler:
            self.runtime.invoke(handler, text)
        if bind:
            self._push_state(bind, text)


def _style_spinbox(spin: QDoubleSpinBox, theme: Any, font_size: int, radius: int) -> None:
    spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
    spin.setStyleSheet(
        f"QDoubleSpinBox {{ background-color:{theme.surface}; color:{theme.text};"
        f" border:1px solid {theme.border}; border-radius:{radius}px;"
        f" padding:6px 8px; font-size:{font_size}px; }}"
        f"QDoubleSpinBox:focus {{ border:2px solid {theme.accent}; }}"
    )


def _style_dt_edit(edit: QDateTimeEdit, theme: Any, font_size: int, radius: int) -> None:
    edit.setStyleSheet(
        f"QDateTimeEdit {{ background-color:{theme.surface}; color:{theme.text};"
        f" border:1px solid {theme.border}; border-radius:{radius}px;"
        f" padding:6px 8px; font-size:{font_size}px; }}"
        f"QDateTimeEdit:focus {{ border:2px solid {theme.accent}; }}"
        f"QDateTimeEdit::drop-down {{ border:none; width:18px; }}"
    )


EXTRA_BUILTINS: dict[str, type[Component]] = {
    "Radio": Radio,
    "RadioGroup": RadioGroup,
    "Segmented": Segmented,
    "NumberInput": NumberInput,
    "DatePicker": DatePicker,
    "TimePicker": TimePicker,
    "FilePicker": FilePicker,
    "Badge": Badge,
    "Avatar": Avatar,
    "Skeleton": Skeleton,
    "Spinner": Spinner,
    "Link": Link,
    "CodeBlock": CodeBlock,
    "Markdown": Markdown,
    "Panel": Panel,
    "Accordion": Accordion,
    "SplitPane": SplitPane,
    "List": List,
    "Table": Table,
    "Canvas": Canvas,
    "VirtualList": VirtualList,
    "Shortcut": Shortcut,
    "Alert": Alert,
    "GroupBox": GroupBox,
    "DoubleInput": DoubleInput,
    "DateTimePicker": DateTimePicker,
    "Dial": Dial,
    "LCD": LCD,
    "ColorPicker": ColorPicker,
    "Tree": Tree,
}

#: 全量组件注册表：runtime 只认这一份
BUILTINS: dict[str, type[Component]] = {**_BASE_BUILTINS, **EXTRA_BUILTINS}
