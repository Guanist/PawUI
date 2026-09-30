"""布局原语：flex（grow / shrink / wrap / justify / align）与通用盒模型。"""

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from pawui.components import FlowLayout
from pawui.runtime import Runtime


def _rt(src: str, qapp) -> Runtime:
    rt = Runtime(src)
    rt._prepare()
    rt._build_tree()
    return rt


class TestFlex:
    def test_grow_splits_space(self, qapp):
        rt = _rt("""
        <Window width="400" height="100">
          <Row><Text grow="2">wide</Text><Text grow="1">narrow</Text></Row>
        </Window>
        """, qapp)
        wide, narrow = rt.root.findChildren(QLabel)[:2]
        assert wide.width() == 2 * narrow.width(), (wide.width(), narrow.width())
        rt.root.close()

    def test_expand_is_grow_one(self, qapp):
        rt = _rt("""
        <Window width="400" height="100">
          <Row><Text expand="true">a</Text><Text>b</Text></Row>
        </Window>
        """, qapp)
        a, b = rt.root.findChildren(QLabel)[:2]
        assert a.width() > b.width()
        rt.root.close()

    def test_shrink_zero_pins_width(self, qapp):
        rt = _rt("""
        <Window width="120" height="100">
          <Row><Text shrink="0">fixedfixedfixed</Text><Text>rest</Text></Row>
        </Window>
        """, qapp)
        pinned = rt.root.findChildren(QLabel)[0]
        assert pinned.minimumWidth() == pinned.sizeHint().width()
        rt.root.close()

    def test_justify_center_inserts_stretch(self, qapp):
        rt = _rt("""
        <Window width="300" height="100">
          <Row justify="center"><Button>x</Button></Row>
        </Window>
        """, qapp)
        button = rt.root.findChild(QPushButton)
        assert button.x() > 0
        rt.root.close()


class TestWrap:
    def test_row_wrap_uses_flow_layout(self, qapp):
        rt = _rt("""
        <Window width="400" height="200">
          <Row wrap="true" gap="6">
            <Button>A</Button><Button>B</Button><Button>C</Button>
          </Row>
        </Window>
        """, qapp)
        row = rt.root.findChild(FlowLayout).parentWidget()
        assert isinstance(row.layout(), FlowLayout)
        ys = {b.y() for b in rt.root.findChildren(QPushButton)}
        assert len(ys) == 1, "宽度够的时候不该换行"
        rt.root.close()

    def test_flow_wraps_when_narrow(self, qapp):
        rt = _rt("""
        <Window width="400" height="200">
          <Row wrap="true" gap="6">
            <Button>AAAA</Button><Button>BBBB</Button><Button>CCCC</Button>
          </Row>
        </Window>
        """, qapp)
        row = rt.root.findChild(FlowLayout).parentWidget()
        row.setFixedWidth(90)
        qapp.processEvents()
        ys = {b.y() for b in rt.root.findChildren(QPushButton)}
        assert len(ys) > 1, "挤不下就必须换行"
        rt.root.close()

    def test_without_wrap_row_is_linear(self, qapp):
        rt = _rt("""
        <Window width="400" height="200">
          <Row><Button>A</Button><Button>B</Button></Row>
        </Window>
        """, qapp)
        assert rt.root.findChild(FlowLayout) is None
        rt.root.close()


class TestBoxModel:
    def test_margin_wraps_without_changing_identity(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Text id="t" margin="12">hello</Text>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        assert label is not None, "id 必须还能找到本体"
        assert label.geometry().x() == 12 and label.geometry().y() == 12
        rt.root.close()

    def test_margin_two_values_css_order(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Text id="t" margin="4 20">x</Text>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        host = label.parentWidget()
        margins = host.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (20, 4, 20, 4)
        rt.root.close()

    def test_border_rule_targets_only_that_widget(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Column><Text id="t" border="2 solid #ff0000">x</Text></Column>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        assert "border:2px solid #ff0000" in label.styleSheet()
        rt.root.close()

    def test_border_width_and_color(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Column><Text id="t" border_width="3" border_color="#00ff00">x</Text></Column>
        </Window>
        """, qapp)
        sheet = rt.root.findChild(QLabel, "t").styleSheet()
        assert "border-width:3px" in sheet and "border-color:#00ff00" in sheet
        rt.root.close()

    def test_generic_width_height(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Column><Text id="t" width="120" height="30">x</Text></Column>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        assert (label.width(), label.height()) == (120, 30)
        rt.root.close()

    def test_window_owns_its_size(self, qapp):
        rt = _rt("""
        <Window width="320" height="240"><Text>x</Text></Window>
        """, qapp)
        assert rt.root.width() == 320 and rt.root.height() == 240
        assert rt.root.minimumWidth() < 320, "窗口不能被钉死"
        rt.root.close()

    def test_text_alignment_prop(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Column><Text id="t" align="center">x</Text></Column>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        assert int(label.alignment()) == 132  # AlignHCenter | AlignVCenter
        rt.root.close()

    def test_text_ellipsis_and_selectable(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Column><Text id="t" ellipsis="true" selectable="true">a very long text</Text></Column>
        </Window>
        """, qapp)
        label = rt.root.findChild(QLabel, "t")
        assert label.text() == "a very long text"
        assert label.textInteractionFlags() != 0
        rt.root.close()

    def test_margin_host_is_a_widget(self, qapp):
        rt = _rt("""
        <Window width="300" height="200">
          <Text id="t" margin="10"><b>x</b></Text>
        </Window>
        """, qapp)
        assert isinstance(rt.root.findChild(QLabel, "t").parentWidget(), QWidget)
        rt.root.close()
