#!/usr/bin/env python3
"""PawUI 发版一条龙。

凭据**不放在仓库里**（仓库是公开的），从仓库外的文件读：

``~/.pypirc``                twine 直接认，PyPI 令牌写在这儿
``~/.pawui/secrets.env``     GITHUB_TOKEN / SITE_REPO（KEY=VALUE，别提交）

用法::

    python tools/release.py build     # 清 dist + python -m build + twine check
    python tools/release.py upload    # twine upload（读 ~/.pypirc）
    python tools/release.py publish   # 打 tag + push + 建 GitHub Release
    python tools/release.py site      # docs 同步到站点仓库 + 重建 data.js + 推送
    python tools/release.py all       # build → upload → publish

版本号来自 ``pyproject.toml``；GitHub Release 的正文自动从 ``CHANGELOG.md``
里那一段抠出来。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS = Path.home() / ".pawui" / "secrets.env"
SITE_DIR = Path("D:/PawUI-Site")


def read_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("pyproject.toml 里找不到 version")
    return match.group(1)


def load_secrets() -> dict[str, str]:
    """仓库外的 KEY=VALUE 文件；已有环境变量优先。"""
    out: dict[str, str] = {}
    if SECRETS.exists():
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    for key in ("GITHUB_TOKEN", "SITE_REPO"):
        if os.environ.get(key):
            out[key] = os.environ[key]
    return out


def redact(text: str) -> str:
    """把命令行里的凭据换成 ***，免得 token 被打印进终端/日志/会话记录。

    匹配 ``scheme://user:secret@host`` 里的 ``user:secret`` 段（含
    ``x-access-token:<token>@`` 这种形式），整体替换成 ``***:***``。
    """
    return re.sub(r"(://)[^/@\s]+:[^/@\s]+@", r"\1***:***@", text)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {redact(' '.join(cmd))}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), text=True,
                            capture_output=True, encoding="utf-8", errors="replace")
    tail = (result.stdout or "").strip().splitlines()
    for line in tail[-6:]:
        print("  " + redact(line))
    if result.returncode != 0 and check:
        err = (result.stderr or "").strip().splitlines()
        for line in err[-8:]:
            print("  ! " + redact(line))
        raise SystemExit(f"命令失败（{result.returncode}）: {' '.join(cmd)}")
    return result


def changelog_section(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(rf"^## \[{re.escape(version)}\].*?$", re.M)
    match = pattern.search(text)
    if not match:
        return f"PawUI {version}"
    rest = text[match.end():]
    nxt = re.search(r"^## \[", rest, re.M)
    return rest[: nxt.start()].strip() if nxt else rest.strip()


def cmd_build() -> None:
    dist = ROOT / "dist"
    if dist.exists():
        for item in dist.iterdir():
            item.unlink()
        print(f"cleared {dist}")
    run([sys.executable, "-m", "build"])
    run([sys.executable, "-m", "twine", "check", *[str(p) for p in sorted(dist.iterdir())]])


def cmd_upload() -> None:
    files = [str(p) for p in sorted((ROOT / "dist").iterdir())]
    if not files:
        raise SystemExit("dist/ 是空的，先跑 build")
    # --skip-existing：重复跑 all 不会因为「这个版本已经在 PyPI 上」直接炸
    run([sys.executable, "-m", "twine", "upload", "--non-interactive",
         "--disable-progress-bar", "--skip-existing", *files])


def git_push(secrets: dict[str, str], *refs: str) -> None:
    token = secrets.get("GITHUB_TOKEN", "")
    if token:
        # URL 里带 token，但 run() 会把它脱敏后再打印
        url = f"https://x-access-token:{token}@github.com/LK-BLOG/PawUI.git"
        run(["git", "push", url, *refs])
    else:
        run(["git", "push", "origin", *refs])


def cmd_publish() -> None:
    version = read_version()
    tag = f"v{version}"
    secrets = load_secrets()
    existing = run(["git", "tag", "-l", tag]).stdout.strip()
    if not existing:
        run(["git", "tag", "-a", tag, "-m", f"PawUI {version}"])
    git_push(secrets, "main", tag)
    token = secrets.get("GITHUB_TOKEN", "")
    if not token:
        print("没有 GITHUB_TOKEN，跳过建 Release（tag 已经推上去了）")
        return
    payload = json.dumps({
        "tag_name": tag,
        "name": f"PawUI {version}",
        "body": changelog_section(version),
        "draft": False,
        "prerelease": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/repos/LK-BLOG/PawUI/releases",
        data=payload, method="POST",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "pawui-release",
                 "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        print(f"release: {data.get('html_url')}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"建 Release 失败：{error.code} {detail}")


def cmd_site() -> None:
    """docs → 站点仓库 → 重建 data.js → 推送（CF Pages 自动部署）。"""
    secrets = load_secrets()
    if not SITE_DIR.exists():
        raise SystemExit(f"站点仓库不存在: {SITE_DIR}")
    synced = 0
    for src, dst in ((ROOT / "docs", SITE_DIR / "docs_en"),
                     (ROOT / "docs" / "zh", SITE_DIR / "docs_zh")):
        for path in src.glob("*.md"):
            target = dst / path.name
            body = path.read_text(encoding="utf-8")
            if not target.exists() or target.read_text(encoding="utf-8") != body:
                target.write_text(body, encoding="utf-8", newline="\n")
                synced += 1
    print(f"synced {synced} docs")
    run([sys.executable, "build.py"], cwd=SITE_DIR)
    if not run(["git", "status", "--porcelain"], cwd=SITE_DIR).stdout.strip():
        print("站点无改动")
        return
    run(["git", "add", "-A"], cwd=SITE_DIR)
    run(["git", "commit", "-m", f"docs: sync from PawUI {read_version()}"], cwd=SITE_DIR)
    url = secrets.get("SITE_REPO", "origin")
    token = secrets.get("GITHUB_TOKEN", "")
    if token and url.startswith("https://github.com/"):
        url = url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
    run(["git", "push", url, "main"], cwd=SITE_DIR)


USAGE = "用法: python tools/release.py [build|upload|publish|site|all] …"


def main(argv: list[str]) -> int:
    actions = argv[1:]
    if not actions:
        print(USAGE)
        return 2
    version = read_version()
    print(f"PawUI {version} · {ROOT}")
    for action in actions:
        if action == "build":
            cmd_build()
        elif action == "upload":
            cmd_upload()
        elif action == "publish":
            cmd_publish()
        elif action == "site":
            cmd_site()
        elif action == "all":
            cmd_build()
            cmd_upload()
            cmd_publish()
        else:
            raise SystemExit(f"未知动作 {action!r}（build / upload / publish / site / all）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
