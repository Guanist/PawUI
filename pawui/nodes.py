"""PyX AST / UI Tree 节点定义。

解析器输出一棵由 Element / ScriptBlock 组成的内存树，运行时据此构建真正的 Tk 界面。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import Position


@dataclass
class Element:
    """一个 UI 元素节点。tag 是元素名，props 是属性字典，children 是子节点。"""

    tag: str
    props: dict[str, Any] = field(default_factory=dict)
    children: list[Element] = field(default_factory=list)
    pos: Position | None = None
    name: str | None = None  # component 定义时使用
    is_block: bool = False      # 该元素是否以 `:` 结尾，允许有子节点


@dataclass
class ScriptBlock:
    """顶层 script 块，内含一段原始 Python 源码。"""

    source: str
    pos: Position | None = None


@dataclass
class Program:
    """整个 .pyx 文件的解析结果。"""

    elements: list[Element] = field(default_factory=list)
    script: ScriptBlock | None = None


@dataclass
class ComponentDef:
    """已注册的组件定义：组件名 -> 组件的模板树。"""

    name: str
    root: Element
    pos: Position | None = None


@dataclass
class Symbol:
    """一个未定型的符号引用。

    解析器在遇到裸名字（如事件绑定的 on_click=greet、组件传参 title=headline）
    时生成它，最终由运行时解析为 callable、prop 或 state 值。
    """

    name: str
    pos: Position
