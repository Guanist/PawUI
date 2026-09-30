"""PawUI 运行时（Qt）：解析 -> 组件 -> 渲染，串联事件、状态与主题。"""

from __future__ import annotations

import inspect
import sys
import weakref
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGraphicsOpacityEffect,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from .animate import entrance, is_animation
from .components import Component, Form, apply_text_props
from .dom import EVENT_KINDS, Event, widget_text
from .dom import Element as DomElement
from .errors import ComponentError, RenderError, ScriptError
from .nodes import ComponentDef, Element, Program
from .parser import parse
from .resolve import is_template, resolve_handler, resolve_prop_value, resolve_raw, runtime_refs
from .state import State
from .style import StyleEngine, normalize_value, selector_matches, theme_variables
from .theme import COLOR_FIELDS, THEMES, Theme
from .widgets import BUILTINS

LOGICAL_TAGS = {"If", "For"}

#: 只有这几类事件才值得进 `_on_event`（应用级过滤器会看到一切）
_WATCHED_EVENTS = frozenset({
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.Enter,
    QEvent.Type.Leave,
    QEvent.Type.FocusIn,
    QEvent.Type.FocusOut,
    QEvent.Type.KeyPress,
})


class _AsyncBridge(QObject):
    """把后台线程的结果经 Qt 信号送还主线程（QueuedConnection）。"""

    done = Signal(object, object)


class _WidgetFilter(QObject):
    """挂在控件自己身上的事件过滤器。

    Qt 要求 ``installEventFilter`` 传 QObject，而 Runtime 是普通 Python 对象，
    所以用这个小壳子转发。父对象必须是**被监听的那个控件**：这样控件被销毁时
    Qt 顺手把它一起删掉，绝不会留下一个「装着的过滤器已经死了」的悬挂指针。

    为什么不装在 QApplication 上：进程级过滤器会收到所有对象的事件，测试里
    控件反复建销，一旦在销毁过程中被回调就是访问越界崩溃；而且它需要 Runtime
    一直活着。装在控件上这两个问题都不存在。
    """

    def __init__(self, runtime: Runtime, widget: QWidget):
        super().__init__(widget)
        self._runtime_ref: weakref.ReferenceType[Runtime] = weakref.ref(runtime)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802 (Qt 命名)
        runtime = self._runtime_ref()
        if runtime is None:
            return False
        return runtime._on_event(obj, event)


class Runtime:
    def __init__(self, source: str, filename: str = "<memory>", context: dict | None = None, theme: str = "light"):
        self.app = QApplication.instance() or QApplication([])
        self.filename = filename
        self.program: Program = parse(source, filename)
        self.state = State()
        self.namespace: dict[str, Any] = {}
        self.components: dict[str, ComponentDef] = {}
        self.theme: Theme = THEMES.get(theme, Theme.light)()
        # 主题分两层记住：「底子」和「文件里的覆盖」。set_theme() 之后要能重新叠加，
        # 否则 <Theme>/<Color> 定义的颜色会在第一次切主题时被静默丢掉。
        self._theme_name: str = theme if theme in THEMES else "light"
        self._file_theme_name: str = self._theme_name
        self._theme_overrides: dict[str, str] = {}
        self._color_warnings: set[str] = set()
        self._injected_css: list[str] = []
        self._style_engine = StyleEngine("")
        self._built_components: list[Component] = []
        self.root: QWidget | None = None
        self._context = dict(context or {})
        self._built = False
        self._animations: list[tuple] = []
        self._bridges: set[_AsyncBridge] = set()
        self._subscriptions: list[Any] = []
        self._logical_pending: set[int] = set()
        self._validators: list[Any] = []
        self._fields: list[Component] = []
        self._toasts: list[QWidget] = []
        self._auto_name_seq = 0
        self._event_handlers: dict[QWidget, list[tuple[str, Any]]] = {}
        self._mouse_clicked: set[QWidget] = set()
        self._click_wired: set[QWidget] = set()
        self._want_click = False
        self._widget_filters: dict[QWidget, _WidgetFilter] = {}
        self._ready_callbacks: list[Any] = []

    def run(self, block: bool = True) -> QWidget | None:
        self._prepare()
        if self.root is None:
            self._build_tree()
        if block and self.app is not None:
            self.app.exec()
        return self.root

    def _prepare(self) -> None:
        if self._built:
            return
        self.namespace.update(self._context)
        self._resolve_theme()
        self._register_components()
        self._run_script()
        self._built = True

    def _resolve_theme(self) -> None:
        """主题优先级：Window theme 属性 -> <Theme extends> -> <Color> 覆盖。"""
        base = self._theme_name
        win = next((e for e in self.program.elements if e.tag == "Window"), None)
        if win:
            name = win.props.get("theme")
            if isinstance(name, str) and name in THEMES:
                base = name
        overrides: dict[str, str] = {}
        for el in self.program.elements:
            if el.tag != "Theme":
                continue
            ext = el.props.get("extends")
            if isinstance(ext, str) and ext in THEMES:
                base = ext
            for color in el.children:
                if color.tag != "Color":
                    continue
                name = color.props.get("name")
                value = color.props.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    overrides[name] = value
        self._theme_name = base
        self._file_theme_name = base
        self._theme_overrides = overrides
        self._apply_theme()

    def _apply_theme(self) -> None:
        """按「内置主题 + 文件内 <Color> 覆盖」重建 Theme 对象。

        文件里的覆盖只在用**文件自己声明的那个主题**时整份生效。一旦显式切到别的
        内置主题，内置字段（background / surface / accent …）就让位给那个主题的原样
        配色，只保留自定义色（brand 之类）—— 否则切到浅色后卡片还会是深色的。
        切回文件声明的主题时，整份覆盖复原。
        """
        factory = THEMES.get(self._theme_name, Theme.light)
        theme = factory()
        overrides = dict(self._theme_overrides)
        if overrides and self._theme_name != self._file_theme_name:
            overrides = {k: v for k, v in overrides.items() if k not in COLOR_FIELDS}
        if overrides:
            theme.apply(overrides)
        self.theme = theme

    def _register_components(self) -> None:
        for el in self.program.elements:
            if el.tag == "component":
                if not el.name:
                    raise ComponentError("component is missing a name", el.pos)
                self.components[el.name] = ComponentDef(el.name, el, el.pos)

    def _run_script(self) -> None:
        if self.program.script is None:
            return
        namespace: dict[str, Any] = {"state": self.state, "__builtins__": __builtins__, "app": self}
        namespace.update(self._context)
        namespace["state"] = self.state
        # DOM 快捷方式：脚本里直接 query/on/append 就是 app 上的那套
        namespace.update({
            "query": self.query,
            "query_all": self.query_all,
            "on": self.bind_event_selector,
            "append": self.append,
            "remove": self.remove,
            "css": self.css,
            "ready": self.ready,
            "toast": self.toast,
            "El": Element,
            "Event": Event,
        })
        try:
            code = compile(self.program.script.source, self.filename, "exec")
        except SyntaxError as e:
            raise ScriptError("script block has invalid Python syntax", self.program.script.pos, e)
        try:
            exec(code, namespace)
        except Exception as e:
            raise ScriptError("script block failed at runtime", self.program.script.pos, e)
        for k, v in namespace.items():
            if k in ("state", "__builtins__"):
                continue
            self.namespace[k] = v

    def _build_tree(self) -> None:
        self._clear_subscriptions()
        self._validators.clear()
        self._fields.clear()
        self._animations = []
        self._built_components = []
        self._style_engine = StyleEngine(
            "\n".join([*self.program.styles, *self._injected_css]),
            set(self.components),
            theme_variables(self.theme),
        )
        top_level = [e for e in self.program.elements if e.tag not in ("component", "Theme")]
        if not top_level:
            raise RenderError("no UI elements found in the file")

        window_els = [e for e in top_level if e.tag == "Window"]
        if len(window_els) > 1:
            raise RenderError("only one root <Window> is allowed", window_els[1].pos)
        if window_els:
            root_el = window_els[0]
            others = [e for e in top_level if e is not root_el]
            if others:
                raise RenderError("top-level elements must live inside <Window>", others[0].pos)
        else:
            root_el = Element(tag="Window", props={}, children=top_level, is_block=True)

        comp = self._build_element(root_el, None, {})
        self.root = comp.widget
        # 建树过程中子控件还没被 layout 挂到父节点上，后代选择器（.card Text）
        # 那时找不到祖先；整棵树建完后再刷一遍，级联才算真正生效。
        self._refresh_widget_styles()
        self._apply_app_stylesheet()
        self.root.setWindowTitle(comp.opt_str("title", "PawUI"))  # type: ignore[union-attr]
        self.root.resize(comp.opt_int("width", 480), comp.opt_int("height", 640))  # type: ignore[union-attr]
        self.root.show()  # type: ignore[union-attr]
        QTimer.singleShot(0, self._start_animations)
        self._run_ready()

    def _apply_app_stylesheet(self) -> None:
        """给整个应用套主题基线（滚动条 / 菜单 / 提示框这些细节控件靠它）。

        ``self.app`` 是 Qt 对象，应用已经销毁时再调就是碰野指针，直接跳过。
        """
        app = self.app
        if app is None or not isValid(app):
            return
        app.setStyleSheet(self.theme.qss())  # type: ignore[attr-defined]

    def _build_element(self, element: Element, parent: Component | None, scope: dict,
                       delay_bonus: int = 0) -> Component:
        tag = element.tag
        if tag in self.components:
            comp = self._build_component(element, parent, scope, delay_bonus)
            self._apply_style_attrs(comp, element)
            self._apply_user_css(comp)
            self._animate(comp.widget, element.props, scope, delay_bonus)
            return comp
        if tag in LOGICAL_TAGS:
            comp = self._build_logical(element, parent, scope, delay_bonus)
            self._apply_style_attrs(comp, element)
            self._apply_user_css(comp)
            return comp
        cls = BUILTINS.get(tag)
        if cls is None:
            raise RenderError(f"unknown component <{tag}>", element.pos)
        comp = cls(self, parent, element, scope)
        if parent is not None:
            parent._children.append(comp)
        comp.build()
        comp.apply_flex_policy()
        self._built_components.append(comp)
        # 内置组件也打上 pw-tag：DOM 里 app.query("Text") 的 tag 才是 PawUI 的名字，
        # 而不是 _ElidedLabel 这种内部实现类名。自定义组件稍后会覆盖成自己的名字。
        if comp.widget is not None and not comp.widget.property("pw-tag"):
            comp.widget.setProperty("pw-tag", tag)
        if self._want_click and comp.widget is not None:
            self._wire_click(comp.widget)
        self._apply_style_attrs(comp, element)
        self._apply_user_css(comp)
        self._animate(comp.widget, element.props, scope, delay_bonus)
        if cls.is_container:
            stagger = comp.opt_int("stagger", 0)
            index = 0
            for i, child in enumerate(element.children):
                child_comp = self._build_element(child, comp, scope, delay_bonus + i * stagger)
                if child_comp.widget is not None:
                    comp.add_child(child_comp, index)
                    index += 1
            comp.finish_children()
        return comp

    def _build_logical(self, element: Element, parent: Component | None, scope: dict,
                       delay_bonus: int = 0) -> Component:
        comp = Component(self, parent, element, scope)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(self.theme.spacing)
        comp.widget = box
        comp.layout = lay

        def populate() -> None:
            comp.dispose_children()
            while lay.count():
                item = lay.takeAt(0)
                if item is not None and item.widget() is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
            pairs: list[tuple[Element, dict]] = []
            if element.tag == "For":
                each = str(resolve_prop_value(element.props.get("each", "item"), scope, self))
                items = resolve_raw(element.props.get("in", []), scope, self)
                if isinstance(items, str):
                    items = [items]
                elif items is None:
                    items = []
                elif not isinstance(items, (list, tuple)):
                    try:
                        items = list(items)
                    except TypeError:
                        items = [items]
                for item in items:
                    item_scope = dict(scope)
                    item_scope[each] = item
                    pairs.extend((child, item_scope) for child in element.children)
            else:
                condition = resolve_raw(element.props.get("condition"), scope, self)
                show = condition.strip().lower() in ("1", "true", "yes", "on") if isinstance(condition, str) else bool(condition)
                if show:
                    pairs = [(child, scope) for child in element.children]
            stagger = int(resolve_prop_value(element.props.get("stagger", 0), scope, self) or 0)
            for i, (child, child_scope) in enumerate(pairs):
                child_comp = self._build_element(child, comp, child_scope, delay_bonus + i * stagger)
                placement = child_comp.placement()
                if placement is not None:
                    lay.addWidget(placement, child_comp.stretch())
            lay.addStretch(1)

        def refresh() -> None:
            key = id(box)
            if key in self._logical_pending:
                return
            self._logical_pending.add(key)
            def finish() -> None:
                populate()
                self._logical_pending.discard(key)
            QTimer.singleShot(0, finish)

        populate()
        ref_value = element.props.get("condition" if element.tag == "If" else "in", "")
        if isinstance(ref_value, str):
            for name in runtime_refs(ref_value):
                comp.watch_state(name, lambda _: refresh())
        self._animate(box, element.props, scope, delay_bonus)
        return comp

    def _animate(self, widget: QWidget | None, props: dict, scope: dict, delay_bonus: int) -> None:
        kind = props.get("animate")
        if not kind or widget is None:
            return
        kind = str(resolve_prop_value(kind, scope, self))
        if not is_animation(kind):
            return
        try:
            duration = int(resolve_prop_value(props.get("duration", 260), scope, self))
            delay = int(resolve_prop_value(props.get("delay", 0), scope, self)) + delay_bonus
        except (TypeError, ValueError):
            duration, delay = 260, delay_bonus
        curve = str(resolve_prop_value(props.get("easing", "out-cubic"), scope, self))
        self.queue_animation(widget, kind, duration, delay, curve)

    def _build_component(self, element: Element, parent: Component | None, scope: dict,
                         delay_bonus: int = 0) -> Component:
        cdef = self.components[element.tag]
        comp_scope = dict(scope)
        for child in cdef.root.children:
            if child.tag == "Prop":
                name = str(child.props.get("name", "")).strip()
                if name and name not in element.props:
                    comp_scope[name] = resolve_prop_value(child.props.get("default", ""), scope, self)
        for k, v in element.props.items():
            if k.startswith("on_"):
                comp_scope[k] = resolve_handler(v, scope, self)
            elif isinstance(v, str) and is_template(v):
                comp_scope[k] = v
            else:
                comp_scope[k] = resolve_prop_value(v, scope, self)
        result: Component | None = None
        for child in cdef.root.children:
            if child.tag in ("Prop",):
                continue
            result = self._build_element(child, parent, comp_scope, delay_bonus)
        if result is None:
            raise RenderError(f"component <{element.tag}> has no body", cdef.pos)
        if result.widget is not None:
            result.widget.setProperty("pw-tag", element.tag)
        return result

    def _apply_style_attrs(self, comp: Component, element: Element) -> None:
        """把 class / id 落到控件上，供样式引擎匹配。

        Qt 没有自定义 class 选择器，所以 class 存成动态属性、CSS 里由
        ``[pw-class~="x"]`` 命中；id 直接用 objectName，Qt 原生支持 ``#id``。
        """
        widget = comp.widget
        if widget is None:
            return
        cls = element.props.get("class")
        if isinstance(cls, str) and cls.strip():
            # 合并而不是覆盖：自定义组件把自己的 class 写在内层根节点上，
            # 调用方又传了一个 class，两个都得留着，否则内层那套样式会整体失效。
            existing = widget.property("pw-class")
            merged = f"{existing if isinstance(existing, str) else ''} {cls}"
            widget.setProperty("pw-class", " ".join(dict.fromkeys(merged.split())))
        ident = element.props.get("id")
        if isinstance(ident, str) and ident.strip():
            widget.setObjectName(ident.strip())
        self._apply_a11y(comp, element)

    def _apply_a11y(self, comp: Component, element: Element) -> None:
        """无障碍：``aria_label`` / ``aria_description`` / ``tabindex``。

        Qt 侧对应 ``accessibleName`` / ``accessibleDescription`` 和焦点策略，
        屏幕阅读器（NVDA / VoiceOver）认的就是这几个字段。
        """
        widget = comp.widget
        if widget is None:
            return
        label = element.props.get("aria_label", element.props.get("aria"))
        if isinstance(label, str) and label.strip():
            widget.setAccessibleName(label.strip())
        elif hasattr(widget, "text") and callable(getattr(widget, "text", None)):
            text = str(getattr(widget, "text")() or "").strip()
            if text:
                widget.setAccessibleName(text)
        description = element.props.get("aria_description", element.props.get("title"))
        if isinstance(description, str) and description.strip():
            widget.setAccessibleDescription(description.strip())
        if isinstance(label, str) and label.strip():
            widget.setToolTip(str(element.props.get("tooltip", label)))
        if "tabindex" in element.props:
            index = comp.opt_int("tabindex", 0)
            widget.setFocusPolicy(
                Qt.FocusPolicy.NoFocus if index < 0 else Qt.FocusPolicy.StrongFocus
            )
        # 盒模型：min / max 对所有组件通用
        for key, setter in (
            ("min_width", widget.setMinimumWidth),
            ("min_height", widget.setMinimumHeight),
            ("max_width", widget.setMaximumWidth),
            ("max_height", widget.setMaximumHeight),
        ):
            value = comp.opt_int(key, 0)
            if value:
                setter(value)

        # 盒模型：width / height 是通用属性，除非组件自己解释它们
        if not getattr(comp, "owns_size", False):
            width = comp.opt_int("width", 0)
            height = comp.opt_int("height", 0)
            if width > 0:
                widget.setFixedWidth(width)
            if height > 0:
                widget.setFixedHeight(height)
        self._apply_border(comp)

    def _apply_border(self, comp: Component) -> None:
        """通用边框：``border="1px solid #d2d2d7"`` 或 ``border_width`` + ``border_color``。

        直接用 ``QWidget { border: … }`` 会漏到后代身上（类型选择器匹配子类），
        所以临时给控件挂一个自动 objectName，把规则精确锁死在自己身上。
        """
        widget = comp.widget
        if widget is None:
            return
        shorthand = comp.opt_str("border", "").strip()
        width = comp.opt_str("border_width", "").strip()
        color = comp.opt_str("border_color", "").strip()
        if not (shorthand or width or color):
            return
        decls: list[str] = []
        if shorthand:
            decls.append(f"border:{normalize_value('border', shorthand)}")
        if width:
            decls.append(f"border-width:{normalize_value('border-width', width)}")
        if color:
            resolved = comp.opt_color("border_color", color)
            decls.append(f"border-color:{resolved}")
        if not decls:
            return
        name = widget.objectName()
        if not name:
            name = self._next_auto_name()
            widget.setObjectName(name)
        base = widget.styleSheet() or ""
        widget.setStyleSheet(f"{base}\nQWidget#{name} {{ {'; '.join(decls)}; }}")

    def _next_auto_name(self) -> str:
        self._auto_name_seq += 1
        return f"pw-auto-{self._auto_name_seq}"

    def _apply_user_css(self, comp: Component) -> None:
        """把匹配到的用户 CSS 追加到控件自身样式表末尾（后写胜出）。

        控件自带的组件默认样式先记成 ``_base_qss``，重放时从它重算，
        这样多次 ``inject_css`` 不会把同一条规则叠出好几份。
        """
        widget = comp.widget
        if widget is None:
            return
        if comp not in self._built_components:
            self._built_components.append(comp)
        if not comp._base_qss_locked:
            comp._base_qss = widget.styleSheet() or ""
            comp._base_qss_locked = True
        css, props = self._style_engine.apply(widget)
        final = f"{comp._base_qss}\n{css}".strip()
        # 第二次（建完树补后代选择器那遍）绝大多数控件算出来是一模一样的，
        # 再 setStyleSheet 一次会让 Qt 把整棵样式重算，白花几百毫秒
        if final != comp._last_qss:
            widget.setStyleSheet(final)
            comp._last_qss = final
        if props:
            apply_text_props(widget, props)

    def _refresh_widget_styles(self) -> None:
        for comp in self._built_components:
            self._apply_user_css(comp)

    def inject_css(self, text: str) -> None:
        """运行时注入 CSS：追加到 ``<Style>`` 之后（因此优先级更高），并立即生效。"""
        if not text or not text.strip():
            return
        if text in self._injected_css:
            return  # 同一段重复注入没有意义，还会把规则叠出好几份
        self._injected_css.append(text)
        self._style_engine = StyleEngine(
            "\n".join([*self.program.styles, *self._injected_css]),
            set(self.components),
            theme_variables(self.theme),
        )
        self._refresh_widget_styles()

    def watch_state(self, key: str, fn: Any) -> None:
        self._subscriptions.append(self.state.watch(key, fn))

    def _clear_subscriptions(self) -> None:
        for unsubscribe in self._subscriptions:
            unsubscribe()
        self._subscriptions.clear()

    def register_validator(self, validator: Any) -> None:
        self._validators.append(validator)

    def validate(self) -> bool:
        """跑一遍所有字段校验，把错误画到页面上，返回是否全部通过。"""
        self.validation_errors = []
        for field in self._fields:
            message = field.error_text()
            field.set_error(message)
            if message:
                self.validation_errors.append(message)
        for validator in self._validators:
            error = validator()
            if error:
                self.validation_errors.append(error)
        return not self.validation_errors

    def register_field(self, comp: Component) -> None:
        """把可校验字段登记进来（``<Input required="true">`` 之类）。"""
        if comp not in self._fields:
            self._fields.append(comp)

    def submit(self) -> bool:
        """提交表单：校验通过才调 ``on_submit``。页面上没有 <Form> 时就只校验。"""
        for comp in self._built_components:
            if isinstance(comp, Form):
                return comp.submit()
        return self.validate()

    def show_field_error(self, comp: Component, message: str | None) -> None:
        """字段错误的表现层：红色描边 + 控件下方一行错误文字。

        以前 ``validation_errors`` 只是躺在内存里的一串字符串，用户点提交什么都
        看不到。这里把「错在哪、错什么」直接画到对应字段上。
        """
        widget = comp.widget
        if widget is None:
            return
        name = widget.objectName()
        if not name:
            name = self._next_auto_name()
            widget.setObjectName(name)
        base = comp._base_qss if comp._base_qss_locked else (widget.styleSheet() or "")
        label: Any = getattr(comp, "_error_label", None)
        if not message:
            widget.setStyleSheet(base)
            if label is not None:
                label.setVisible(False)
            return
        widget.setStyleSheet(
            f"{base}\nQWidget#{name} {{ border:1px solid {self.theme.danger}; }}"
        )
        if label is None:
            label = QLabel("")
            label.setWordWrap(True)
            label.setStyleSheet(
                f"color:{self.theme.danger}; font-size:{self.theme.font_size}px;"
            )
            parent = widget.parentWidget()
            layout = parent.layout() if parent is not None else None
            inserter = getattr(layout, "insertWidget", None) if layout is not None else None
            if layout is not None and inserter is not None:
                index = layout.indexOf(widget)
                inserter(index + 1 if index >= 0 else layout.count(), label)
            comp._error_label = label
        label.setText(message)
        label.setVisible(True)

    def set_theme(self, name_or_theme: str | Theme) -> None:
        """切换主题。传名字时只换内置底子，文件里的 <Color> 覆盖继续生效。"""
        if isinstance(name_or_theme, Theme):
            self.theme = name_or_theme
        elif isinstance(name_or_theme, str):
            if name_or_theme in THEMES:
                self._theme_name = name_or_theme
                self._apply_theme()
        self._apply_app_stylesheet()

    def warn_unknown_color(self, value: str, tag: str, key: str) -> None:
        """颜色既不是主题令牌也不是合法颜色时提醒一次。

        以前这种值会被原样拼进样式表（``color:brand``），Qt 静默丢弃整条声明，
        用户只看到「颜色不对」却拿不到任何报错。同一个值只提醒一次。
        """
        if value in self._color_warnings:
            return
        self._color_warnings.add(value)
        known = sorted({*COLOR_FIELDS, *getattr(self.theme, "custom", {})})
        print(
            f"PawUI: unknown color {value!r} on <{tag} {key}=...> — 既不是主题色也不是"
            f"合法颜色；可用主题色: {', '.join(known)}",
            file=sys.stderr,
        )

    def queue_animation(self, widget: QWidget, kind: str, duration: int, delay: int, curve: str) -> None:
        self._animations.append((widget, kind, duration, delay, curve))

    def _start_animations(self) -> None:
        pending, self._animations = self._animations, []
        for widget, kind, duration, delay, curve in pending:
            if isValid(widget):
                entrance(widget, kind, duration, delay, curve)

    def refresh(self) -> None:
        if self.root is None:
            return
        QTimer.singleShot(0, self._rebuild)

    def reload(self, source: str) -> None:
        """热重载：重新解析 source 并重建 UI。保留 State 对象与命名空间函数。"""
        self.program = parse(source, self.filename)
        self.components.clear()
        self._built = False
        self._prepare()
        old = self.root
        try:
            self._build_tree()
        except Exception:
            self.root = old
            raise
        if old is not None and old is not self.root:
            old.close()
            old.deleteLater()

    def _rebuild(self) -> None:
        old = self.root
        try:
            self._build_tree()
        except Exception as e:
            self.root = old
            print(f"PawUI rebuild error: {e}", file=sys.stderr)
            return
        if old is not None and old is not self.root:
            old.close()
            old.deleteLater()

    def invoke(self, handler: Any, *args: Any) -> Any:
        if not callable(handler):
            return None
        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
        except (TypeError, ValueError):
            return handler(*args)
        has_var = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
        positional = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        if args and not positional and not has_var:
            return handler()
        return handler(*args)

    # ------------------------------------------------------------------
    # DOM：脚本侧对页面的增删改查（和浏览器那套对齐）
    # ------------------------------------------------------------------
    def wroot(self) -> QWidget | None:
        return self.root

    def all_widgets(self, root: QWidget | None = None) -> list[QWidget]:
        """按**布局顺序**先序返回所有控件（含 root 自己）。

        不能用 ``findChildren``：它按父子关系的创建顺序返回，``append`` 加进来的
        新控件会跑到列表最后，``query_all`` 的顺序就和页面上的视觉顺序对不上了。
        """
        start = root if root is not None else self.root
        if start is None:
            return []
        out = [start]
        for child in self._layout_children(start):
            out.extend(self.all_widgets(child))
        return out

    def _layout_children(self, widget: QWidget) -> list[QWidget]:
        """直接子控件，按布局里的摆放顺序；没有布局就退回 Qt 的直系子控件。"""
        layout = widget.layout()
        if layout is not None:
            out: list[QWidget] = []
            for i in range(layout.count()):
                item = layout.itemAt(i)
                found = item.widget() if item is not None else None
                if found is not None:
                    out.append(found)
            if out:
                return out
        comp = self.owner_of(widget)
        if comp is not None and comp._children:
            kids = [c.placement() or c.widget for c in comp._children]
            return [k for k in kids if k is not None]
        return widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)

    def on(self, selector: str, kind: str, handler: Any) -> int:
        """``app.on("#save", "click", fn)`` 的别名（脚本里写起来更短）。"""
        return self.bind_event_selector(selector, kind, handler)

    def _selector_tags(self) -> set[str]:
        """选择器里可以当「类型」写的名字：用户组件 + 内置组件。

        不带上内置的，``app.query("Panel")`` 会被当成 Qt 类名去找，永远查不到。
        """
        return {*self.components, *BUILTINS}

    def query(self, selector: str, root: QWidget | None = None) -> DomElement | None:
        """CSS 选择器查一个控件，命中的第一个（``document.querySelector``）。"""
        for widget in self.all_widgets(root):
            if selector_matches(widget, selector, self._selector_tags()):
                return DomElement(self, widget)
        return None

    def query_all(self, selector: str, root: QWidget | None = None) -> list[DomElement]:
        """CSS 选择器查全部（``document.querySelectorAll``）。"""
        return [
            DomElement(self, widget)
            for widget in self.all_widgets(root)
            if selector_matches(widget, selector, self._selector_tags())
        ]

    def el(self, target: Any) -> DomElement | None:
        """把 id / 选择器 / 控件 / 已有句柄统一转成 :class:`DomElement`。"""
        if target is None:
            return None
        if isinstance(target, DomElement):
            return target
        if isinstance(target, QWidget):
            return DomElement(self, target)
        return self.query(str(target))

    def owner_of(self, widget: QWidget) -> Component | None:
        """反查控件所属的组件对象。"""
        for comp in reversed(self._built_components):
            if comp.widget is widget:
                return comp
        return None

    def _target_layout(self, widget: QWidget) -> Any:
        comp = self.owner_of(widget)
        if comp is not None and comp.layout is not None:
            return comp.layout
        layout = widget.layout()
        if layout is None:
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
        return layout

    def _insert_widget(self, widget: QWidget, child: Component, index: int, prepend: bool) -> None:
        """把子控件插进容器的布局里（追加时插在尾部弹簧之前）。"""
        layout = self._target_layout(widget)
        comp = self.owner_of(widget)
        placement = child.placement()
        if placement is None:
            return
        if layout.__class__.__name__ == "QGridLayout":
            columns = max(1, comp.opt_int("columns", 2)) if comp is not None else 2
            existing = layout.count()
            position = 0 if prepend else existing
            layout.addWidget(placement, position // columns, position % columns)
            return
        if prepend:
            layout.insertWidget(0, placement, child.stretch())
            return
        position = layout.count()
        last = layout.itemAt(position - 1) if position else None
        if last is not None and last.spacerItem() is not None:
            position -= 1  # 别掉到尾部弹簧下面去
        layout.insertWidget(position, placement, child.stretch())

    def build_fragment(self, markup: str, parent: Component | None = None) -> list[Component]:
        """把一小段 .paw 片段（``<Text>hi</Text>``）构建成组件列表。"""
        fragment = parse(markup, f"{self.filename}:fragment")
        scope = dict(self.namespace)
        scope.setdefault("state", self.state)
        built: list[Component] = []
        for element in fragment.elements:
            if element.tag in ("component", "Theme", "Window"):
                continue
            built.append(self._build_element(element, parent, scope))
        return built

    def append(self, markup: str, target: Any = None, prepend: bool = False) -> list[DomElement]:
        """往容器里插一段 .paw 片段（``parent.append(child)``）。

        目标可以是 ``"#id"`` / ``".class"`` / 控件对象；不传就插到根上。
        """
        host = self.root if target is None else self.el(target)
        widget = host.widget if isinstance(host, DomElement) else host
        if widget is None:
            return []
        comp = self.owner_of(widget)
        added: list[Component] = []
        for child in self.build_fragment(markup, comp):
            if comp is not None:
                comp._children.append(child)
            self._insert_widget(widget, child, len(self._built_components), prepend)
            added.append(child)
        return [DomElement(self, child.widget) for child in added if child.widget is not None]

    def remove(self, target: Any) -> bool:
        """从页面上摘掉一个控件（``el.remove()``）。"""
        element = self.el(target)
        if element is None:
            return False
        return self.remove_widget(element.widget)

    def remove_widget(self, widget: QWidget) -> bool:
        if widget is None or widget is self.root:
            return False
        comp = self.owner_of(widget)
        if comp is not None:
            comp.dispose()
            if comp in self._built_components:
                self._built_components.remove(comp)
            if comp.parent is not None and comp in comp.parent._children:
                comp.parent._children.remove(comp)
        parent = widget.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is not None:
            layout.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()
        return True

    def clear_children(self, widget: QWidget) -> None:
        """清掉容器的所有子控件（``el.clear()``）。"""
        for child in self.child_widgets(widget):
            self.remove_widget(child)

    def child_widgets(self, widget: QWidget) -> list[QWidget]:
        comp = self.owner_of(widget)
        if comp is not None and comp._children:
            return [c.widget for c in comp._children if c.widget is not None]
        layout = widget.layout()
        if layout is None:
            return []
        out: list[QWidget] = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            found = item.widget() if item is not None else None
            if found is not None:
                out.append(found)
        return out

    def bind_event_selector(self, selector: str, kind: str, handler: Any) -> int:
        """``app.on(".card", "click", fn)``：给选择器命中的所有控件绑事件。

        返回绑了几个。页面还没建好时调用会返回 0 —— 想在那个时机绑定，
        用 ``ready(fn)`` 包起来。
        """
        hits = self.query_all(selector)
        for element in hits:
            self.bind_event(element.widget, kind, handler)
        return len(hits)

    def css(self, selector: str, declarations: str) -> None:
        """``app.css(".card", "radius: 8;")``：按选择器注入样式（等价于写进 <Style>）。"""
        self.inject_css(f"{selector} {{ {declarations} }}")

    def bind_event(self, widget: QWidget, kind: str, handler: Any) -> None:
        """动态绑事件（``el.on("click", fn)``）。"""
        kind = str(kind).strip().lower()
        if not callable(handler):
            raise ScriptError(f"event handler for {kind!r} must be callable")
        if kind not in EVENT_KINDS:
            raise ScriptError(
                f"unknown event {kind!r}; available: {', '.join(EVENT_KINDS)}"
            )
        self._event_handlers.setdefault(widget, []).append((kind, handler))
        if kind == "click":
            # 点在自己身上、也点在子控件身上的都要能冒上来，所以整棵子树都接上
            self._want_click = True
            self._wire_click(widget)
            for button in widget.findChildren(QAbstractButton):
                self._wire_click(button)
        self._connect_event(widget, kind)
        self._install_widget_filter(widget)

    def _wire_click(self, widget: QWidget) -> None:
        """把按钮的 ``clicked`` 信号接上（鼠标 / 键盘 / ``.click()`` 都会来）。"""
        if not isinstance(widget, QAbstractButton) or widget in self._click_wired:
            return
        self._click_wired.add(widget)
        widget.clicked.connect(lambda _checked=False, b=widget: self._on_clicked(b))

    def _install_widget_filter(self, widget: QWidget) -> None:
        """给控件自己装过滤器（鼠标 / 悬停 / 焦点 / 回车这些没有信号可用）。

        子控件（标题、图片这类不吃鼠标事件的）上的点击会冒泡到父控件，
        所以「点卡片任意位置」这种绑定照样生效；按钮那种自己吃掉事件的，
        由 ``_wire_click`` 在信号里往上冒。
        """
        if widget in self._widget_filters:
            return
        self._widget_filters[widget] = _WidgetFilter(self, widget)
        widget.installEventFilter(self._widget_filters[widget])

    def _emit(self, widget: QWidget, kind: str, value: Any = None, key: str = "") -> None:
        """把事件派发给绑在这控件上的处理函数（子控件的事件会冒泡上来）。"""
        node: QWidget | None = widget
        while node is not None:
            for bound_kind, handler in self._event_handlers.get(node, ()):
                if bound_kind != kind:
                    continue
                checked = (
                    node.isChecked()
                    if isinstance(node, QAbstractButton) and node.isCheckable()
                    else None
                )
                event = Event(kind, DomElement(self, widget), value, key, checked)
                try:
                    self.invoke(handler, event)
                except Exception as error:  # noqa: BLE001
                    print(f"PawUI: handler for {kind!r} on {node} failed: {error}", file=sys.stderr)
            node = node.parentWidget()

    def _connect_event(self, widget: QWidget, kind: str) -> None:
        """能用信号的地方直接用信号，剩下的靠 eventFilter 兜。"""
        if kind == "click":
            return  # 点击统一走 _wire_click
        if kind in ("hover", "leave", "focus", "blur"):
            return
        if kind == "enter":
            if isinstance(widget, QLineEdit):
                widget.returnPressed.connect(lambda: self._emit(widget, "enter"))
            return
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda text: self._emit(widget, kind, text))
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda: self._emit(widget, kind, widget.toPlainText()))
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(lambda text: self._emit(widget, kind, text))
        elif isinstance(widget, QSlider):
            widget.valueChanged.connect(lambda value: self._emit(widget, kind, value))
        elif isinstance(widget, QAbstractButton):
            widget.toggled.connect(lambda checked: self._emit(widget, kind, checked))

    @staticmethod
    def _signal_backed(widget: QWidget, kind: str) -> bool:
        """这类事件有现成的 Qt 信号，再装事件过滤器就会触发两次。"""
        if kind == "click":
            return isinstance(widget, QAbstractButton)
        if kind == "enter":
            return isinstance(widget, QLineEdit)
        if kind in ("change", "input"):
            return isinstance(
                widget, (QLineEdit, QPlainTextEdit, QComboBox, QSlider, QAbstractButton)
            )
        return False

    def _on_clicked(self, widget: QAbstractButton) -> None:
        """按钮的 ``clicked`` 信号（鼠标 / 键盘 / 代码调用都会来）。

        鼠标点击已经由事件过滤器派发过一次了，这里只补键盘和 ``.click()``
        这两种不会产生鼠标事件的情况，避免同一个点击触发两遍。
        """
        if widget in self._mouse_clicked:
            self._mouse_clicked.discard(widget)
            return
        self._emit(widget, "click", widget_text(widget) or None)

    def _on_event(self, obj: Any, event: Any) -> bool:
        """兜住鼠标 / 悬停 / 焦点 / 回车这些 Qt 没有对应信号的事件。"""
        # 应用级过滤器会收到**所有**对象的事件（QStyle、QWindow、菜单……），
        # 先剔掉不是控件的、以及压根没人绑事件的 Runtime，别白跑一遍。
        if not self._event_handlers or not isinstance(obj, QWidget):
            return False
        try:
            # 控件可能正在被销毁（Qt 对象没了、Python 包装还在），
            # 不先判一次就是碰野指针
            if not isValid(obj):
                return False
            kind = event.type()
            if kind not in _WATCHED_EVENTS:
                return False
            if kind == QEvent.Type.MouseButtonRelease:
                if isValid(obj) and obj.isEnabled():
                    # 真正被点的可能是更深的子控件，跟浏览器一样按最深的来派发，
                    # 再顺着父链往上涨（事件冒泡）
                    deep = obj
                    pos = getattr(event, "position", None)
                    if pos is not None:
                        hit = obj.childAt(pos().toPoint())
                        if hit is not None:
                            deep = hit
                    if isinstance(obj, QAbstractButton):
                        # 紧接着 clicked 信号会到，标一下别派发第二遍
                        self._mouse_clicked.add(obj)
                    self._emit(deep, "click", widget_text(deep) or None)
            elif kind == QEvent.Type.Enter:
                self._emit(obj, "hover")
            elif kind == QEvent.Type.Leave:
                self._emit(obj, "leave")
            elif kind == QEvent.Type.FocusIn:
                self._emit(obj, "focus")
            elif kind == QEvent.Type.FocusOut:
                self._emit(obj, "blur")
            elif kind == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter
            ):
                self._emit(obj, "enter", widget_text(obj), "Enter")
        except RuntimeError:  # 控件已经销毁
            return False
        return False

    def restyle(self) -> None:
        """class / 属性变了之后重新算一遍样式。"""
        self._refresh_widget_styles()

    # ------------------------------------------------------------------
    # Toast
    # ------------------------------------------------------------------
    TOAST_COLORS = {
        "info": "accent",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "danger",
    }

    def toast(self, message: str, kind: str = "info", duration: int = 2400) -> QWidget | None:
        """弹一条浮动提示（``app.toast("已保存", "success")``）。

        Qt 没有内置的 toast，这里直接在根窗口上浮一个圆角标签，淡入 → 停留 →
        淡出，到点自己销毁。多条会往上叠，不会互相压住。
        """
        if self.root is None:
            return None
        color = self.TOAST_COLORS.get(str(kind).lower(), str(kind))
        if not color.startswith("#"):
            color = getattr(self.theme, color, self.theme.accent)
        label = QLabel(str(message), self.root)
        label.setStyleSheet(
            f"QLabel {{ background-color:{color}; color:#ffffff;"
            f" border-radius:10px; padding:9px 18px;"
            f" font-size:{self.theme.font_size}px; font-weight:600; }}"
        )
        label.adjustSize()
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)
        self._toasts.append(label)
        self._layout_toasts()
        fade_in = QPropertyAnimation(effect, b"opacity", label)
        fade_in.setDuration(160)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.start()
        label._fade = fade_in  # type: ignore[attr-defined]
        label.show()
        label.raise_()

        def dismiss() -> None:
            if not isValid(label):
                return
            fade_out = QPropertyAnimation(effect, b"opacity", label)
            fade_out.setDuration(220)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.finished.connect(lambda: self._drop_toast(label))
            fade_out.start()
            label._fade = fade_out  # type: ignore[attr-defined]

        QTimer.singleShot(max(400, int(duration)), dismiss)
        return label

    def _drop_toast(self, label: QWidget) -> None:
        if label in self._toasts:
            self._toasts.remove(label)
        if isValid(label):
            label.hide()
            label.deleteLater()
        self._layout_toasts()

    def _layout_toasts(self) -> None:
        if self.root is None:
            return
        offset = 18
        for label in reversed(self._toasts):
            if not isValid(label):
                continue
            label.adjustSize()
            x = max(8, (self.root.width() - label.width()) // 2)
            y = max(8, self.root.height() - label.height() - offset)
            label.move(x, y)
            label.raise_()
            offset += label.height() + 8

    # ------------------------------------------------------------------
    # inspect
    # ------------------------------------------------------------------
    def inspect_tree(self) -> str:
        """把控件树 + 命中的 CSS 规则 + state 订阅关系打成人能看的文本。

        ``pawui inspect app.paw`` 用的是这一份；样式没生效时先看它，
        比盯着 QSS 猜快得多。
        """
        lines: list[str] = []
        engine = self._style_engine
        for widget in self.all_widgets():
            if not isValid(widget):
                continue
            depth = 0
            node = widget.parentWidget()
            while node is not None and node is not self.root:
                depth += 1
                node = node.parentWidget()
            if widget is self.root:
                depth = 0
            tag = widget.property("pw-tag") or type(widget).__name__
            ident = f"#{widget.objectName()}" if widget.objectName() else ""
            classes = str(widget.property("pw-class") or "").strip()
            cls = f".{classes.replace(' ', '.')}" if classes else ""
            geo = widget.geometry()
            text = ""
            if hasattr(widget, "text") and callable(getattr(widget, "text", None)):
                raw = str(getattr(widget, "text")() or "")
                text = f' "{raw[:24]}"' if raw else ""
            lines.append(
                f"{'  ' * depth}<{tag}{ident}{cls}> {geo.width()}x{geo.height()}{text}"
            )
            for selector in engine.matched_selectors(widget):
                lines.append(f"{'  ' * depth}    ← {selector}")
            aria = widget.accessibleName()
            if aria:
                lines.append(f"{'  ' * depth}    aria: {aria}")
        listeners = getattr(self.state, "_listeners", None)
        if listeners:
            watched = ", ".join(
                f"{key}({len(fns)})" for key, fns in sorted(listeners.items()) if fns
            )
            lines.append(f"\nstate subscriptions: {watched}")
        return "\n".join(lines)

    def ready(self, fn: Any) -> None:
        """页面（控件树）建好之后跑一次 —— 脚本里访问控件就写在这里面。"""
        if callable(fn):
            self._ready_callbacks.append(fn)

    def _run_ready(self) -> None:
        for fn in list(self._ready_callbacks):
            try:
                fn()
            except Exception as error:  # noqa: BLE001
                print(f"PawUI: ready() callback failed: {error}", file=sys.stderr)

    def invoke_async(self, handler: Any, *args: Any, done: Any = None) -> None:
        """在后台线程执行 handler，完成后把结果经 done(result, error) 交回主线程。

        适合耗时任务：handler 只做计算、千万别碰 Qt 控件；UI/state 更新放到 done。
        """
        if not callable(handler):
            return
        bridge = _AsyncBridge()
        self._bridges.add(bridge)

        def _worker() -> None:
            try:
                result = self.invoke(handler, *args)
                error = None
            except Exception as e:  # noqa: BLE001
                result, error = None, e
            bridge.done.emit(result, error)

        def _on_done(result: Any, error: Any) -> None:
            self._bridges.discard(bridge)
            if callable(done):
                done(result, error)

        bridge.done.connect(_on_done)
        from threading import Thread
        Thread(target=_worker, daemon=True).start()


def render(source: str, filename: str = "<memory>", context: dict | None = None, theme: str = "light", block: bool = False) -> QWidget | None:
    rt = Runtime(source, filename, context, theme)
    return rt.run(block=block)
