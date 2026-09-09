"""Integration tests for PawUI runtime."""

import pytest

from pawui.runtime import Runtime


class TestRuntime:
    def test_basic_window(self, qapp):
        source = '<Window title="Test" width="400" height="300"/>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        assert rt.root.windowTitle() == "Test"
        rt.root.close()

    def test_window_with_content(self, qapp):
        source = '''
        <Window title="Test" width="400" height="300">
            <Text size="24">Hello World</Text>
        </Window>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_button_with_click(self, qapp):
        source = '''<Window title="Test" width="400" height="300">
            <Button on_click="handler">Click me</Button>
        </Window>
        <script>
def handler():
    pass
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_state_binding(self, qapp):
        source = '''<Window title="Test" width="400" height="300">
            <Text>{$count}</Text>
        </Window>
        <script>
state.count = 42
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_custom_component(self, qapp):
        source = '''
        <Window title="Test" width="400" height="300">
            <Card label="Test" value="123"/>
        </Window>
        <Component name="Card">
            <Column padding="12" bg="surface">
                <Text color="subtext">{$label}</Text>
                <Text size="22" bold="true">{$value}</Text>
            </Column>
        </Component>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_theme_dark(self, qapp):
        source = '<Window theme="dark"/>'
        rt = Runtime(source)
        rt._prepare()
        assert rt.theme.background == "#1e1e2e"
        rt._build_tree()
        rt.root.close()

    def test_theme_light(self, qapp):
        source = '<Window theme="light"/>'
        rt = Runtime(source)
        rt._prepare()
        assert rt.theme.background == "#f5f5f7"
        rt._build_tree()
        rt.root.close()

    def test_theme_extends(self, qapp):
        source = '''
        <Theme extends="dark">
            <Color name="accent" value="#ff0000"/>
        </Theme>
        <Window/>
        '''
        rt = Runtime(source)
        rt._prepare()
        assert rt.theme.accent == "#ff0000"
        rt._build_tree()
        rt.root.close()

    def test_custom_color(self, qapp):
        source = '''
        <Theme extends="dark">
            <Color name="brand" value="#00ff00"/>
        </Theme>
        <Window>
            <Text color="brand">Green</Text>
        </Window>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.theme.custom["brand"] == "#00ff00"
        rt.root.close()

    def test_input_with_on_change(self, qapp):
        source = '''<Window title="Test" width="400" height="300">
            <Input on_change="on_change" placeholder="Type..."/>
        </Window>
        <script>
def on_change(value):
    pass
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_checkbox(self, qapp):
        source = '''<Window title="Test" width="400" height="300">
            <Checkbox checked="true" on_change="on_toggle">Toggle me</Checkbox>
        </Window>
        <script>
def on_toggle(checked):
    pass
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_divider(self, qapp):
        source = '<Window><Divider/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_spacer(self, qapp):
        source = '<Window><Spacer width="10" height="20"/></Window>'
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_row_column_layout(self, qapp):
        source = '''
        <Window>
            <Row spacing="10">
                <Text>A</Text>
                <Text>B</Text>
            </Row>
            <Column spacing="10">
                <Text>C</Text>
                <Text>D</Text>
            </Column>
        </Window>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_animation_props(self, qapp):
        source = '''
        <Window>
            <Text animate="fade" duration="300" delay="100" easing="out-cubic">Animated</Text>
        </Window>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_stagger_on_container(self, qapp):
        source = '''
        <Window>
            <Column stagger="50">
                <Text>A</Text>
                <Text>B</Text>
                <Text>C</Text>
            </Column>
        </Window>
        '''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.root is not None
        rt.root.close()

    def test_script_state_mutation(self, qapp):
        source = '''<Window>
            <Text>{$value}</Text>
            <Button on_click="increment">+</Button>
        </Window>
        <script>
state.value = 0
def increment():
    state.value = state.get("value", 0) + 1
        </script>'''
        rt = Runtime(source)
        rt._prepare()
        rt._build_tree()
        assert rt.state.get("value") == 0
        rt.invoke(rt.namespace["increment"])
        assert rt.state.get("value") == 1
        rt.root.close()

    def test_multiple_windows_error(self, qapp):
        source = '<Window/><Window/>'
        rt = Runtime(source)
        rt._prepare()
        with pytest.raises(Exception, match="only one root"):
            rt._build_tree()

    def test_no_root_elements_error(self, qapp):
        source = '<script>pass</script>'
        rt = Runtime(source)
        rt._prepare()
        with pytest.raises(Exception, match="no UI elements"):
            rt._build_tree()
