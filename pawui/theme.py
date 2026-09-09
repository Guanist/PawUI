"""PyX 主题：一组可继承的默认颜色 / 字体 / 间距。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

COLOR_FIELDS = ("background", "surface", "text", "subtext", "accent", "border", "danger")


@dataclass
class Theme:
    """默认主题参数，所有组件从 theme 继承样式。"""

    background: str = "#1e1e2e"
    surface: str = "#282a36"
    text: str = "#f8f8f2"
    subtext: str = "#a6adc8"
    accent: str = "#7aa2f7"
    border: str = "#44475a"
    danger: str = "#f7768e"
    spacing: int = 8
    padding: int = 12
    radius: int = 24
    font_family: str = "Segoe UI"
    font_size: int = 12
    title_size: int = 18
    # 用户自定义的命名颜色：<Color name="brand" value="#ff5c8a"/>
    custom: dict[str, str] = field(default_factory=dict)

    @classmethod
    def light(cls) -> Theme:
        return cls(
            background="#f5f5f7",
            surface="#ffffff",
            text="#1d1d1f",
            subtext="#6e6e73",
            accent="#0071e3",
            border="#d2d2d7",
            danger="#ff375f",
        )

    @classmethod
    def dark(cls) -> Theme:
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def override(self, **kwargs: Any) -> Theme:
        return replace(self, **kwargs)

    def color(self, name: str, default: str | None = None) -> str | None:
        """按名字取色：先查内置主题色，再查自定义色。"""
        if name in COLOR_FIELDS:
            return getattr(self, name, default)
        return self.custom.get(name, default)

    def apply(self, overrides: dict[str, str]) -> Theme:
        """应用一组颜色覆盖；命中内置字段就改主题，否则进 custom。"""
        for name, value in overrides.items():
            if name in COLOR_FIELDS:
                setattr(self, name, value)
            else:
                self.custom[name] = value
        return self

    def qss(self) -> str:
        """渲染成 Qt 样式表：圆角、抗锯齿、悬停/聚焦态全都走这里。"""
        t = self
        return f"""
        QWidget {{ background-color: {t.background}; color: {t.text};
                  font-family: "Microsoft YaHei UI","Segoe UI","Segoe UI Symbol"; }}
        QLabel {{ background: transparent; }}
        QLineEdit {{
            background-color: {t.surface}; color: {t.text}; border: 1px solid {t.border};
            border-radius: 10px; padding: 7px 12px; font-size: 14px;
            selection-background-color: {t.accent}; selection-color: {t.background};
        }}
        QLineEdit:focus {{ border: 2px solid {t.accent}; }}
        QCheckBox {{ color: {t.text}; spacing: 8px; font-size: 14px; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
            border: 1px solid {t.border}; background: {t.surface}; }}
        QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent}; }}
        QFrame#divider {{ background-color: {t.border}; }}
        """


THEMES = {
    "dark": Theme.dark,
    "light": Theme.light,
}


def _blend(c1: str, c2: str, t: float) -> str:
    a = _parse(c1)
    b = _parse(c2)
    out = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"#{out[0]:02x}{out[1]:02x}{out[2]:02x}"


def _parse(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
