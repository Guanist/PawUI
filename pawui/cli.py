"""PawUI 命令行入口：``pawui app.paw`` 直接运行。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .errors import PyxError
from .parser import parse
from .runtime import Runtime

USAGE = """\
PawUI - 轻量、直接运行的 Python 声明式 UI 层

用法:
  pawui <file.paw>            直接运行一个 .paw 文件
  pawui run <file.paw>        同上（显式子命令）
  pawui check <file.paw>      语法检查，不运行
  pawui schema                输出组件 Schema (JSON)
  pawui render <file.paw>     离屏渲染并输出信息
  pawui --version             打印版本
  pawui --help                显示帮助

示例:
  pawui app.paw
  pawui check app.paw
  pawui schema
  pawui render app.paw
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
            },
            "description": "Text input (self-closing)",
        },
        "Checkbox": {
            "props": {
                "checked": {"type": "boolean", "default": False},
                "on_change": {"type": "string", "description": "Handler(checked)"},
                "size": {"type": "integer", "default": 12},
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
        "interpolation": ["{$var}", "{var}", "$var"],
        "events": "on_click=\"handler\" / on_change=\"handler\" / on_enter=\"handler\"",
        "components": "<Component name=\"Name\">...<Component/>",
        "script": "<script>def handler(): pass</script>",
    },
}


def run(path: str | Path, context: dict[str, Any] | None = None, theme: str = "dark") -> None:
    """读取并运行一个 .paw 文件（阻塞，直到窗口关闭）。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PawUI: file not found: {p}")
    source = p.read_text(encoding="utf-8")
    rt = Runtime(source, str(p), context=context, theme=theme)
    rt.run(block=True)


def check(path: str | Path) -> int:
    """语法检查 .paw 文件，不运行。"""
    p = Path(path)
    if not p.exists():
        print(f"PawUI: file not found: {p}", file=sys.stderr)
        return 1
    source = p.read_text(encoding="utf-8")
    try:
        program = parse(source, str(p))
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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(USAGE, file=sys.stderr)
        return 2

    cmd = args[0]
    if cmd in ("-h", "--help", "help"):
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

    if cmd == "render":
        if len(args) < 2:
            print("Usage: pawui render <file.paw>", file=sys.stderr)
            return 2
        return render(args[1])

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
