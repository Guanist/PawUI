#!/usr/bin/env python3
"""从 CHANGELOG.md 里抠出指定版本的正文，用于 GitHub Release。

    python tools/release_notes.py v0.1.3.2 > notes.md

找不到该版本时回落成一行标题，不让发布流程因为「还没写 CHANGELOG」而中断 ——
``tools/release_check.py`` 那边会把缺失的段落判成失败，职责分开。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def notes(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(version)}\].*?$", text, re.M)
    if not match:
        return f"PawUI {version}"
    rest = text[match.end():]
    nxt = re.search(r"^## \[", rest, re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: python tools/release_notes.py vX.Y.Z", file=sys.stderr)
        return 2
    print(notes(argv[1].lstrip("v")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
