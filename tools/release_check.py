#!/usr/bin/env python3
"""发布前校验：tag 与版本号一致、CHANGELOG 有对应段落、示例能过 check。

由 ``.github/workflows/release.yml`` 调用，本地发版前也可以直接跑：

    python tools/release_check.py v0.1.3.2
    python tools/release_check.py            # 不传 tag 就只校验版本 + CHANGELOG
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("pyproject.toml 里找不到 version")
    return match.group(1)


def init_version() -> str:
    text = (ROOT / "pawui" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("pawui/__init__.py 里找不到 __version__")
    return match.group(1)


def changelog_section(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(version)}\].*?$", text, re.M)
    if not match:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^## \[", rest, re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def main(argv: list[str]) -> int:
    tag = argv[1] if len(argv) > 1 else ""
    problems: list[str] = []

    version = read_version()
    print(f"pyproject version : {version}")
    print(f"__init__ version  : {init_version()}")

    if init_version() != version:
        problems.append(
            f"pawui/__init__.py 的 __version__ ({init_version()}) "
            f"与 pyproject.toml ({version}) 不一致"
        )

    if tag:
        stripped = tag.lstrip("v")
        print(f"tag               : {tag}")
        if stripped != version:
            problems.append(f"tag {tag} 与 pyproject.toml 的 {version} 不一致")

    section = changelog_section(version)
    if section:
        lines = len(section.splitlines())
        print(f"CHANGELOG [{version}] : {lines} 行")
    else:
        problems.append(f"CHANGELOG.md 里没有 ## [{version}] 段落")

    # 示例必须还能过 check，否则发出去的包带一个坏示例
    showcase = ROOT / "examples" / "showcase.paw"
    if showcase.is_file():
        sys.path.insert(0, str(ROOT))
        from pawui.cli import check

        code = check(str(showcase))
        print(f"examples/showcase.paw : {'OK' if code == 0 else 'FAIL'}")
        if code != 0:
            problems.append("examples/showcase.paw 没通过 pawui check")
    else:
        print("examples/showcase.paw : (不存在，跳过)")

    print()
    if problems:
        for item in problems:
            print(f"  ! {item}")
        print("\n校验失败")
        return 1
    print("校验通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
