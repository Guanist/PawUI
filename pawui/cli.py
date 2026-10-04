"""PawUI 命令行入口：``pawui app.paw`` 直接运行。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import docsfeed
from .errors import PyxError
from .parser import parse
from .runtime import Runtime

# check 必须和 runtime 用**同一份**注册表，否则会把 runtime 明明支持的组件
# 判成 unknown。`components.BUILTINS` 只是基础 22 个，`widgets.BUILTINS`
# 才是合并后的 44 个全量（widgets 里的注释也写明「runtime 只认这一份」）。
# 这里放在 runtime 之后导入：widgets 依赖 components，顺序反过来会有循环导入风险。
from .widgets import BUILTINS  # noqa: E402

# Windows 控制台默认编码是 cp936：stdout 一旦被管道 / 文件 / CI 日志捕获，
# 非 ASCII 输出会直接抛 UnicodeEncodeError 把整个命令带崩（退出码 1）。
# 这里兜底成「替换」而不是抛异常 —— 控制台本身反而是安全的。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

USAGE = """\
PawUI - 轻量、直接运行的 Python 声明式 UI 层

用法:
  pawui <file.paw>            直接运行一个 .paw 文件
  pawui run <file.paw>        同上（显式子命令）
  pawui watch <file.paw>      热重载：文件变化自动重建窗口
  pawui check <file.paw>      语法检查，不运行
  pawui schema                输出组件 Schema (JSON)
  pawui render <file.paw>     离屏渲染并输出信息
  pawui inspect <file.paw>    打印控件树 / 命中的 CSS / state 订阅
  pawui help [topic]          显示文档（线上获取，离线回落随包）
  pawui help --refresh        强制刷新线上文档
  pawui --version             打印版本
  pawui --help                显示帮助

示例:
  pawui app.paw
  pawui check app.paw
  pawui schema
  pawui render app.paw
  pawui inspect app.paw
  pawui help theming
  pawui help --refresh
"""


SCHEMA = {
    "components": {
        "Window": {
            "props": {
                "title": {"type": "string", "default": "PawUI"},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 640},
                "theme": {"type": "string", "enum": ["dark", "light"], "default": "light"},
                "padding": {"type": "integer", "default": 0},
                "spacing": {"type": "integer", "default": 8},
            },
            "description": "Root window (exactly one per file)",
        },
        "Column": {
            "props": {
                "padding": {"type": ["integer", "array"], "default": 12},
                "spacing": {"type": "integer", "default": 8},
                "bg": {"type": "string", "description": "Background color"},
                "radius": {"type": "integer", "default": 24},
                "expand": {"type": "boolean", "default": False},
                "stagger": {"type": "integer", "default": 0},
            },
            "description": "Vertical container",
        },
        "Row": {
            "props": {
                "padding": {"type": ["integer", "array"], "default": 12},
                "spacing": {"type": "integer", "default": 8},
                "bg": {"type": "string", "description": "Background color"},
                "radius": {"type": "integer", "default": 24},
                "expand": {"type": "boolean", "default": False},
                "stagger": {"type": "integer", "default": 0},
            },
            "description": "Horizontal container",
        },
        "Text": {
            "props": {
                "size": {"type": "integer", "default": 12},
                "font": {"type": "string", "description": "Font family override"},
                "bold": {"type": "boolean", "default": False},
                "italic": {"type": "boolean", "default": False},
                "color": {"type": "string", "default": "text"},
                "fg": {"type": "string", "default": "text"},
            },
            "description": "Text display (content between tags)",
        },
        "Button": {
            "props": {
                "on_click": {"type": "string", "description": "Handler function name"},
                "bg": {"type": "string", "default": "accent"},
                "fg": {"type": "string", "default": "background"},
                "size": {"type": "integer", "default": 12},
                "radius": {"type": "integer", "default": 17},
                "disabled": {"type": "boolean", "default": False},
            },
            "description": "Clickable button (label between tags)",
        },
        "Input": {
            "props": {
                "placeholder": {"type": "string", "default": ""},
                "value": {"type": "string", "default": ""},
                "on_change": {"type": "string", "description": "Handler(text)"},
                "on_enter": {"type": "string", "description": "Handler(text)"},
                "size": {"type": "integer", "default": 14},
                "radius": {"type": "integer", "default": 10},
                "font": {"type": "string", "description": "Font family override"},
                "show": {"type": "string", "enum": ["", "password"], "default": ""},
                "bind": {"type": "string", "description": "Two-way bind to state key"},
                "required": {"type": "boolean", "default": False},
                "min_length": {"type": "integer", "default": 0},
                "error": {"type": "string"},
            },
            "description": "Text input (self-closing)",
        },
        "Checkbox": {
            "props": {
                "checked": {"type": "boolean", "default": False},
                "on_change": {"type": "string", "description": "Handler(checked)"},
                "size": {"type": "integer", "default": 12},
                "bind": {"type": "string", "description": "Two-way bind to state key"},
            },
            "description": "Toggle switch (label between tags)",
        },
        "Divider": {
            "props": {
                "color": {"type": "string", "default": "border"},
                "thickness": {"type": "integer", "default": 2},
            },
            "description": "Horizontal divider (self-closing)",
        },
        "Spacer": {
            "props": {
                "width": {"type": "integer", "default": 1},
                "height": {"type": "integer", "default": 1},
            },
            "description": "Empty space (self-closing)",
        },
        "Slider": {
            "props": {
                "min": {"type": "integer", "default": 0},
                "max": {"type": "integer", "default": 100},
                "value": {"type": "integer", "default": 0},
                "step": {"type": "integer", "default": 1},
                "on_change": {"type": "string", "description": "Handler(value)"},
                "accent": {"type": "string", "default": "accent"},
                "bg": {"type": "string", "default": "border"},
                "radius": {"type": "integer", "default": 3},
                "bind": {"type": "string", "description": "Two-way bind to state key"},
            },
            "description": "Horizontal value slider (self-closing)",
        },
        "Progress": {
            "props": {
                "value": {"type": "integer", "default": 0},
                "max": {"type": "integer", "default": 100},
                "height": {"type": "integer", "default": 10},
                "text": {"type": "boolean", "default": False},
                "align": {"type": "string", "enum": ["left", "center", "right"], "default": "center"},
                "radius": {"type": "integer", "default": 5},
                "fg": {"type": "string", "default": "text"},
                "accent": {"type": "string", "default": "accent"},
                "bg": {"type": "string", "default": "surface"},
            },
            "description": "Progress bar (self-closing)",
        },
        "Dialog": {
            "props": {"title": {"type": "string"}, "open": {"type": "boolean", "default": True},
                      "radius": {"type": "integer", "default": 12},
                      "button_radius": {"type": "integer", "default": 10},
                      "cancel": {"type": "string", "default": "Cancel"},
                      "accept": {"type": "string", "default": "OK"},
                      "on_accept": {"type": "string"}, "on_reject": {"type": "string"}},
            "description": "Inline dialog panel",
        },
        "Menu": {
            "props": {"label": {"type": "string", "default": "Menu"},
                      "items": {"type": "array", "description": "[a, b, c] / {$list}"},
                      "bg": {"type": "string", "default": "surface"},
                      "fg": {"type": "string", "default": "text"},
                      "radius": {"type": "integer", "default": 10},
                      "on_select": {"type": "string"}, "bind": {"type": "string"}},
            "description": "Native popup menu",
        },
        "Form": {
            "props": {"padding": {"type": ["integer", "array"]}, "spacing": {"type": "integer"}},
            "description": "Container for fields validated by app.validate()",
        },
        "Select": {
            "props": {
                "items": {"type": "array", "description": "[a, b, c] / a, b, c / {$state} reference"},
                "value": {"type": "string", "default": ""},
                "placeholder": {"type": "string", "default": "", "description": "Shown when nothing is selected"},
                "on_change": {"type": "string", "description": "Handler(value)"},
                "bind": {"type": "string", "description": "Two-way bind to state key"},
            },
            "description": "Native dropdown selector",
        },
        "Tabs": {
            "props": {"bg": {"type": "string", "default": "background"}},
            "description": "Tabbed container; children are pages (use <Tab label=...>)",
        },
        "Image": {
            "props": {
                "src": {"type": "string", "description": "Image path or source"},
                "width": {"type": "integer", "description": "Target width"},
                "height": {"type": "integer", "description": "Target height"},
                "cover": {"type": "boolean", "default": False},
            },
            "description": "Image display (self-closing)",
        },
        "Tooltip": {
            "props": {"text": {"type": "string", "description": "Tooltip text"}},
            "description": "Wraps a child; hover shows tooltip",
        },
        "TextArea": {
            "props": {
                "value": {"type": "string", "description": "Initial text or {$state} template"},
                "placeholder": {"type": "string"},
                "on_change": {"type": "string", "description": "Handler(text)"},
                "readonly": {"type": "boolean", "default": False},
                "height": {"type": "integer", "description": "Fixed height (px)"},
                "radius": {"type": "integer", "default": 10},
                "font": {"type": "string", "description": "Font family override"},
                "bind": {"type": "string", "description": "Two-way bind to state key"},
            },
            "description": "Multiline text editor (self-closing)",
        },
        "Scroll": {
            "props": {
                "bg": {"type": "string"},
                "spacing": {"type": "integer"},
                "padding": {"type": "string", "description": "int or tuple"},
                "axis": {"type": "string", "enum": ["y", "x"], "default": "y"},
            },
            "description": "Scrollable container; children overflow-scroll",
        },
        "Web": {
            "props": {
                "src": {"type": "string", "description": "URL to load"},
                "html": {"type": "string", "description": "Inline HTML (if no src)"},
            },
            "description": "iframe-like embedded web view (requires PySide6-Addons)",
        },
        "If": {
            "props": {"condition": {"type": "boolean", "description": "Render when truthy"}},
            "description": "Conditional logical container",
        },
        "For": {
            "props": {
                "each": {"type": "string", "default": "item"},
                "in": {"type": "array", "description": "List reference ({$items})"},
            },
            "description": "List loop logical container",
        },
        "Grid": {
            "props": {"columns": {"type": "integer", "default": 2}, "gap": {"type": "integer"}},
            "description": "Grid container (row-major auto placement)",
        },
        "Radio": {
            "props": {"value": {"type": "string"}, "checked": {"type": "boolean"}},
            "description": "Radio button (put inside <RadioGroup>)",
        },
        "RadioGroup": {
            "props": {
                "value": {"type": "string", "description": "Selected value / {$state}"},
                "on_change": {"type": "string"}, "bind": {"type": "string"},
            },
            "description": "Exclusive radio group",
        },
        "Segmented": {
            "props": {
                "items": {"type": "array", "description": "[a, b, c] / {$list}"},
                "value": {"type": "string"}, "on_change": {"type": "string"},
                "bind": {"type": "string"}, "radius": {"type": "integer", "default": 9},
            },
            "description": "iOS-style segmented control",
        },
        "NumberInput": {
            "props": {
                "min": {"type": "integer", "default": 0}, "max": {"type": "integer"},
                "step": {"type": "integer", "default": 1}, "value": {"type": "integer"},
                "on_change": {"type": "string"}, "bind": {"type": "string"},
            },
            "description": "Numeric input with stepper",
        },
        "DatePicker": {
            "props": {
                "value": {"type": "string", "default": "today (yyyy-MM-dd)"},
                "format": {"type": "string", "default": "yyyy-MM-dd"},
                "on_change": {"type": "string"}, "bind": {"type": "string"},
            },
            "description": "Date picker with calendar popup",
        },
        "TimePicker": {
            "props": {
                "value": {"type": "string", "default": "now (HH:mm)"},
                "format": {"type": "string", "default": "HH:mm"},
                "on_change": {"type": "string"},
            },
            "description": "Time picker",
        },
        "FilePicker": {
            "props": {
                "label": {"type": "string"}, "mode": {"type": "string", "enum": ["open", "save", "dir"]},
                "filter": {"type": "string"}, "on_pick": {"type": "string", "description": "Handler(path)"},
            },
            "description": "Button that opens a native file dialog",
        },
        "Badge": {
            "props": {
                "text": {"type": "string"}, "bg": {"type": "string", "default": "accent"},
                "fg": {"type": "string"}, "size": {"type": "integer"}, "radius": {"type": "integer"},
            },
            "description": "Small status pill",
        },
        "Avatar": {
            "props": {
                "src": {"type": "string"}, "initials": {"type": "string"},
                "size": {"type": "integer", "default": 40},
                "bg": {"type": "string", "default": "accent"}, "fg": {"type": "string"},
            },
            "description": "Round avatar (image or initials)",
        },
        "Skeleton": {
            "props": {
                "width": {"type": "integer", "default": 120}, "height": {"type": "integer"},
                "radius": {"type": "integer", "default": 6}, "animate": {"type": "boolean", "default": True},
            },
            "description": "Pulsing placeholder block",
        },
        "Spinner": {
            "props": {
                "size": {"type": "integer", "default": 22}, "color": {"type": "string"},
                "thickness": {"type": "integer", "default": 3},
            },
            "description": "Rotating loading spinner",
        },
        "Link": {
            "props": {"href": {"type": "string"}, "external": {"type": "boolean", "default": True},
                      "on_click": {"type": "string"}},
            "description": "Clickable text link",
        },
        "CodeBlock": {
            "props": {"language": {"type": "string"}, "height": {"type": "integer"},
                      "numbers": {"type": "boolean", "default": False}},
            "description": "Monospace read-only code block",
        },
        "Markdown": {
            "props": {"size": {"type": "integer"}},
            "description": "Markdown-rendered text block",
        },
        "Panel": {
            "props": {"title": {"type": "string"}, "open": {"type": "boolean", "default": False},
                      "on_toggle": {"type": "string"}},
            "description": "Collapsible panel",
        },
        "Accordion": {
            "props": {"multiple": {"type": "boolean", "default": True}},
            "description": "Stack of panels (multiple=false keeps one open)",
        },
        "SplitPane": {
            "props": {"axis": {"type": "string", "enum": ["x", "y"], "default": "x"},
                      "ratio": {"type": "number", "default": 0.5}, "handle": {"type": "integer"}},
            "description": "Draggable two-pane splitter",
        },
        "List": {
            "props": {"items": {"type": "array"}, "value": {"type": "string"},
                      "height": {"type": "integer", "default": 180},
                      "on_select": {"type": "string"}, "bind": {"type": "string"}},
            "description": "Selectable list",
        },
        "Table": {
            "props": {
                "columns": {"type": "array", "description": "[Name, Age]"},
                "rows": {"type": "array", "description": "[{...}, ...] or [[...], ...] / {$state}"},
                "sortable": {"type": "boolean", "default": True},
                "striped": {"type": "boolean", "default": True},
                "index": {"type": "boolean", "default": False},
                "height": {"type": "integer", "default": 240},
                "on_select": {"type": "string", "description": "Handler([cell, cell, ...])"},
            },
            "description": "Sortable data table",
        },
        "VirtualList": {
            "props": {
                "rows": {"type": "array", "description": "Any length; only visible rows are built"},
                "row_height": {"type": "integer", "default": 34},
                "height": {"type": "integer", "default": 400},
                "each": {"type": "string", "default": "item"},
                "gap": {"type": "integer", "default": 0},
            },
            "description": "Virtual scrolling list (constant cost for 100k rows)",
        },
        "Canvas": {
            "props": {
                "width": {"type": "integer", "default": 320}, "height": {"type": "integer", "default": 200},
                "on_draw": {"type": "string", "description": "Handler(painter)"},
                "on_press": {"type": "string", "description": "Handler(x, y)"},
            },
            "description": "Custom QPainter surface",
        },
        "Shortcut": {
            "props": {"keys": {"type": "string", "description": "Ctrl+S"}, "on_press": {"type": "string"}},
            "description": "Application-wide keyboard shortcut",
        },
    },
    "animation_props": {
        "animate": {
            "type": "string",
            "enum": ["fade", "reveal", "slide-up", "slide-down", "slide-left", "slide-right"],
            "description": "Entrance animation type",
        },
        "duration": {"type": "integer", "default": 260, "description": "Animation duration (ms)"},
        "delay": {"type": "integer", "default": 0, "description": "Initial delay (ms)"},
        "easing": {
            "type": "string",
            "enum": ["linear", "in-cubic", "out-cubic", "in-out-cubic", "out-quad", "out-quart", "out-back", "out-elastic"],
            "default": "out-cubic",
            "description": "Easing curve",
        },
    },
    "theme": {
            "extends": {"type": "string", "enum": ["dark", "light"], "default": "light"},
            "colors": {
                "background": {"type": "string", "default": "#f5f5f7"},
                "surface": {"type": "string", "default": "#ffffff"},
                "text": {"type": "string", "default": "#1d1d1f"},
                "subtext": {"type": "string", "default": "#6e6e73"},
                "accent": {"type": "string", "default": "#0071e3"},
                "border": {"type": "string", "default": "#d2d2d7"},
                "danger": {"type": "string", "default": "#ff375f"},
            },
            "font": {
                "font_family": {"type": "string", "default": "Microsoft YaHei UI"},
                "font_size": {"type": "integer", "default": 12},
            },
        "custom_colors": {"type": "object", "description": "Additional named colors"},
    },
    "syntax": {
        "interpolation": ["{$var}", "{var}", "$var", "{$item.name}", "{$items[0]}"],
        "events": "on_click=\"handler\" / on_change=\"handler\" / on_enter=\"handler\"",
        "components": "<Component name=\"Name\">...<Component/>",
        "default_props": "<Component name=\"Card\"><Prop name=\"label\" default=\"x\"/>...</Component>",
        "binding": "bind=\"name\" (Input/Checkbox/Slider writes back to state)",
        "control_flow": "<If condition=\"{$flag}\">...</If> / <For each=\"item\" in=\"{$items}\">...</For>",
        "script": "<script>def handler(): pass</script>",
        "style": "<Style>Card { radius: 12px; } .card Text { color: var(--fg); }</Style>",
        "style_vars": ":root { --brand: #ff7a1a; } 然后 var(--brand) / var(--x, 兜底)",
        "selectors": "Tag / .class / #id / [attr=value] / 后代 / 子代 > / 逗号分组 / :hover",
        "text_props": "wrap / ellipsis / align / selectable / line-height（QSS 不认，运行时施加）",
        "box_model": "margin / padding / border / border_width / border_color / width / height / min_* / max_*",
        "flex": "grow / shrink / wrap / justify / align / gap",
        "dom": "app.query(sel) / app.query_all / app.append(sel, \"<Text>x</Text>\") / app.remove / app.on(sel, kind, fn)",
        "event_kinds": ["click", "change", "input", "enter", "hover", "leave", "focus", "blur"],
        "inject_css": "app.inject_css(\"Button { radius: 6px; }\") / app.css(\".card\", \"radius: 6;\")",
        "a11y": "aria_label / aria_description / tabindex",
        "toast": "app.toast(\"已保存\", \"success\")",
        "form": "<Form on_submit=\"fn\"> + app.validate() / app.submit()，错误画在字段上",
        "ready": "ready(fn) —— 控件树建好之后才跑，脚本里访问控件的正确姿势",
    },
}


def _docs_dir() -> Path | None:
    """随包文档目录：优先源码仓库 docs/，其次安装后的 share/pawui/docs。"""
    candidates = (
        Path(__file__).resolve().parent.parent / "docs",
        Path(sys.prefix) / "share" / "pawui" / "docs",
    )
    for c in candidates:
        if c.is_dir():
            return c
    return None


def help_cmd(topic: str | None = None, refresh: bool = False,
             use_network: bool = True) -> int:
    """显示文档：**线上优先，随包兜底**。

    线上那份就是站点渲染用的 ``static/data.js``（正文的单一事实源是仓库
    ``docs/``）—— 所以改文档不用发新版，装了旧版的用户也能读到最新内容。
    离线 / 内网拿不到时就静默回落到随包的 ``docs/``。

    ``pawui help <topic>`` 打印全文，``pawui help`` 列出主题，
    ``pawui help --refresh`` 强制重拉线上文档。
    """
    feed, source = docsfeed.get_feed(refresh=refresh, use_network=use_network)
    d = _docs_dir()
    if topic:
        body = docsfeed.topic_body(feed, topic)
        if body is not None:
            print(body)
            origin = ("线上文档 pawui.pages.dev" if source == "online"
                      else "本地缓存（线上文档）")
            print(f"\n— 来源: {origin} · topic: {topic}")
            return 0
        if d is not None:
            path = d / f"{topic}.md"
            if path.exists():
                print(path.read_text(encoding="utf-8"))
                print(f"\n— 来源: 随包文档（离线回落）· topic: {topic}")
                return 0
        available = ", ".join(t for t, _ in docsfeed.topic_list(feed)) or \
            ", ".join(sorted(p.stem for p in d.glob("*.md"))) if d is not None else ""
        print(f"PawUI: no doc topic '{topic}'. Available: {available}", file=sys.stderr)
        return 1
    entries = docsfeed.topic_list(feed)
    if entries:
        origin = "线上文档 pawui.pages.dev" if source == "online" else "本地缓存（线上文档）"
        print(f"PawUI docs ({len(entries)} 篇 · 来源: {origin}):")
        for name, title in entries:
            print(f"  pawui help {name:<26} {title}")
        print("\n提示: pawui help --refresh 强制刷新线上文档；"
              "PAWUI_DOCS_OFFLINE=1 只用本地。")
        return 0
    if d is None:
        print("PawUI: docs not found in this installation", file=sys.stderr)
        return 1
    topics_list = sorted(p.stem for p in d.glob("*.md"))
    print("PawUI docs topics (随包文档 · 离线):")
    for t in topics_list:
        print(f"  pawui help {t}")
    return 0


def run(path: str | Path, context: dict[str, Any] | None = None, theme: str = "light") -> None:
    """读取并运行一个 .paw 文件（阻塞，直到窗口关闭）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PawUI: file not found: {p}")
    source = p.read_text(encoding="utf-8")
    rt = Runtime(source, str(p), context=context, theme=theme)
    rt.run(block=True)


def _validate_program(program: Any) -> list[str]:
    errors: list[str] = []
    definitions = {el.name for el in program.elements if el.tag == "component" and el.name}
    seen: set[str] = set()
    for el in program.elements:
        if el.tag == "component" and el.name:
            if el.name in seen:
                errors.append(f"duplicate component: {el.name}")
            seen.add(el.name)
    top = [el for el in program.elements if el.tag not in ("component", "Theme")]
    windows = [el for el in top if el.tag == "Window"]
    if len(windows) > 1:
        errors.append("only one root <Window> is allowed")
    if windows and len(top) > 1:
        errors.append("top-level elements must live inside <Window>")

    def visit(el: Any) -> None:
        if el.tag not in BUILTINS and el.tag not in ("If", "For", "Tab") and el.tag not in definitions:
            errors.append(f"unknown component <{el.tag}>")
        if el.tag == "If" and ("condition" not in el.props or not el.children):
            errors.append("<If> requires condition and at least one child")
        if el.tag == "For" and ("in" not in el.props or not el.children):
            errors.append("<For> requires in and at least one child")
        if el.tag == "Scroll" and str(el.props.get("axis", "y")) not in ("x", "y"):
            errors.append('<Scroll axis> must be "x" or "y"')
        for child in el.children:
            visit(child)

    for el in top:
        visit(el)
    return errors


def check(path: str | Path) -> int:
    """语法检查 .paw 文件，不运行。"""
    p = Path(path)
    if not p.exists():
        print(f"PawUI: file not found: {p}", file=sys.stderr)
        return 1
    source = p.read_text(encoding="utf-8")
    try:
        program = parse(source, str(p))
        errors = _validate_program(program)
        if errors:
            for error in errors:
                print(f"{p}: error: {error}", file=sys.stderr)
            return 1
        print(f"[OK] {p}: syntax OK")
        print(f"  Elements: {len(program.elements)}")
        print(f"  Script: {'yes' if program.script else 'no'}")
        for el in program.elements:
            if el.tag == "component":
                print(f"  Component: {el.name}")
        return 0
    except PyxError as e:
        print(e.formatted(), file=sys.stderr)
        return 1


def schema_cmd() -> int:
    """输出组件 Schema (JSON)。"""
    print(json.dumps(SCHEMA, indent=2, ensure_ascii=False))
    return 0


def render(path: str | Path) -> int:
    """离屏渲染并输出信息。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    p = Path(path)
    if not p.exists():
        print(f"PawUI: file not found: {p}", file=sys.stderr)
        return 1

    source = p.read_text(encoding="utf-8")
    try:
        rt = Runtime(source, str(p))
        rt.run(block=False)
        print(f"[OK] {p}: render OK")
        if rt.root:
            print(f"  Window: {rt.root.windowTitle()}")
            size = rt.root.size()
            print(f"  Size: {size.width()}x{size.height()}")
            rt.root.close()
        return 0
    except PyxError as e:
        print(e.formatted(), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"PawUI render error: {e}", file=sys.stderr)
        return 1


def inspect(path: str | Path) -> int:
    """打印控件树 + 命中的 CSS 规则 + state 订阅（样式不生效时先看它）。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    p = Path(path)
    if not p.exists():
        print(f"PawUI: file not found: {p}", file=sys.stderr)
        return 1
    source = p.read_text(encoding="utf-8")
    try:
        rt = Runtime(source, str(p))
        rt.run(block=False)
    except PyxError as e:
        print(e.formatted(), file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"PawUI inspect error: {e}", file=sys.stderr)
        return 1
    print(f"# {p}")
    print(rt.inspect_tree())
    if rt.root is not None:
        rt.root.close()
    return 0


def watch(path: str | Path) -> int:
    """热重载：监视文件，变化时重建窗口。"""
    p = Path(path)
    if not p.exists():
        print(f"PawUI: file not found: {p}", file=sys.stderr)
        return 1

    from PySide6.QtCore import QTimer

    source = p.read_text(encoding="utf-8")
    rt = Runtime(source, str(p))
    rt.run(block=False)
    last: tuple[int, int] = (p.stat().st_mtime_ns, p.stat().st_size)

    def poll() -> None:
        nonlocal last
        try:
            now = (p.stat().st_mtime_ns, p.stat().st_size)
        except OSError:
            return
        if now == last:
            return
        last = now
        print(f"  .. {p.name} changed, rebuilding...", file=sys.stderr)
        try:
            rt.reload(p.read_text(encoding="utf-8"))
            print("  [OK] reloaded", file=sys.stderr)
        except PyxError as e:
            print(e.formatted(), file=sys.stderr)
        except Exception as e:
            print(f"PawUI rebuild error: {e}", file=sys.stderr)

    timer = QTimer()
    timer.setInterval(400)
    timer.timeout.connect(poll)
    timer.start()
    rt.app.exec()
    timer.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 2

    cmd = args[0]
    if cmd in ("-h", "--help"):
        print(USAGE)
        return 0
    if cmd in ("-v", "--version"):
        from . import __version__
        print(f"PawUI {__version__}")
        return 0

    if cmd == "check":
        if len(args) < 2:
            print("Usage: pawui check <file.paw>", file=sys.stderr)
            return 2
        return check(args[1])

    if cmd == "schema":
        return schema_cmd()

    if cmd == "watch":
        if len(args) < 2:
            print("Usage: pawui watch <file.paw>", file=sys.stderr)
            return 2
        return watch(args[1])

    if cmd == "inspect":
        if len(args) < 2:
            print("Usage: pawui inspect <file.paw>", file=sys.stderr)
            return 2
        return inspect(args[1])

    if cmd == "render":
        if len(args) < 2:
            print("Usage: pawui render <file.paw>", file=sys.stderr)
            return 2
        return render(args[1])

    if cmd == "help":
        rest = [a for a in args[1:] if a not in ("--refresh", "--offline")]
        return help_cmd(
            rest[0] if rest else None,
            refresh="--refresh" in args,
            use_network="--offline" not in args,
        )

    file = args[1] if cmd == "run" else cmd
    if not file:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        run(file)
    except PyxError as e:
        print(e.formatted(), file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
