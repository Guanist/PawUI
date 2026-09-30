"""`pawui help` 的文档来源：线上优先、缓存兜底、随包离线回落。"""

import base64
import json

import pytest

from pawui import cli, docsfeed


def _payload(zh: str = "中文正文", en: str = "english body") -> dict:
    return {
        "order": ["index", "theming"],
        "groups": [{"id": "start", "zh": "开始", "en": "Start", "docs": ["index", "theming"]}],
        "docs": {
            "index": {
                "zh": {"title": "简介", "body": base64.b64encode(zh.encode()).decode()},
                "en": {"title": "Intro", "body": base64.b64encode(en.encode()).decode()},
            },
            "theming": {
                "zh": {"title": "主题", "body": base64.b64encode(b"# theme").decode()},
                "en": {"title": "Theming", "body": base64.b64encode(b"# theme en").decode()},
            },
        },
    }


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """缓存写进临时目录，别动用户真实的 %LOCALAPPDATA%\\pawui\\docs.json。"""
    monkeypatch.setattr(docsfeed, "cache_file", lambda: tmp_path / "docs.json")
    monkeypatch.delenv("PAWUI_DOCS_OFFLINE", raising=False)
    # 语言必须钉死：CI 机器是英文 locale，跟着系统语言走会让断言随环境变
    monkeypatch.setenv("PAWUI_DOCS_LANG", "zh")


class TestParse:
    def test_parses_window_assignment(self):
        text = "window.PAWUI_DOCS = " + json.dumps(_payload()) + ";\n"
        parsed = docsfeed.parse_data_js(text)
        assert parsed is not None and "docs" in parsed

    def test_rejects_garbage(self):
        assert docsfeed.parse_data_js("") is None
        assert docsfeed.parse_data_js("not js at all") is None
        assert docsfeed.parse_data_js("window.PAWUI_DOCS = [1,2];") is None


class TestCache:
    def test_offline_without_cache_returns_local(self):
        feed, source = docsfeed.get_feed(use_network=False)
        assert feed is None and source == "local"

    def test_network_result_is_cached(self, monkeypatch, tmp_path):
        monkeypatch.setattr(docsfeed, "fetch", lambda *a, **k: _payload())
        feed, source = docsfeed.get_feed()
        assert source == "online" and feed is not None
        assert (tmp_path / "docs.json").exists()
        # 第二次不用网络也拿得到
        monkeypatch.setattr(docsfeed, "fetch", lambda *a, **k: None)
        feed2, source2 = docsfeed.get_feed()
        assert source2 == "cache" and feed2 == feed

    def test_offline_env_blocks_network(self, monkeypatch):
        called = []

        def boom(*args, **kwargs):
            called.append(1)
            return _payload()

        monkeypatch.setenv("PAWUI_DOCS_OFFLINE", "1")
        monkeypatch.setattr(docsfeed, "fetch", boom)
        feed, source = docsfeed.get_feed()
        assert called == [] and feed is None and source == "local"

    def test_stale_cache_is_refreshed(self, monkeypatch):
        monkeypatch.setattr(docsfeed, "fetch", lambda *a, **k: _payload(zh="v1"))
        docsfeed.get_feed()
        monkeypatch.setattr(docsfeed, "cache_age", lambda: docsfeed.CACHE_TTL + 10)
        monkeypatch.setattr(docsfeed, "fetch", lambda *a, **k: _payload(zh="v2"))
        feed, source = docsfeed.get_feed()
        assert source == "online"
        assert docsfeed.topic_body(feed, "index") == "v2"

    def test_broken_cache_file_is_ignored(self, monkeypatch, tmp_path):
        (tmp_path / "docs.json").write_text("{ not json", encoding="utf-8")
        assert docsfeed.load_cache() is None


class TestTopics:
    def test_language_selection(self, monkeypatch):
        monkeypatch.setenv("PAWUI_DOCS_LANG", "zh")
        assert docsfeed.language() == "zh"
        assert docsfeed.topic_body(_payload(), "index") == "中文正文"
        monkeypatch.setenv("PAWUI_DOCS_LANG", "en")
        assert docsfeed.topic_body(_payload(), "index") == "english body"

    def test_title_list_follows_order(self):
        assert docsfeed.topic_list(_payload()) == [("index", "简介"), ("theming", "主题")]
        assert docsfeed.topic_list(None) == []

    def test_unknown_topic_returns_none(self):
        assert docsfeed.topic_body(_payload(), "nope") is None


class TestHelpCommand:
    def test_lists_topics_from_feed(self, monkeypatch, capsys):
        monkeypatch.setattr(docsfeed, "get_feed", lambda **k: (_payload(), "online"))
        assert cli.help_cmd() == 0
        out = capsys.readouterr().out
        assert "pawui help index" in out and "简介" in out
        assert "线上文档" in out

    def test_prints_topic_body(self, monkeypatch, capsys):
        monkeypatch.setattr(docsfeed, "get_feed", lambda **k: (_payload(), "online"))
        assert cli.help_cmd("index") == 0
        out = capsys.readouterr().out
        assert "中文正文" in out or "english body" in out
        assert "来源" in out

    def test_falls_back_to_packaged_doc(self, monkeypatch, capsys):
        monkeypatch.setattr(docsfeed, "get_feed", lambda **k: (None, "local"))
        assert cli.help_cmd("theming") == 0
        out = capsys.readouterr().out
        assert "随包文档" in out
        assert "Theme" in out or "主题" in out

    def test_offline_lists_packaged_topics(self, monkeypatch, capsys):
        monkeypatch.setattr(docsfeed, "get_feed", lambda **k: (None, "local"))
        assert cli.help_cmd() == 0
        out = capsys.readouterr().out
        assert "pawui help theming" in out

    def test_unknown_topic_exits_1(self, monkeypatch, capsys):
        monkeypatch.setattr(docsfeed, "get_feed", lambda **k: (_payload(), "online"))
        assert cli.help_cmd("definitely-not-a-topic") == 1
        assert "no doc topic" in capsys.readouterr().err

    def test_main_accepts_refresh_flag(self, monkeypatch, capsys):
        seen = {}

        def fake(topic=None, refresh=False, use_network=True):
            seen["refresh"] = refresh
            seen["use_network"] = use_network
            return 0

        monkeypatch.setattr(cli, "help_cmd", fake)
        assert cli.main(["help", "theming", "--refresh"]) == 0
        assert seen == {"refresh": True, "use_network": True}
        assert cli.main(["help", "--offline"]) == 0
        assert seen == {"refresh": False, "use_network": False}
