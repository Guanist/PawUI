"""PawUI 组件库（Qt 后端）：把 AST 元素映射为 QWidget + QSS 自定义样式。

Qt 原生抗锯齿、QSS 圆角/悬停/聚焦态、IME 组字全部由 Qt 处理，
不再有 Tk 的糊、像素角、IME 小字问题。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTabWidget,
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
    resolve_template,
)
from .theme import Theme, _blend


class Component:
    is_container = False

    def __init__(self, runtime: Any, parent: Component | None, element: Element, scope: dict):
        self.runtime = runtime
        self.parent = parent
        self.element = element
        self.scope = scope
        self.props = element.props
        self.theme: Theme = runtime.theme
        self.widget: QWidget | None = None
        self.layout: Any = None

    def build(self) -> QWidget:
        raise NotImplementedError

    def stretch(self) -> int:
        return 1 if self.opt_bool("expand", False) else 0

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
        v = resolve_prop_value(self.props.get(key, default), self.scope, self.runtime)
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)

    def opt_color(self, key: str, default: str) -> str:
        return str(resolve_prop_value(self.props.get(key, default), self.scope, self.runtime))

    def padding(self) -> tuple[int, int, int, int]:
        v = resolve_prop_value(self.props.get("padding", self.theme.padding), self.scope, self.runtime)
        try:
            n = int(v)
            return (n, n, n, n)
        except (TypeError, ValueError):
            try:
                seq = tuple(v)
                if len(seq) == 1:
                    return (int(seq[0]),) * 4
                if len(seq) == 2:
                    return (int(seq[1]), int(seq[0]), int(seq[1]), int(seq[0]))
                if len(seq) == 4:
                    return (int(seq[0]), int(seq[1]), int(seq[2]), int(seq[3]))
            except Exception:
                pass
        p = self.theme.padding
        return (p, p, p, p)

    def bind_state(self, template: str, set_fn: Any) -> None:
        names = collect_refs(template, self.scope, self.runtime)
        for name in names:
            self.runtime.state.watch(name, lambda _: set_fn(resolve_template(template, self.scope, self.runtime)))

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

    def build(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box) if self.axis == "y" else QHBoxLayout(box)
        left, top, right, bottom = self.padding()
        lay.setContentsMargins(left, top, right, bottom)
        lay.setSpacing(self.opt_int("spacing", self.theme.spacing))
        bg = self.opt_color("bg", "")
        if bg:
            box.setStyleSheet(
                f"QWidget {{ background-color:{bg}; border-radius:{self.opt_int('radius', self.theme.radius)}px; }}"
            )
        self.widget = box
        self.layout = lay
        return box


class Column(Container):
    axis = "y"


class Row(Container):
    axis = "x"


class Text(Component):
    def build(self) -> QLabel:
        label = QLabel(self.resolved_content())
        fg = self.opt_color("color", self.opt_color("fg", self.theme.text))
        size = self.opt_size()
        bold = self.opt_bool("bold", False)
        italic = self.opt_bool("italic", False)
        style = f"color:{fg}; font-size:{size}px;"
        if bold:
            style += " font-weight:600;"
        if italic:
            style += " font-style:italic;"
        label.setStyleSheet(style)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.widget = label
        content = self.props.get("__content__", "")
        if isinstance(content, str) and is_template(content):
            self.bind_state(content, lambda v: self.widget.setText(str(v)))
        return label


class Button(Component):
    def build(self) -> QPushButton:
        handler = resolve_handler(self.props.get("on_click", None), self.scope, self.runtime)
        theme = self.theme
        bg = self.opt_color("bg", theme.accent)
        fg = self.opt_color("fg", theme.background)
        radius = self.opt_int("radius", 17)
        size = self.opt_size()
        btn = QPushButton(self.resolved_content())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        hover = _blend(bg, "#ffffff", 0.14)
        press = _blend(bg, "#000000", 0.16)
        disabled = self.opt_bool("disabled", False)
        btn.setEnabled(not disabled)
        btn.setStyleSheet(
            f"""
            QPushButton {{ background-color:{bg}; color:{fg}; border:none; border-radius:{radius}px;
                min-height:34px; padding:0 18px; font-weight:600; font-size:{size}px; }}
            QPushButton:hover {{ background-color:{hover}; }}
            QPushButton:pressed {{ background-color:{press}; }}
            QPushButton:disabled {{ background-color:{theme.border}; color:{theme.subtext}; }}
            """
        )
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
        size = self.opt_int("size", 0)
        if size:
            edit.setStyleSheet(
                f"QLineEdit {{ background-color:{self.theme.surface}; color:{self.theme.text};"
                f" border:1px solid {self.theme.border}; border-radius:10px; padding:7px 12px;"
                f" font-size:{size}px; }} QLineEdit:focus {{ border:2px solid {self.theme.accent}; }}"
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
        value = self.props.get("value", "")
        if isinstance(value, str) and is_template(value):

            def _set(v: Any) -> None:
                self._suppress = True
                edit.setText(str(resolve_prop_value(v, self.scope, self.runtime)))
                self._suppress = False

            self.bind_state(value, _set)
        return edit

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
        slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{ background:{bg}; height:6px; border-radius:3px; }}
            QSlider::sub-page:horizontal {{ background:{accent}; border-radius:3px; }}
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
    def build(self) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, self.opt_int("max", 100))
        bar.setValue(self.opt_int("value", 0))
        bar.setFixedHeight(self.opt_int("height", 10))
        bar.setTextVisible(self.opt_bool("text", False))
        accent = self.opt_color("accent", self.theme.accent)
        bg = self.opt_color("bg", self.theme.surface)
        bar.setStyleSheet(
            f"""
            QProgressBar {{ background-color:{bg}; border:none; border-radius:5px; }}
            QProgressBar::chunk {{ background-color:{accent}; border-radius:5px; }}
            """
        )
        self.widget = bar
        self._bar = bar
        value = self.props.get("value", None)
        if isinstance(value, str) and is_template(value):
            self.bind_state(value, lambda v: bar.setValue(int(resolve_prop_value(v, self.scope, self.runtime))))
        return bar


class Tabs(Component):
    is_container = False

    def build(self) -> QTabWidget:
        tabs = QTabWidget()
        bg = self.opt_color("bg", self.theme.background)
        tabs.setStyleSheet(
            f"""
            QTabBar::tab {{ background:{self.theme.surface}; color:{self.theme.subtext};
                padding:8px 18px; border:none; border-top-left-radius:8px; border-top-right-radius:8px; }}
            QTabBar::tab:selected {{ background:{bg}; color:{self.theme.text}; }}
            QTabWidget::pane {{ border:1px solid {self.theme.border}; border-radius:0 0 8px 8px; }}
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
            if child.tag == "Tab":
                for inner in child.children:
                    inner_comp = self.runtime._build_element(inner, self, self.scope)
                    if inner_comp.widget is not None:
                        page_lay.addWidget(inner_comp.widget)
            else:
                child_comp = self.runtime._build_element(child, self, self.scope)
                if child_comp.widget is not None:
                    page_lay.addWidget(child_comp.widget)
            page_lay.addStretch(1)
            self._tabs.addTab(page, label)
        return tabs


class Image(Component):
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
    is_container = True

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


BUILTINS: dict[str, type[Component]] = {
    "Window": Window,
    "Column": Column,
    "Row": Row,
    "Text": Text,
    "Button": Button,
    "Input": Input,
    "Checkbox": Checkbox,
    "Divider": Divider,
    "Spacer": Spacer,
    "Slider": Slider,
    "Progress": Progress,
    "Tabs": Tabs,
    "Image": Image,
    "Tooltip": Tooltip,
}
