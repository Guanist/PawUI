"""三个回归：check 注册表 / Dialog 容器字段 / Text 的 CSS 可用性。

对应 0.1.3.2 修掉的三个问题，都是「本地看着没事、一到真实用法就翻车」的类型，
所以每条都直接钉住触发路径：

1. ``cli.BUILTINS`` 只从 ``components`` 导入 22 个基础组件，``pawui check``
   会把 runtime 明明支持的另外 22 个判成 unknown。
2. ``Dialog`` 自己搭布局、没走 ``Container.build()``，缺 ``_justify`` /
   ``_cross_align``；``Tabs`` 会对子元素调 ``add_child()``，于是
   「Tabs 里放 Dialog」直接 AttributeError。
3. ``Text`` 的内联样式表是裸声明（没有选择器前缀），而用户的 ``<Style>`` 规则
   是按控件**内联追加**的 —— Qt 只要看到 ``{`` 就整段按「选择器 { 声明 }」解析，
   前面的裸声明被当成选择器，整张表解析失败，Text 上的 class / id 样式全部失效。
"""

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from pawui import cli
from pawui.runtime import Runtime
from pawui.widgets import BUILTINS as RUNTIME_BUILTINS


def _render(source: str) -> Runtime:
    runtime = Runtime(source, filename="<test>")
    runtime._prepare()
    runtime._build_tree()
    QApplication.instance().processEvents()
    return runtime


# --------------------------------------------------------------------------
# 1) check 必须和 runtime 用同一份注册表
# --------------------------------------------------------------------------


class TestCheckRegistry:
    def test_cli_uses_full_registry(self):
        """cli 的注册表就是 runtime 的那一份，不能是 components 的基础子集。"""
        assert cli.BUILTINS is RUNTIME_BUILTINS

    def test_cli_registry_covers_every_builtin(self):
        assert set(RUNTIME_BUILTINS) <= set(cli.BUILTINS)

    def test_new_components_are_not_reported_unknown(self):
        """这 22 个曾经被 check 全部误报成 unknown component。"""
        new_tags = [
            "Accordion", "Avatar", "Badge", "Canvas", "CodeBlock", "DatePicker",
            "FilePicker", "Link", "List", "Markdown", "NumberInput", "Panel",
            "Radio", "RadioGroup", "Segmented", "Shortcut", "Skeleton", "Spinner",
            "SplitPane", "Table", "TimePicker", "VirtualList",
        ]
        missing = [t for t in new_tags if t not in cli.BUILTINS]
        assert missing == [], f"check 仍会误报这些组件: {missing}"

    def test_check_passes_on_new_component_markup(self, tmp_path):
        from pawui.cli import check

        paw = tmp_path / "new.paw"
        paw.write_text(
            '<Window title="t" width="320" height="240">\n'
            '  <Column>\n'
            '    <Badge text="x"/><Avatar initials="AB"/><Spinner size="16"/>\n'
            '    <Skeleton width="60" height="8"/><Segmented items="[a, b]"/>\n'
            '    <NumberInput min="0" max="9"/><DatePicker value="2026-09-30"/>\n'
            '  </Column>\n'
            "</Window>\n",
            encoding="utf-8",
        )
        assert check(str(paw)) == 0


# --------------------------------------------------------------------------
# 2) 容器子类不该因漏初始化 _justify 而崩
# --------------------------------------------------------------------------


class TestContainerFields:
    def test_tabs_with_dialog_does_not_crash(self):
        """Tabs 会对子元素调 add_child()，Dialog 曾经在这里 AttributeError。"""
        _render(
            '<Window title="t" width="320" height="240">\n'
            "  <Tabs>\n"
            '    <Tab label="A"><Dialog title="D"><Text>hi</Text></Dialog></Tab>\n'
            "  </Tabs>\n"
            "</Window>\n"
        )

    def test_tabs_with_every_container_subclass(self):
        bodies = {
            "Column": '<Column padding="8"><Text>x</Text></Column>',
            "Row": '<Row spacing="8"><Text>x</Text></Row>',
            "Scroll": "<Scroll><Text>x</Text></Scroll>",
            "Grid": '<Grid columns="2"><Text>x</Text></Grid>',
            "Form": '<Form><Input placeholder="p"/></Form>',
            "Dialog": '<Dialog title="D"><Text>x</Text></Dialog>',
            "Accordion": '<Accordion><Panel title="P"><Text>x</Text></Panel></Accordion>',
            "RadioGroup": '<RadioGroup value="a"><Radio value="a">A</Radio></RadioGroup>',
        }
        for tag, body in bodies.items():
            _render(
                '<Window title="t" width="360" height="280">\n'
                f'  <Tabs><Tab label="{tag}">{body}</Tab></Tabs>\n'
                "</Window>\n"
            )

    def test_dialog_honours_justify(self):
        """Dialog 需要自己读 justify，否则基类默认值会把属性吞掉。"""
        runtime = _render(
            '<Window title="t" width="320" height="240">\n'
            '  <Dialog title="D" justify="space-between"><Text>a</Text><Text>b</Text></Dialog>\n'
            "</Window>\n"
        )
        dialog = next(c for c in runtime._built_components if type(c).__name__ == "Dialog")
        assert dialog._justify == "space-between"

    def test_component_default_fields(self):
        from pawui.components import Component

        runtime = _render('<Window title="t" width="200" height="120"><Text>x</Text></Window>')
        text = next(c for c in runtime._built_components if type(c).__name__ == "Text")
        assert isinstance(text, Component)
        assert text._justify == "start"
        assert text._cross_align == "start"


# --------------------------------------------------------------------------
# 3) Text 上的用户 CSS 必须真的生效（且 Qt 不报解析失败）
# --------------------------------------------------------------------------


def _capture_qt_warnings(fn) -> list[str]:
    messages: list[str] = []
    previous = qInstallMessageHandler(lambda mode, ctx, msg: messages.append(msg))
    try:
        fn()
    finally:
        qInstallMessageHandler(previous)
    return messages


class TestTextUserCss:
    def test_text_base_qss_is_not_bare_declarations(self):
        """裸声明一旦和用户规则拼接，Qt 会把整段当选择器 —— 必须包选择器前缀。"""
        runtime = _render('<Window title="t" width="240" height="120"><Text>x</Text></Window>')
        text = next(c for c in runtime._built_components if type(c).__name__ == "Text")
        sheet = text.widget.styleSheet()
        assert sheet.startswith("QLabel {"), sheet
        assert sheet.rstrip().endswith("}"), sheet

    def test_text_class_rule_does_not_break_qt_stylesheet(self):
        def run():
            _render(
                '<Window title="t" width="320" height="200">\n'
                "  <Style>.hl { color: #ff0000; }</Style>\n"
                '  <Column><Text class="hl">x</Text></Column>\n'
                "</Window>\n"
            )

        warnings = _capture_qt_warnings(run)
        bad = [m for m in warnings if "parse stylesheet" in m]
        assert bad == [], f"Qt 报样式表解析失败: {bad}"

    def test_text_class_rule_is_inlined_after_base(self):
        runtime = _render(
            '<Window title="t" width="320" height="200">\n'
            "  <Style>.hl { color: #ff0000; }</Style>\n"
            '  <Column><Text class="hl">x</Text></Column>\n'
            "</Window>\n"
        )
        text = next(c for c in runtime._built_components if type(c).__name__ == "Text")
        sheet = text.widget.styleSheet()
        assert '[pw-class~="hl"]' in sheet
        # 组件默认样式在前，用户规则在后（后写胜出）
        assert sheet.index("QLabel {") < sheet.index('[pw-class~="hl"]')

    def test_text_id_rule_also_clean(self):
        def run():
            _render(
                '<Window title="t" width="320" height="200">\n'
                "  <Style>#title { color: #00ff00; }</Style>\n"
                '  <Column><Text id="title">x</Text></Column>\n'
                "</Window>\n"
            )

        warnings = _capture_qt_warnings(run)
        assert [m for m in warnings if "parse stylesheet" in m] == []

    def test_text_props_still_applied(self):
        """包了 QLabel{} 之后，color / size / bold 这些仍要落到控件上。"""
        runtime = _render(
            '<Window title="t" width="240" height="120">'
            '<Text size="22" bold color="#123456">x</Text></Window>'
        )
        text = next(c for c in runtime._built_components if type(c).__name__ == "Text")
        sheet = text.widget.styleSheet()
        assert "#123456" in sheet
        assert "font-size:22px" in sheet
        assert "font-weight:600" in sheet


# --------------------------------------------------------------------------
# 4) 全组件示例本身要一直是干净的（否则它就不再是「能跑的文档」）
# --------------------------------------------------------------------------


class TestShowcaseExample:
    """`examples/showcase.paw` 覆盖全部内置组件，必须 check + render 双通过。

    它是上面几条 bug 的发现现场，也是最容易悄悄腐烂的文件 —— 组件改名、
    属性收紧、样式引擎调整，都会先在这里暴露。
    """

    @staticmethod
    def _path():
        from pathlib import Path

        return Path(__file__).resolve().parent.parent / "examples" / "showcase.paw"

    def test_example_exists(self):
        assert self._path().is_file(), "examples/showcase.paw 不见了"

    def test_example_passes_check(self):
        from pawui.cli import check

        assert check(str(self._path())) == 0

    def test_example_renders_and_builds_every_builtin(self):
        runtime = _render(self._path().read_text(encoding="utf-8"))
        built = {type(c).__name__ for c in runtime._built_components}
        missing = sorted(set(RUNTIME_BUILTINS) - built)
        assert missing == [], f"示例里这些组件没建出控件: {missing}"

    def test_example_has_no_qt_stylesheet_warnings(self):
        def run():
            _render(self._path().read_text(encoding="utf-8"))

        warnings = _capture_qt_warnings(run)
        bad = [m for m in warnings if "parse stylesheet" in m]
        assert bad == [], f"示例触发了 Qt 样式表告警: {bad[:3]}"

