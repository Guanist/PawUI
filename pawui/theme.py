"""PawUI 主题：一组可继承的默认颜色 / 字体 / 间距。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

COLOR_FIELDS = ("background", "surface", "text", "subtext", "accent", "border", "danger",
                "success", "warning", "info")


@dataclass
class Theme:
    """默认主题参数，所有组件从 theme 继承样式。

    默认值是**浅色 + 蓝色主色**（``Theme.light()``，等价于 ``Theme()``）；
    暗色在 ``Theme.dark()`` 里显式给出。
    """

    # -- 基础色 --
    background: str = "#f5f5f7"
    surface: str = "#ffffff"
    text: str = "#1d1d1f"
    subtext: str = "#6e6e73"
    accent: str = "#0071e3"
    border: str = "#d2d2d7"
    danger: str = "#ff375f"
    success: str = "#22c55e"
    warning: str = "#f59e0b"
    #: 信息色默认跟随主色；想让它独立就显式覆盖
    info: str = ""

    # -- 层次：surface 的几个变体，用来在不靠阴影的情况下也能分层 --
    #: 比 surface 更靠前一层（卡片、浮层）
    surface_raised: str = ""
    #: 比 surface 更沉一层（输入框凹陷、代码块）
    surface_sunken: str = ""
    #: 悬停 / 按下时的底色，留空则按 surface 自动算
    surface_hover: str = ""
    surface_active: str = ""

    # -- 间距刻度（8pt 网格 + 4px 半步）--
    spacing: int = 8
    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16
    space_xl: int = 24

    # -- 圆角分级：小控件小圆角，容器才用大圆角 --
    #: 兼容旧字段：没显式给组件 radius 时的兜底
    radius: int = 24
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 16

    padding: int = 12
    font_family: str = "Microsoft YaHei UI"
    font_size: int = 12

    # -- 字号分级 --
    font_xs: int = 11
    font_sm: int = 12
    font_md: int = 13
    font_lg: int = 15
    font_xl: int = 20
    title_size: int = 18

    # -- 字重 --
    weight_normal: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600

    # -- 层次/立体感 --
    #: 容器默认是否画投影（自绘 QGraphicsDropShadowEffect）
    shadow: bool = False
    shadow_blur: int = 28
    shadow_offset_y: int = 6
    #: 投影颜色（带 alpha 的 #rrggbbaa）
    shadow_color: str = "#00000033"

    #: 「贴在 accent 底色上的文字色」。默认按 accent 的明暗自动选黑白，
    #: 显式给值则用它（比如主色是亮黄时想配深字）。
    on_accent: str = ""

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
            success="#34d399",
            warning="#fbbf24",
            # 暗色下「浮起」要更亮、不是更暗
            surface_raised="#2f3142",
            surface_sunken="#20222e",
            surface_hover="#323545",
            surface_active="#3a3d4f",
            shadow_color="#00000066",
        )

    # ---- 派生色：留空时按 background/surface 自动算，写死时用写死的 ----

    #: 浅色主题往「白」走，暗色主题往「亮」走 —— 同一个方向词在两套主题里
    #: 是相反的绝对颜色，所以先判断底色明暗，再决定混哪个端点。
    @property
    def is_dark(self) -> bool:
        r, g, b = _parse(self.background)
        # 相对亮度，够用了（不需要真正的 WCAG）
        return (0.299 * r + 0.587 * g + 0.114 * b) < 128

    @property
    def _up(self) -> str:
        """「更靠前」的方向：浅色 -> 白，暗色 -> 白（暗色里变亮也是往白）。"""
        return "#ffffff"

    @property
    def _down(self) -> str:
        """「更靠后」的方向：浅色 -> 黑，暗色 -> 黑。"""
        return "#000000"

    def _auto(self, value: str, base: str, target: str, amount: float) -> str:
        """value 为空就用 base 往 target 混 amount，否则原样返回。"""
        if value:
            return value
        return _blend(base, target, amount)

    @property
    def raised(self) -> str:
        """比 surface 更靠前一层（卡片、浮层）：浅色更白，暗色更亮。"""
        if self.surface_raised:
            return self.surface_raised
        return _blend(self.surface, self._up, 0.55 if not self.is_dark else 0.06)

    @property
    def sunken(self) -> str:
        """比 surface 更沉一层（输入框凹陷、代码块底）：浅色更灰，暗色更暗。"""
        if self.surface_sunken:
            return self.surface_sunken
        return _blend(self.surface, self._down, 0.04 if not self.is_dark else 0.22)

    @property
    def hover(self) -> str:
        """悬停底色。"""
        if self.surface_hover:
            return self.surface_hover
        return _blend(self.surface, self._down if not self.is_dark else self._up, 0.06)

    @property
    def active(self) -> str:
        """按下底色：比 hover 再重一点。"""
        if self.surface_active:
            return self.surface_active
        return _blend(self.surface, self._down if not self.is_dark else self._up, 0.12)

    @property
    def on_accent_color(self) -> str:
        """accent 底色上的文字色：默认按对比度自动选黑/白。"""
        if self.on_accent:
            return self.on_accent
        r, g, b = _parse(self.accent)
        # 相对亮度高 -> 用深字，否则用白字
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#1d1d1f" if lum > 0.6 else "#ffffff"

    @property
    def subtle_border(self) -> str:
        """更轻的分隔线。"""
        return _blend(self.border, self.surface, 0.5)

    @property
    def info_color(self) -> str:
        """info 状态色，默认跟随主色。"""
        return self.info or self.accent

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
        """渲染成 Qt 样式表。

        这里只放**所有控件共有**的默认外观：底色、字体、滚动条、弹出层。
        具体组件自己的形状（按钮、输入框、卡片……）由组件内联样式表决定 ——
        控件 ``setStyleSheet`` 会压过 app 样式表，写在这儿反而会和组件打架。

        用法：``app.setStyleSheet(theme.qss())``。
        """
        t = self

        # 统一的「悬停/按下」底色，给各处复用
        hover = t.hover
        active = t.active

        return f"""
        /* ── 基础 ─────────────────────────────────────────────────────── */
        QWidget {{
            background-color: {t.background};
            color: {t.text};
            font-family: "{t.font_family}","Segoe UI","Segoe UI Symbol";
            font-size: {t.font_size}px;
        }}
        QLabel {{ background: transparent; }}
        QMainWindow, QDialog {{ background-color: {t.background}; }}
        QMainWindow::separator {{ background: {t.subtle_border}; width: 1px; height: 1px; }}

        /* 焦点提示统一走各控件的 :focus 规则（QSS 不支持通配 *:focus） */

        /* ── 文本输入 ─────────────────────────────────────────────────── */
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background-color: {t.sunken};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: {t.radius_sm}px;
            padding: 7px 12px;
            selection-background-color: {t.accent};
            selection-color: {t.on_accent_color};
        }}
        QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{
            border-color: {t.subtext};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
            border: 2px solid {t.accent};
            background-color: {t.surface};
        }}

        /* ── 复选框（未自绘的那条路：原生 QCheckBox）─────────────────── */
        QCheckBox {{ color: {t.text}; spacing: 8px; background: transparent; }}
        QCheckBox::indicator {{
            width: 18px; height: 18px;
            border-radius: {t.radius_sm - 1}px;
            border: 1px solid {t.border};
            background: {t.surface};
        }}
        QCheckBox::indicator:hover {{ border-color: {t.accent}; }}
        QCheckBox::indicator:checked {{
            background: {t.accent}; border-color: {t.accent};
        }}
        QRadioButton {{ color: {t.text}; spacing: 8px; background: transparent; }}
        QRadioButton::indicator {{
            width: 18px; height: 18px; border-radius: 9px;
            border: 1px solid {t.border}; background: {t.surface};
        }}
        QRadioButton::indicator:checked {{
            background: {t.accent}; border-color: {t.accent};
        }}

        /* ── 分隔线 ───────────────────────────────────────────────────── */
        QFrame#divider {{ background-color: {t.subtle_border}; }}

        /* ── 滚动条 ───────────────────────────────────────────────────── */
        /* 纵向/横向必须分开写：合在一起时 min-height/min-width 会互相串，
           纵向手柄被撑到 28px 宽，塞进 10px 的槽里就成了怪东西。 */
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
        QScrollBar::handle:vertical {{
            background: {t.border}; border-radius: 3px; min-height: 32px; margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t.border}; border-radius: 3px; min-width: 32px; margin: 2px;
        }}
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

        /* ── 弹出层 ───────────────────────────────────────────────────── */
        /* 弹出层窗口没有圆角裁剪，硬写 border-radius 只会在方角外面露出一圈
           底色，所以只用 1px 边框，靠留白和选中色取胜。 */
        QMenu {{
            background-color: {t.raised}; color: {t.text};
            border: 1px solid {t.border}; padding: 6px;
        }}
        QMenu::item {{ padding: 7px 22px; border-radius: {t.radius_sm}px; }}
        QMenu::item:selected {{ background-color: {t.accent}; color: {t.on_accent_color}; }}
        QMenu::item:disabled {{ color: {t.subtext}; }}
        QMenu::separator {{ height: 1px; background: {t.subtle_border}; margin: 5px 8px; }}

        QMenuBar {{ background: {t.background}; color: {t.text}; padding: 2px 4px; }}
        QMenuBar::item {{ padding: 5px 12px; border-radius: {t.radius_sm}px; background: transparent; }}
        QMenuBar::item:selected {{ background: {hover}; }}
        QMenuBar::item:pressed {{ background: {active}; }}

        QToolTip {{
            background-color: {t.raised}; color: {t.text};
            border: 1px solid {t.border}; padding: 6px 10px;
            border-radius: {t.radius_sm}px;
        }}

        /* ── 下拉框 ───────────────────────────────────────────────────── */
        QComboBox {{
            background-color: {t.surface}; color: {t.text};
            border: 1px solid {t.border}; border-radius: {t.radius_sm}px;
            padding: 6px 26px 6px 12px; min-height: 22px;
        }}
        /* 只换颜色不改宽度：改宽度会让圆角重新计算，右边缘出现接缝 */
        QComboBox:hover {{ border-color: {t.subtext}; }}
        QComboBox:focus {{ border-color: {t.accent}; }}
        QComboBox::down-arrow {{ width: 0; height: 0; border: none; }}
        QComboBox::drop-down {{ border: none; background: transparent; }}
        QComboBox QAbstractItemView {{
            background-color: {t.raised}; color: {t.text};
            border: none; padding: 4px; outline: none;
            selection-background-color: {t.accent}; selection-color: {t.on_accent_color};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 26px; padding: 4px 10px; border-radius: {t.radius_sm}px;
        }}

        /* ── 数据视图（表格/列表/树共有的部分）───────────────────────── */
        QHeaderView::section {{
            background-color: {t.background}; color: {t.subtext};
            padding: 6px 8px; border: none;
            border-bottom: 1px solid {t.border};
        }}
        QTableView, QTreeView, QListView {{
            background-color: {t.surface}; color: {t.text};
            border: 1px solid {t.border};
            border-radius: {t.radius_md}px;
            outline: none;
            selection-background-color: {t.accent};
            selection-color: {t.on_accent_color};
        }}
        QTableView::item:hover, QTreeView::item:hover, QListView::item:hover {{
            background-color: {hover};
        }}

        /* ── 滑块 / 进度条（原生形态的兜底）────────────────────────────── */
        QSlider::groove:horizontal {{
            height: 4px; background: {t.border}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 16px; margin: -6px 0;
            background: {t.accent}; border-radius: 8px;
        }}
        QProgressBar {{
            background: {t.border}; border: none;
            border-radius: 4px; text-align: center; color: {t.text};
        }}
        QProgressBar::chunk {{ background: {t.accent}; border-radius: 4px; }}

        /* ── 分组框 / 工具箱 ─────────────────────────────────────────── */
        QGroupBox {{
            border: 1px solid {t.border};
            border-radius: {t.radius_md}px;
            margin-top: 10px; padding-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            left: 12px; padding: 0 4px; color: {t.subtext};
        }}

        /* ── 标签页 ───────────────────────────────────────────────────── */
        QTabBar::tab {{
            background: transparent; color: {t.subtext};
            padding: 7px 16px; border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:hover {{ color: {t.text}; }}
        QTabBar::tab:selected {{
            color: {t.text}; border-bottom: 2px solid {t.accent}; font-weight: {t.weight_semibold};
        }}

        /* ── 日历（QCalendarWidget 的弹出部分）───────────────────────── */
        QCalendarWidget QWidget {{ alternate-background-color: {t.sunken}; }}
        QCalendarWidget QAbstractItemView:enabled {{
            background: {t.surface}; color: {t.text};
            selection-background-color: {t.accent}; selection-color: {t.on_accent_color};
        }}
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
