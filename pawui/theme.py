"""PawUI 主题：一组可继承的默认颜色 / 字体 / 间距。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

COLOR_FIELDS = ("background", "surface", "text", "subtext", "accent", "border", "danger")


@dataclass
class Theme:
    """默认主题参数，所有组件从 theme 继承样式。

    默认值是**浅色 + 蓝色主色**（``Theme.light()``，等价于 ``Theme()``）；
    暗色在 ``Theme.dark()`` 里显式给出。
    """

    background: str = "#f5f5f7"
    surface: str = "#ffffff"
    text: str = "#1d1d1f"
    subtext: str = "#6e6e73"
    accent: str = "#0071e3"
    border: str = "#d2d2d7"
    danger: str = "#ff375f"
    spacing: int = 8
    padding: int = 12
    radius: int = 24
    font_family: str = "Microsoft YaHei UI"
    font_size: int = 12
    title_size: int = 18
    # 用户自定义的命名颜色：<Color name="brand" value="#ff5c8a"/>
    custom: dict[str, str] = field(default_factory=dict)

    @classmethod
    def light(cls) -> Theme:
        return cls()

    @classmethod
    def dark(cls) -> Theme:
        return cls(
            background="#1e1e2e",
            surface="#282a36",
            text="#f8f8f2",
            subtext="#a6adc8",
            accent="#7aa2f7",
            border="#44475a",
            danger="#f7768e",
        )

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
        """渲染成 Qt 样式表：圆角、抗锯齿、悬停/聚焦态全都走这里。

        字体族与字号取自主题字段，不再写死 —— 以前 ``font_family`` /
        ``font_size`` 是死字段，用户改不动字体。
        """
        t = self
        return f"""
        QWidget {{ background-color: {t.background}; color: {t.text};
                  font-family: "{t.font_family}","Segoe UI","Segoe UI Symbol";
                  font-size: {t.font_size}px; }}
        QLabel {{ background: transparent; }}
        QLineEdit {{
            background-color: {t.surface}; color: {t.text}; border: 1px solid {t.border};
            border-radius: 10px; padding: 7px 12px;
            selection-background-color: {t.accent}; selection-color: {t.background};
        }}
        QLineEdit:focus {{ border: 2px solid {t.accent}; }}
        QCheckBox {{ color: {t.text}; spacing: 8px; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
            border: 1px solid {t.border}; background: {t.surface}; }}
        QCheckBox::indicator:checked {{ background: {t.accent}; border-color: {t.accent}; }}
        QFrame#divider {{ background-color: {t.border}; }}

        /* 细节控件以前完全没有规则，吃系统默认外观，切主题不会变色 */

        /* 滚动条：纵向/横向必须分开写。合在一起时 min-height/min-width
           会互相串——纵向手柄被撑到 28px 宽，塞进 10px 的槽里就成了怪东西。 */
        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 3px;
            min-height: 32px; margin: 3px; }}
        QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 3px;
            min-width: 32px; margin: 3px; }}
        QScrollBar::handle:vertical:hover {{ background: {t.subtext}; }}
        QScrollBar::handle:horizontal:hover {{ background: {t.subtext}; }}
        QScrollBar::handle:vertical:pressed {{ background: {t.accent}; }}
        QScrollBar::handle:horizontal:pressed {{ background: {t.accent}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0; background: none; border: none; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0; background: none; border: none; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none; }}
        QScrollBar::up-arrow, QScrollBar::down-arrow,
        QScrollBar::left-arrow, QScrollBar::right-arrow {{ width: 0; height: 0; }}

        /* 弹出层窗口（QMenu / 下拉框）没有圆角裁剪，硬写 border-radius 只会在
           方角外面露出一圈底色，所以这里只用 1px 边框，靠留白和选中色取胜。 */
        QMenu {{ background-color: {t.surface}; color: {t.text};
            border: 1px solid {t.border}; padding: 6px; }}
        QMenu::item {{ padding: 6px 20px; border-radius: 5px; }}
        QMenu::item:selected {{ background-color: {t.accent}; color: {t.background}; }}
        QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}

        QToolTip {{ background-color: {t.surface}; color: {t.text};
            border: 1px solid {t.border}; padding: 6px 10px; }}

        QComboBox {{ background-color: {t.surface}; color: {t.text};
            border: 1px solid {t.border}; border-radius: 10px;
            padding: 6px 26px 6px 12px; min-height: 22px; }}
        QComboBox:hover {{ border-color: {t.accent}; }}
        /* 只换颜色不改宽度：改宽度会让圆角重新计算，右边缘出现接缝 */
        QComboBox:focus {{ border-color: {t.accent}; }}
        /* 系统默认箭头又小又歪，这里关掉，由 _ThemedComboBox 自绘 chevron */
        QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
        QComboBox::drop-down {{ border: none; background: transparent; }}
        QComboBox QAbstractItemView {{ background-color: {t.surface}; color: {t.text};
            border: none; padding: 4px; outline: none;
            selection-background-color: {t.accent}; selection-color: {t.background}; }}
        QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 4px 10px;
            border-radius: 5px; }}
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
