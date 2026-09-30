"""样式引擎：`<Style>` + class / id / 级联 / 文本属性 / Grid。"""

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QWidget

from pawui.runtime import Runtime
from pawui.style import compile_css


class TestCompileCss:
    def test_builtin_tag_maps_to_qt_class(self):
        assert compile_css("Button { color: red; }") == "QPushButton { color: red; }"

    def test_custom_component_maps_to_attribute(self):
        out = compile_css("Card { padding: 12; }", {"Card"})
        assert out == '[pw-tag="Card"] { padding: 12px; }'

    def test_class_maps_to_attribute_selector(self):
        assert compile_css(".card { color: red; }") == '[pw-class~="card"] { color: red; }'

    def test_compound_classes_split(self):
        out = compile_css(".card.primary { color: red; }")
        assert out == '[pw-class~="card"][pw-class~="primary"] { color: red; }'

    def test_id_and_pseudo_kept(self):
        assert compile_css("#go:hover { color: red; }") == "#go:hover { color: red; }"

    def test_descendant_and_child(self):
        assert compile_css(".card Text { color: red; }") == (
            '[pw-class~="card"] QLabel { color: red; }'
        )
        assert compile_css("Row > Text { color: red; }") == "QWidget > QLabel { color: red; }"

    def test_attribute_selector_untouched(self):
        out = compile_css("Input[placeholder] { color: red; }")
        assert out == "QLineEdit[placeholder] { color: red; }"

    def test_pawui_aliases_translated(self):
        out = compile_css(".a { radius: 12; bg: #fff; fg: #000; }")
        assert "border-radius: 12" in out and "background-color: #fff" in out and "color: #000" in out


STYLED_APP = """
<Style>
  Card          { padding: 14; }
  .accent-card  { background-color: #ff7a1a; }
  .card Text    { color: #7a7a7a; }
  #go           { font-weight: 600; }
  .title        { wrap: true; align: center; }
</Style>
<Window width="420" height="320">
  <Column padding="16" spacing="10">
    <Text class="title" id="go">a long title</Text>
    <Card class="accent-card" value="a"/>
    <Button id="go">go</Button>
  </Column>
</Window>
<Component name="Card"><Column class="card" bg="surface"><Text>{$value}</Text></Column></Component>
"""


class TestCascade:
    def test_user_rule_lands_after_component_defaults(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        button = rt.root.findChild(QPushButton)
        sheet = button.styleSheet()
        # 组件默认样式在前，用户规则在后 —— 同一张表里后写胜出
        assert sheet.index("QPushButton {") < sheet.index("#go {")
        assert "#go { font-weight: 600; }" in sheet
        rt.root.close()

    def test_descendant_selector_matches_nested_text(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        texts = [label for label in rt.root.findChildren(QLabel) if label.text() == "a"]
        assert texts, "Card 里的 Text 应该存在"
        assert '[pw-class~="card"] QLabel { color: #7a7a7a; }' in texts[0].styleSheet()
        rt.root.close()

    def test_component_and_instance_class_are_merged(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        tagged = [w for w in rt.root.findChildren(QWidget) if w.property("pw-tag") == "Card"]
        assert tagged, "应该能找到自定义组件根控件"
        assert set(str(tagged[0].property("pw-class")).split()) == {"card", "accent-card"}
        rt.root.close()

    def test_tag_selector_matches_all_instances(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        tagged = [w for w in rt.root.findChildren(QWidget) if w.property("pw-tag") == "Card"]
        assert tagged
        assert '[pw-tag="Card"] { padding: 14px; }' in tagged[0].styleSheet()
        rt.root.close()

    def test_text_properties_from_css(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        title = rt.root.findChildren(QLabel)[0]
        assert title.wordWrap() is True
        assert title.alignment() == 132  # AlignCenter | AlignVCenter
        rt.root.close()

    def test_inject_css_applies_and_wins(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        button = rt.root.findChild(QPushButton)
        rt.inject_css("Button { background-color: #22c55e; }")
        sheet = button.styleSheet()
        assert sheet.rstrip().endswith("QPushButton { background-color: #22c55e; }")
        rt.root.close()

    def test_inject_css_is_idempotent_across_reapply(self, qapp):
        rt = Runtime(STYLED_APP)
        rt._prepare()
        rt._build_tree()
        rt.inject_css("#go { font-weight: 600; }")
        once = rt.root.findChild(QPushButton).styleSheet()
        rt.inject_css("#go { font-weight: 600; }")
        twice = rt.root.findChild(QPushButton).styleSheet()
        assert once == twice, "重放不能把同一条规则叠出多份"
        rt.root.close()


class TestGrid:
    def test_grid_places_children_row_major(self, qapp):
        src = """
        <Window width="400" height="300">
          <Grid columns="3" gap="6">
            <Text>a</Text><Text>b</Text><Text>c</Text><Text>d</Text>
          </Grid>
        </Window>
        """
        rt = Runtime(src)
        rt._prepare()
        rt._build_tree()
        grid = rt.root.findChild(QGridLayout)
        assert grid is not None
        positions = sorted(
            (grid.getItemPosition(i)[:2]) for i in range(grid.count()) if grid.itemAt(i) is not None
        )
        assert positions == [(0, 0), (0, 1), (0, 2), (1, 0)]
        rt.root.close()


class TestTooltipIsNotContainer:
    def test_children_built_once(self, qapp):
        rt = Runtime('<Window><Tooltip text="t"><Text>hover</Text></Tooltip></Window>')
        rt._prepare()
        rt._build_tree()
        assert len(rt.root.findChildren(QLabel)) == 1, "Tooltip 的子元素不能构建两次"
        rt.root.close()


class TestCssVariables:
    """`var()` 是编译期替换的：Qt 不认 var()，必须由 StyleEngine 换成实际值。"""

    SRC = """
    <Style>
      :root { --brand: #ff7a1a; --pad: 14px; }
      Card  { padding: var(--pad); border-radius: var(--radius); }
      .tag  { background-color: var(--brand); color: var(--fg); }
      .fb   { color: var(--nope, #123456); }
    </Style>
    <Window width="300" height="200">
      <Card class="tag" value="x"/>
      <Text class="fb">fallback</Text>
    </Window>
    <Component name="Card"><Column class="card"><Text>{$value}</Text></Column></Component>
    """

    def test_custom_property_is_substituted(self, qapp):
        rt = Runtime(self.SRC)
        rt._prepare()
        rt._build_tree()
        card = [w for w in rt.root.findChildren(QWidget) if w.property("pw-tag") == "Card"][0]
        sheet = card.styleSheet()
        assert "padding: 14px" in sheet
        assert "background-color: #ff7a1a" in sheet
        assert "var(" not in sheet
        rt.root.close()

    def test_theme_token_is_available(self, qapp):
        rt = Runtime(self.SRC)
        rt._prepare()
        rt._build_tree()
        card = [w for w in rt.root.findChildren(QWidget) if w.property("pw-tag") == "Card"][0]
        assert f"border-radius: {rt.theme.radius}px" in card.styleSheet()
        rt.root.close()

    def test_fallback_value_is_used(self, qapp):
        rt = Runtime(self.SRC)
        rt._prepare()
        rt._build_tree()
        label = [lb for lb in rt.root.findChildren(QLabel) if lb.text() == "fallback"][0]
        assert "color: #123456" in label.styleSheet()
        rt.root.close()

    def test_missing_variable_is_recorded(self, qapp):
        rt = Runtime(self.SRC)
        rt._prepare()
        rt._build_tree()
        assert "nope" not in rt._style_engine.missing_vars  # 有兜底就不算缺
        rt.root.close()

    def test_unknown_variable_没有兜底会被记录(self, qapp):
        rt = Runtime('<Style>Text { color: var(--ghost); }</Style>'
                     '<Window><Text>x</Text></Window>')
        rt._prepare()
        rt._build_tree()
        assert "ghost" in rt._style_engine.missing_vars
        rt.root.close()


class TestLengthUnits:
    """裸数字要补 px，不然 Qt 直接把整条声明丢掉。"""

    def test_bare_number_gets_px(self):
        assert "padding: 12px" in compile_css(".a { padding: 12; }")
        assert "border-radius: 8px" in compile_css(".a { radius: 8; }")

    def test_explicit_units_untouched(self):
        assert "padding: 1em 2px" in compile_css(".a { padding: 1em 2px; }")
        assert "border-radius: 50%" in compile_css(".a { border-radius: 50%; }")

    def test_multi_value_bare_numbers(self):
        assert "padding: 4px 8px" in compile_css(".a { padding: 4 8; }")

    def test_border_shorthand_gets_px(self):
        out = compile_css(".a { border: 1 solid #ccc; }")
        assert "border: 1px solid #ccc" in out

    def test_line_height_is_not_pxed(self):
        assert "line-height: 1.5" in compile_css(".a { line-height: 1.5; }")
