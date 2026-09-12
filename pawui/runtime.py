"""PawUI 运行时（Qt）：解析 -> 组件 -> 渲染，串联事件、状态与主题。"""

from __future__ import annotations

import inspect
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from .animate import entrance, is_animation
from .components import BUILTINS, Component
from .errors import ComponentError, RenderError, ScriptError
from .nodes import ComponentDef, Element, Program
from .parser import parse
from .resolve import is_template, resolve_handler, resolve_prop_value, resolve_raw, runtime_refs
from .state import State
from .theme import THEMES, Theme

LOGICAL_TAGS = {"If", "For"}


class _AsyncBridge(QObject):
    """把后台线程的结果经 Qt 信号送还主线程（QueuedConnection）。"""

    done = Signal(object, object)


class Runtime:
    def __init__(self, source: str, filename: str = "<memory>", context: dict | None = None, theme: str = "dark"):
        self.app = QApplication.instance() or QApplication([])
        self.filename = filename
        self.program: Program = parse(source, filename)
        self.state = State()
        self.namespace: dict[str, Any] = {}
        self.components: dict[str, ComponentDef] = {}
        self.theme: Theme = THEMES.get(theme, Theme.dark)()
        self.root: QWidget | None = None
        self._context = dict(context or {})
        self._built = False
        self._animations: list[tuple] = []
        self._bridges: set[_AsyncBridge] = set()
        self._subscriptions: list[Any] = []
        self._logical_pending: set[int] = set()
        self._validators: list[Any] = []

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
        win = next((e for e in self.program.elements if e.tag == "Window"), None)
        if win:
            base = win.props.get("theme")
            if isinstance(base, str) and base in THEMES:
                self.theme = THEMES[base]()
        overrides: dict[str, str] = {}
        for el in self.program.elements:
            if el.tag != "Theme":
                continue
            ext = el.props.get("extends")
            if isinstance(ext, str) and ext in THEMES:
                self.theme = THEMES[ext]()
            for color in el.children:
                if color.tag != "Color":
                    continue
                name = color.props.get("name")
                value = color.props.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    overrides[name] = value
        if overrides:
            self.theme.apply(overrides)

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
        self._animations = []
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
        self.app.setStyleSheet(self.theme.qss())  # type: ignore[attr-defined]
        self.root.setWindowTitle(comp.opt_str("title", "PawUI"))  # type: ignore[union-attr]
        self.root.resize(comp.opt_int("width", 480), comp.opt_int("height", 640))  # type: ignore[union-attr]
        self.root.show()  # type: ignore[union-attr]
        QTimer.singleShot(0, self._start_animations)

    def _build_element(self, element: Element, parent: Component | None, scope: dict,
                       delay_bonus: int = 0) -> Component:
        tag = element.tag
        if tag in self.components:
            comp = self._build_component(element, parent, scope, delay_bonus)
            self._animate(comp.widget, element.props, scope, delay_bonus)
            return comp
        if tag in LOGICAL_TAGS:
            return self._build_logical(element, parent, scope, delay_bonus)
        cls = BUILTINS.get(tag)
        if cls is None:
            raise RenderError(f"unknown component <{tag}>", element.pos)
        comp = cls(self, parent, element, scope)
        if parent is not None:
            parent._children.append(comp)
        comp.build()
        self._animate(comp.widget, element.props, scope, delay_bonus)
        if cls.is_container:
            stagger = comp.opt_int("stagger", 0)
            for i, child in enumerate(element.children):
                child_comp = self._build_element(child, comp, scope, delay_bonus + i * stagger)
                comp.layout.addWidget(child_comp.widget, child_comp.stretch())  # type: ignore[attr-defined]
            comp.layout.addStretch(1)  # type: ignore[attr-defined]
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
                if child_comp.widget is not None:
                    lay.addWidget(child_comp.widget, child_comp.stretch())
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
        return result

    def watch_state(self, key: str, fn: Any) -> None:
        self._subscriptions.append(self.state.watch(key, fn))

    def _clear_subscriptions(self) -> None:
        for unsubscribe in self._subscriptions:
            unsubscribe()
        self._subscriptions.clear()

    def register_validator(self, validator: Any) -> None:
        self._validators.append(validator)

    def validate(self) -> bool:
        self.validation_errors = [error for validator in self._validators if (error := validator())]
        return not self.validation_errors

    def set_theme(self, name_or_theme: str | Theme) -> None:
        if isinstance(name_or_theme, Theme):
            self.theme = name_or_theme
        elif isinstance(name_or_theme, str):
            factory = THEMES.get(name_or_theme)
            if factory:
                self.theme = factory()
        self.app.setStyleSheet(self.theme.qss())  # type: ignore[attr-defined]

    def queue_animation(self, widget: QWidget, kind: str, duration: int, delay: int, curve: str) -> None:
        self._animations.append((widget, kind, duration, delay, curve))

    def _start_animations(self) -> None:
        pending, self._animations = self._animations, []
        for widget, kind, duration, delay, curve in pending:
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
            print(f"PawUI rebuild error: {e}", file=__import__("sys").stderr)
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


def render(source: str, filename: str = "<memory>", context: dict | None = None, theme: str = "dark", block: bool = False) -> QWidget | None:
    rt = Runtime(source, filename, context, theme)
    return rt.run(block=block)
