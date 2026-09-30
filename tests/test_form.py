"""Form 校验 UI：错误要画在页面上，而不是只躺在内存里。"""

from PySide6.QtWidgets import QLabel, QLineEdit

from pawui.runtime import Runtime

FORM = """
<Script>
submitted = []
def on_ok():
    submitted.append(app.query("#name").text)
</Script>
<Window width="360" height="280">
  <Form on_submit="on_ok">
    <Input id="name" placeholder="名字" required="true" error="名字不能空"/>
    <Input id="age" placeholder="年龄" min_length="2"/>
  </Form>
</Window>
"""


def _rt(src: str, qapp) -> Runtime:
    rt = Runtime(src)
    rt._prepare()
    rt._build_tree()
    return rt


class TestValidation:
    def test_empty_required_fails(self, qapp):
        rt = _rt(FORM, qapp)
        assert rt.validate() is False
        assert "名字不能空" in rt.validation_errors
        rt.root.close()

    def test_error_is_painted_on_page(self, qapp):
        rt = _rt(FORM, qapp)
        rt.validate()
        texts = [lb.text() for lb in rt.root.findChildren(QLabel) if lb.isVisible()]
        assert "名字不能空" in texts, texts
        rt.root.close()

    def test_error_border_applied(self, qapp):
        rt = _rt(FORM, qapp)
        rt.validate()
        sheet = rt.root.findChild(QLineEdit, "name").styleSheet()
        assert rt.theme.danger in sheet
        rt.root.close()

    def test_error_clears_when_fixed(self, qapp):
        rt = _rt(FORM, qapp)
        rt.validate()
        rt.query("#name").widget.setText("骆戡")
        rt.query("#age").widget.setText("18")
        assert rt.validate() is True
        assert rt.validation_errors == []
        assert rt.theme.danger not in rt.root.findChild(QLineEdit, "name").styleSheet()
        rt.root.close()

    def test_min_length(self, qapp):
        rt = _rt(FORM, qapp)
        rt.query("#name").widget.setText("x")
        rt.query("#age").widget.setText("1")
        assert rt.validate() is False
        assert any("Minimum length" in e for e in rt.validation_errors)
        rt.root.close()


class TestSubmit:
    def test_submit_blocked_by_errors(self, qapp):
        rt = _rt(FORM, qapp)
        assert rt.submit() is False
        assert rt.namespace["submitted"] == []
        rt.root.close()

    def test_submit_calls_handler_when_valid(self, qapp):
        rt = _rt(FORM, qapp)
        rt.query("#name").widget.setText("骆戡")
        rt.query("#age").widget.setText("18")
        assert rt.submit() is True
        assert rt.namespace["submitted"] == ["骆戡"]
        rt.root.close()

    def test_form_summary_shows_errors(self, qapp):
        rt = _rt(FORM, qapp)
        rt.submit()
        labels = [lb for lb in rt.root.findChildren(QLabel) if lb.isVisible()]
        assert any("名字不能空" in lb.text() for lb in labels)
        rt.root.close()

    def test_submit_without_form_only_validates(self, qapp):
        rt = _rt('<Window><Input id="a" required="true"/></Window>', qapp)
        assert rt.submit() is False
        rt.root.close()
