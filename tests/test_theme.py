"""Tests for the PawUI theme module."""

from pawui.theme import THEMES, Theme, _blend, _parse


class TestTheme:
    def test_dark_theme_defaults(self):
        theme = Theme.dark()
        assert theme.background == "#1e1e2e"
        assert theme.surface == "#282a36"
        assert theme.text == "#f8f8f2"
        assert theme.accent == "#7aa2f7"

    def test_light_theme_defaults(self):
        theme = Theme.light()
        assert theme.background == "#f5f5f7"
        assert theme.text == "#1d1d1f"
        assert theme.accent == "#0071e3"

    def test_override(self):
        theme = Theme.dark()
        new_theme = theme.override(background="#000000", accent="#ff0000")
        assert new_theme.background == "#000000"
        assert new_theme.accent == "#ff0000"
        assert new_theme.text == theme.text

    def test_color_lookup_builtin(self):
        theme = Theme.dark()
        assert theme.color("background") == "#1e1e2e"
        assert theme.color("accent") == "#7aa2f7"

    def test_color_lookup_custom(self):
        theme = Theme.dark()
        theme.custom["brand"] = "#ff00ff"
        assert theme.color("brand") == "#ff00ff"

    def test_color_lookup_missing(self):
        theme = Theme.dark()
        assert theme.color("nonexistent") is None
        assert theme.color("nonexistent", "default") == "default"

    def test_apply_overrides_builtin(self):
        theme = Theme.dark()
        theme.apply({"background": "#000000", "accent": "#ff0000"})
        assert theme.background == "#000000"
        assert theme.accent == "#ff0000"

    def test_apply_overrides_custom(self):
        theme = Theme.dark()
        theme.apply({"brand": "#00ff00"})
        assert theme.custom["brand"] == "#00ff00"

    def test_qss_generation(self):
        theme = Theme.dark()
        qss = theme.qss()
        assert "background-color" in qss
        assert theme.background in qss
        assert theme.text in qss

    def test_to_dict(self):
        theme = Theme.dark()
        d = theme.to_dict()
        assert isinstance(d, dict)
        assert d["background"] == "#1e1e2e"

    def test_themes_registry(self):
        assert "dark" in THEMES
        assert "light" in THEMES
        # THEMES stores classmethods, not instances
        assert callable(THEMES["dark"])
        assert callable(THEMES["light"])
        # Calling them produces Theme instances
        assert isinstance(THEMES["dark"](), Theme)
        assert isinstance(THEMES["light"](), Theme)


class TestColorBlend:
    def test_blend_50_percent(self):
        result = _blend("#000000", "#ffffff", 0.5)
        # int() truncates, so 127.5 -> 127 (0x7f)
        assert result == "#7f7f7f"

    def test_blend_0_percent(self):
        result = _blend("#ff0000", "#00ff00", 0.0)
        assert result == "#ff0000"

    def test_blend_100_percent(self):
        result = _blend("#ff0000", "#00ff00", 1.0)
        assert result == "#00ff00"

    def test_blend_short_hex(self):
        result = _blend("#f00", "#0f0", 0.5)
        # int() truncates, so 127.5 -> 127 (0x7f)
        assert result == "#7f7f00"


class TestParseColor:
    def test_parse_full_hex(self):
        r, g, b = _parse("#ff00aa")
        assert (r, g, b) == (255, 0, 170)

    def test_parse_short_hex(self):
        r, g, b = _parse("#f0a")
        assert (r, g, b) == (255, 0, 170)

    def test_parse_without_hash(self):
        r, g, b = _parse("ff00aa")
        assert (r, g, b) == (255, 0, 170)
