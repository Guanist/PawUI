"""Tests for the PawUI animate module."""

from pawui.animate import _EASINGS, _KINDS, _SLIDE, easing, is_animation


class TestEasing:
    def test_known_easings(self):
        for name in _EASINGS:
            curve = easing(name)
            assert curve is not None

    def test_unknown_easing_defaults_to_out_cubic(self):
        from PySide6.QtCore import QEasingCurve
        curve = easing("unknown")
        assert curve == QEasingCurve.Type.OutCubic


class TestIsAnimation:
    def test_known_animations(self):
        for kind in _KINDS:
            assert is_animation(kind) is True

    def test_unknown_animation(self):
        assert is_animation("unknown") is False

    def test_empty_string(self):
        assert is_animation("") is False


class TestSlideConstants:
    def test_slide_up(self):
        dx, dy = _SLIDE["slide-up"]
        assert dx == 0
        assert dy == 22

    def test_slide_down(self):
        dx, dy = _SLIDE["slide-down"]
        assert dx == 0
        assert dy == -22

    def test_slide_left(self):
        dx, dy = _SLIDE["slide-left"]
        assert dx == 22
        assert dy == 0

    def test_slide_right(self):
        dx, dy = _SLIDE["slide-right"]
        assert dx == -22
        assert dy == 0
