# PawUI

轻量、直接运行的 Python 声明式 UI 层。HTML 风格，Qt/PySide6 渲染（原生抗锯齿、QSS 圆角/悬停/聚焦、IME 组字正常），无构建。

## 安装

```bash
pip install pawui        # 依赖 PySide6>=6.5，自动安装
python -m pip install --upgrade pawui
```

## 运行

```bash
pawui app.paw
```

也可以传统方式启动：

```python
import pawui
pawui.run("app.paw")
```

## 语法（HTML 风格）

```html
<Window title="你好" width="460" height="840" theme="dark">
  <Column padding="24" spacing="12">
    <Text size="24" bold>欢迎使用 PawUI 👋</Text>
    <Text size="13" color="subtext">副标题</Text>

    <Text>{$greeting}</Text>

    <Row spacing="8">
      <Button on_click="increment">点我 +1</Button>
      <Button on_click="reset">清空</Button>
    </Row>

    <Input placeholder="输入你的名字..." on_change="on_name"/>
    <Text>你好，{$name}</Text>

    <Card label="点击量" value="{$count}"/>
  </Column>
</Window>

<!-- 自定义组件 -->
<Component name="Card">
  <Column padding="12" bg="surface">
    <Text color="subtext">{$label}</Text>
    <Text size="22" bold>{$value}</Text>
  </Column>
</Component>

<script>
def increment():
    state.count = int(state.get("count", 0)) + 1
</script>
```

## 要点

- **状态绑定**：`{$count}` / `{count}` / `$count`，在 `<script>` 里改 `state.count = ...` 界面自动刷新。
- **事件**：字符串引用 `<script>` / `main.py` 里的函数：`on_click="函数名"`。
- **组件**：`<Component name="X">...</Component>` 定义，直接 `<X .../>` 使用。
- **主题**：`theme="dark" | "light"`，颜色可直接引用：`color="subtext"`、`bg="surface"`。
- **布局**：`Column` 纵排、`Row` 横排，`spacing` / `padding` 调节。

## 内置组件

`Window` `Column` `Row` `Text` `Button` `Input` `Checkbox`（开关） `Divider` `Spacer` `Slider` `Progress` `Tabs` `Image` `Tooltip` `TextArea`（多行输入） `Scroll`（可滚动容器） `Web`（内嵌网页，需要 PySide6-Addons） `If`（条件渲染） `For`（列表循环）

```html
<For each="item" in="{$items}">
  <If condition="{$item.done}">
    <Text>{$item.name}</Text>
  </If>
</For>
```

## CLI

```bash
pawui run app.paw      # 运行（或直接 pawui app.paw）
pawui watch app.paw    # 热重载：保存即重建窗口
pawui check app.paw    # 仅语法检查
pawui schema           # 输出组件 JSON Schema
pawui render app.paw   # 离屏渲染自检
pawui help             # 列出内置文档主题
pawui help theming     # 查看某篇文档
pawui --version
```
