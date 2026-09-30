"""``pawui help`` 的文档来源: **线上优先，本地兜底**。

文档正文的单一事实源在仓库的 ``docs/``，发布时同步到站点仓库并编译成
``static/data.js``（站点渲染用的同一份）。这里直接拉那份 data.js：

- 线上拿得到 -> 用线上的，顺便写进用户缓存目录，下次离线也能看；
- 线上拿不到（离线 / 内网 / 还没发布）-> 静默回落到随包 ``docs/``；
- 缓存过期才重拉，默认 6 小时。

好处很直白：改文档不用发新版 ``pawui``，装的旧版本也能读到最新文档。

环境变量：

- ``PAWUI_DOCS_OFFLINE=1`` 完全不走网络，只用缓存 / 随包文档；
- ``PAWUI_DOCS_LANG=zh|en`` 强制语言，不设时按系统语言猜。
"""

from __future__ import annotations

import base64
import json
import locale
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

#: 站点上那份 data.js —— 站点和命令行读的是同一个字符串
FEED_URL = "https://pawui.pages.dev/static/data.js"
#: 超时给短一点：拿不到就回落本地，别让 `pawui help` 卡住
TIMEOUT = 2.5
#: 缓存多久算新鲜（秒）
CACHE_TTL = 6 * 3600


def cache_file() -> Path:
    """缓存位置：Windows 用 LOCALAPPDATA，其余走 XDG_CACHE_HOME。"""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "pawui" / "docs.json"


def parse_data_js(text: str) -> dict[str, Any] | None:
    """把 ``window.PAWUI_DOCS = {...};`` 解析成 dict。"""
    if not text:
        return None
    body = text.strip()
    index = body.find("{")
    if index < 0:
        return None
    body = body[index:].rstrip()
    if body.endswith(";"):
        body = body[:-1]
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict) or "docs" not in payload:
        return None
    return payload


def offline() -> bool:
    value = os.environ.get("PAWUI_DOCS_OFFLINE", "")
    return value.strip().lower() in ("1", "true", "yes", "on")


def language() -> str:
    """文档语言：环境变量 > 系统语言 > en。"""
    forced = os.environ.get("PAWUI_DOCS_LANG", "").strip().lower()
    if forced in ("zh", "en"):
        return forced
    try:
        name = locale.getlocale()[0] or ""
    except (TypeError, ValueError):
        name = ""
    name = name or os.environ.get("LANG", "")
    return "zh" if "zh" in name.lower() or "chinese" in name.lower() else "en"


def load_cache() -> dict[str, Any] | None:
    try:
        payload = json.loads(cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) and "docs" in payload else None


def cache_age() -> float | None:
    try:
        return time.time() - cache_file().stat().st_mtime
    except OSError:
        return None


def save_cache(payload: dict[str, Any]) -> None:
    path = cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 缓存写不进去不影响使用


def fetch(url: str = FEED_URL, timeout: float = TIMEOUT) -> dict[str, Any] | None:
    """拉线上文档；失败返回 None（由调用方回落）。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": "pawui-help", "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return parse_data_js(raw)


def get_feed(refresh: bool = False, use_network: bool = True) -> tuple[dict[str, Any] | None, str]:
    """返回 ``(feed, 来源)``，来源取值 ``online`` / ``cache`` / ``local``。"""
    cached = load_cache()
    age = cache_age()
    if cached is not None and age is not None and age < CACHE_TTL and not refresh:
        return cached, "cache"
    if use_network and not offline():
        payload = fetch()
        if payload is not None:
            save_cache(payload)
            return payload, "online"
    if cached is not None:
        return cached, "cache"
    return None, "local"


def topic_list(feed: dict[str, Any] | None) -> list[tuple[str, str]]:
    """``[(topic_id, title), …]``，按站点侧边栏顺序；没有 feed 就是空表。"""
    if not feed:
        return []
    lang = language()
    out: list[tuple[str, str]] = []
    for topic in feed.get("order", []):
        entry = feed.get("docs", {}).get(topic, {})
        meta = entry.get(lang) or entry.get("en") or {}
        out.append((str(topic), str(meta.get("title") or topic)))
    return out


def topic_body(feed: dict[str, Any] | None, topic: str) -> str | None:
    """取出某篇文档的 markdown 正文（base64 解出来）。"""
    if not feed:
        return None
    entry = feed.get("docs", {}).get(topic)
    if not isinstance(entry, dict):
        return None
    meta = entry.get(language()) or entry.get("en") or {}
    encoded = meta.get("body")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
