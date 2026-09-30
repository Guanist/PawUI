"""PawUI DOM：PythonScript 侧对页面做增删改查的那套 API。

设计目标就是「HTML 能做的这里也能做」：

===========================  ==========================================
浏览器写法                    PawUI 写法
===========================  ==========================================
``document.querySelector``    ``app.query("#save")``
``document.querySelectorAll`` ``app.query_all(".card")``
``el.addEventListener``       ``app.on("#save", "click", fn)``
``el.classList.add``          ``el.add_class("primary")``
``el.style.background``       ``el.css("bg: red;")``
``parent.append(el)``         ``app.append("#list", "<Text>hi</Text>")``
``el.remove()``               ``app.remove("#old")``
===========================  ==========================================

事件回调收到一个 :class:`Event`，里面有 ``target``（元素句柄）、``value``、
``key``、``checked`` 这些浏览器里也有的字段。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QSlider,
    QWidget,
)

from .style import selector_matches

#: 事件名 -> 支持的控件类型（None 表示任意控件都支持）
EVENT_KINDS = ("click", "change", "input", "enter", "hover", "leave", "focus", "blur")


class Event:
    """事件对象：字段跟浏览器那套对齐，脚本不用另学一套。"""

    __slots__ = ("type", "target", "value", "key", "checked", "_default_prevented")

    def __init__(self, kind: str, target: Any = None, value: Any = None,
                 key: str = "", checked: bool | None = None):
        self.type = kind
        self.target = target
        self.value = value
        self.key = key
        self.checked = checked
        self._default_prevented = False

    def prevent_default(self) -> None:
        """占位：Qt 侧没有浏览器的默认行为链，留着是为了写法一致。"""
        self._default_prevented = True

    @property
    def default_prevented(self) -> bool:
        return self._default_prevented

    def __repr__(self) -> str:
        return f"<Event {self.type} value={self.value!r}>"


def widget_text(widget: QWidget) -> str:
    """读控件上的文字（覆盖所有会显示文字的控件类型）。"""
    if isinstance(widget, QLabel):
        return widget.text()
    if isinstance(widget, (QLineEdit, QPlainTextEdit)):
        return widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()
    if isinstance(widget, QAbstractButton):
        return widget.text()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, QProgressBar):
        return str(widget.value())
    return ""


def set_widget_text(widget: QWidget, value: Any) -> bool:
    """写回控件文字。返回是否真的写成功了。"""
    text = str(value)
    if isinstance(widget, QLabel):
        widget.setText(text)
    elif isinstance(widget, QLineEdit):
        widget.setText(text)
    elif isinstance(widget, QPlainTextEdit):
        widget.setPlainText(text)
    elif isinstance(widget, QAbstractButton):
        widget.setText(text)
    elif isinstance(widget, QComboBox):
        widget.setCurrentText(text)
    else:
        return False
    return True


class Element:
    """控件句柄：``app.query("#save").add_class("primary")`` 里的那个对象。"""

    __slots__ = ("runtime", "widget")

    def __init__(self, runtime: Any, widget: QWidget):
        self.runtime = runtime
        self.widget = widget

    # -- 身份 --
    @property
    def id(self) -> str:
        return self.widget.objectName()

    @property
    def tag(self) -> str:
        """自定义组件的名字（``<Card>`` 就是 ``Card``），内置控件回落到 Qt 类名。"""
        tag = self.widget.property("pw-tag")
        if isinstance(tag, str) and tag:
            return tag
        return type(self.widget).__name__

    @property
    def classes(self) -> list[str]:
        raw = self.widget.property("pw-class")
        return str(raw).split() if raw else []

    # -- 内容 --
    @property
    def text(self) -> str:
        return widget_text(self.widget)

    @text.setter
    def text(self, value: Any) -> None:
        set_widget_text(self.widget, value)

    @property
    def value(self) -> Any:
        if isinstance(self.widget, QSlider):
            return self.widget.value()
        if isinstance(self.widget, QProgressBar):
            return self.widget.value()
        if isinstance(self.widget, QAbstractButton) and self.widget.isCheckable():
            return self.widget.isChecked()
        # <Checkbox> 的根是个包一层的容器，真正的开关是它里面的子控件
        toggle = self._checkable()
        if toggle is not None:
            return toggle.isChecked()
        return widget_text(self.widget)

    @value.setter
    def value(self, value: Any) -> None:
        if isinstance(self.widget, QSlider):
            self.widget.setValue(int(value))
        elif isinstance(self.widget, QProgressBar):
            self.widget.setValue(int(value))
        elif isinstance(self.widget, QAbstractButton) and self.widget.isCheckable():
            self.widget.setChecked(bool(value))
        elif (toggle := self._checkable()) is not None:
            toggle.setChecked(bool(value))
        else:
            set_widget_text(self.widget, value)

    def _checkable(self) -> QAbstractButton | None:
        """找这个元素内部真正可勾选的子控件（``<Checkbox>`` 用得上）。"""
        if isinstance(self.widget, QAbstractButton) and self.widget.isCheckable():
            return self.widget
        for child in self.widget.findChildren(QAbstractButton):
            if child.isCheckable():
                return child
        return None

    def attr(self, name: str, value: Any = None) -> Any:
        """动态属性读写 —— 属性选择器 ``[pw-class~=...]`` 认的就是这个。"""
        if value is None:
            return self.widget.property(name)
        self.widget.setProperty(name, value)
        self.runtime.restyle()
        return value

    # -- class --
    def add_class(self, *names: str) -> Element:
        current = self.classes
        for name in names:
            if name and name not in current:
                current.append(name)
        self._set_classes(current)
        return self

    def remove_class(self, *names: str) -> Element:
        drop = set(names)
        self._set_classes([c for c in self.classes if c not in drop])
        return self

    def toggle_class(self, name: str, force: bool | None = None) -> bool:
        has = name in self.classes
        want = (not has) if force is None else bool(force)
        if want:
            self.add_class(name)
        else:
            self.remove_class(name)
        return want

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def _set_classes(self, names: list[str]) -> None:
        self.widget.setProperty("pw-class", " ".join(dict.fromkeys(names)))
        self.runtime.restyle()

    # -- 样式 --
    def css(self, text: str) -> Element:
        """只给这一个控件加样式（等价于 ``#id { … }``，但不用先想 id）。"""
        if not self.widget.objectName():
            self.widget.setObjectName(self.runtime._next_auto_name())
        self.runtime.inject_css(f"#{self.widget.objectName()} {{ {text} }}")
        return self

    # -- 结构 --
    def append(self, markup: str) -> list[Element]:
        return cast("list[Element]", self.runtime.append(str(markup), self.widget))

    def prepend(self, markup: str) -> list[Element]:
        return cast("list[Element]", self.runtime.append(str(markup), self.widget, prepend=True))

    def clear(self) -> None:
        self.runtime.clear_children(self.widget)

    def remove(self) -> None:
        self.runtime.remove_widget(self.widget)

    def children(self) -> list[Element]:
        return [Element(self.runtime, w) for w in self.runtime.child_widgets(self.widget)]

    def closest(self, selector: str) -> Element | None:
        node: QWidget | None = self.widget
        while node is not None:
            if selector_matches(node, selector, self.runtime._selector_tags()):
                return Element(self.runtime, node)
            node = node.parentWidget()
        return None

    def query(self, selector: str) -> Element | None:
        return cast("Element | None", self.runtime.query(selector, root=self.widget))

    def query_all(self, selector: str) -> list[Element]:
        return cast("list[Element]", self.runtime.query_all(selector, root=self.widget))

    # -- 事件 --
    def on(self, kind: str, handler: Callable[[Event], Any]) -> Element:
        self.runtime.bind_event(self.widget, kind, handler)
        return self

    def set_visible(self, visible: bool) -> Element:
        self.widget.setVisible(bool(visible))
        return self

    def focus(self) -> Element:
        self.widget.setFocus()
        return self

    def __repr__(self) -> str:
        ident = f"#{self.id}" if self.id else ""
        return f"<Element {self.tag}{ident}>"
