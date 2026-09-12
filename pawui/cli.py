"""PawUI 命令行入口：``pawui app.paw`` 直接运行。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .components import BUILTINS
from .errors import PyxError
from .parser import parse
from .runtime import Runtime

USAGE = """\
PawUI - 轻量、直接运行的 Python 声明式 UI 层

用法:
  pawui <file.paw>            直接运行一个 .paw 文件
  pawui run <file.paw>        同上（显式子命令）
  pawui watch <file.paw>      热重载：文件变化自动重建窗口
  pawui check <file.paw>      语法检查，不运行
  pawui schema                输出组件 Schema (JSON)
  pawui render <file.paw>     离屏渲染并输出信息
  pawui help [topic]          显示随包文档（如 pawui help components）
  pawui --version             打印版本
  pawui --help                显示帮助

示例:
  pawui app.paw
  pawui check app.paw
  pawui schema
  pawui render app.paw
  pawui help theming
"""


SCHEMA = {
    "components": {
        "Window": {
            "props": {
                "title": {"type": "string", "default": "PawUI"},
                "width": {"type": "integer", "default": 480},
                "height": {"type": "integer", "default": 640},
                "theme": {"type": "string", "enum": ["dark", "light"], "default": "dark"},
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
                "accent": {"type": "string", "default": "accent"},
                "bg": {"type": "string", "default": "surface"},
            },
            "description": "Progress bar (self-closing)",
        },
        "Dialog": {
            "props": {"title": {"type": "string"}, "open": {"type": "boolean", "default": True}, "on_accept": {"type": "string"}, "on_reject": {"type": "string"}},
            "description": "Inline dialog panel",
        },
        "Menu": {
            "props": {"label": {"type": "string", "default": "Menu"}, "items": {"type": "array"}, "on_select": {"type": "string"}, "bind": {"type": "string"}},
            "description": "Native popup menu",
        },
        "Form": {
            "props": {"padding": {"type": ["integer", "array"]}, "spacing": {"type": "integer"}},
            "description": "Container for fields validated by app.validate()",
        },
        "Select": {
            "props": {
                "items": {"type": "array", "description": "String list or {$state} reference"},
                "value": {"type": "string", "default": ""},
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
        "extends": {"type": "string", "enum": ["dark", "light"], "default": "dark"},
        "colors": {
            "background": {"type": "string", "default": "#1e1e2e"},
            "surface": {"type": "string", "default": "#282a36"},
            "text": {"type": "string", "default": "#f8f8f2"},
            "subtext": {"type": "string", "default": "#a6adc8"},
            "accent": {"type": "string", "default": "#7aa2f7"},
            "border": {"type": "string", "default": "#44475a"},
            "danger": {"type": "string", "default": "#f7768e"},
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


def help_cmd(topic: str | None = None) -> int:
    """显示随包文档：pawui help 列出主题，pawui help <topic> 打印全文。"""
    d = _docs_dir()
    if d is None:
        print("PawUI: docs not found in this installation", file=sys.stderr)
        return 1
    if topic:
        path = d / f"{topic}.md"
        if not path.exists():
            topics = ", ".join(sorted(p.stem for p in d.glob("*.md")))
            print(f"PawUI: no doc topic '{topic}'. Available: {topics}", file=sys.stderr)
            return 1
        print(path.read_text(encoding="utf-8"))
        return 0
    topics_list = sorted(p.stem for p in d.glob("*.md"))
    print("PawUI docs topics:")
    for t in topics_list:
        print(f"  pawui help {t}")
    return 0


def run(path: str | Path, context: dict[str, Any] | None = None, theme: str = "dark") -> None:
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
        print(f"✓ {p}: syntax OK")
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
        print(f"✓ {p}: render OK")
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
        print(f"  ↻ {p.name} changed, rebuilding…", file=sys.stderr)
        try:
            rt.reload(p.read_text(encoding="utf-8"))
            print("  ✓ reloaded", file=sys.stderr)
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

    if cmd == "render":
        if len(args) < 2:
            print("Usage: pawui render <file.paw>", file=sys.stderr)
            return 2
        return render(args[1])

    if cmd == "help":
        return help_cmd(args[1] if len(args) > 1 else None)

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
