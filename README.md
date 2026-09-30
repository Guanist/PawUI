# PawUI

官网 / 文档站：[pawui.pages.dev](https://pawui.pages.dev/)

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
- **主题**：默认 `light`（蓝色主色），`theme="dark"` 可切暗色；颜色直接引用：`color="subtext"`、`bg="surface"`。字体与字号改 `theme.font_family` / `theme.font_size`，圆角用 `radius="12"`。
- **布局**：`Column` 纵排、`Row` 横排，`spacing` / `padding` 调节。

## 内置组件

**44 个组件 + 2 个逻辑容器**，`pawui schema` 会有完整属性表。

| 分类 | 组件 |
| --- | --- |
| 布局 | `Window` `Column` `Row` `Grid` `Scroll` `SplitPane` `Panel` `Accordion` `Spacer` `Divider` |
| 文本 | `Text` `Markdown` `CodeBlock` `Link` `Badge` `Tooltip` |
| 交互 | `Button` `Input` `TextArea` `Checkbox` `RadioGroup` `Radio` `Segmented` `Select` `Slider` `NumberInput` `DatePicker` `TimePicker` `FilePicker` `Menu` |
| 数据 | `Table` `List` `VirtualList` `Progress` `Tabs` `Form` `Dialog` |
| 媒体与绘图 | `Image` `Canvas` `Web`（需要 PySide6-Addons） `Avatar` `Skeleton` `Spinner` |
| 其他 | `Shortcut` `If`（条件） `For`（循环） |

## 样式：在 .paw 里写 CSS3

```xml
<Style>
  :root { --brand: #ff7a1a; }
  Card         { radius: 14; padding: 16; bg: var(--surface); }
  .card.title  { font-size: 18px; font-weight: 600; }
  #save:hover  { bg: var(--brand); }
  .card Text   { color: var(--subtext); }
</Style>
```

选择器、CSS 变量、盒模型、flex（`grow` / `shrink` / `wrap` / `justify` / `align`）、
`class` / `id` 全支持。Qt 不认的 `var()` 与文本属性由 PawUI 编译期处理后交给 Qt。
样式没生效就跑 `pawui inspect app.paw`，它会告诉你每个控件真正命中了哪些选择器。

## 脚本操作页面

```python
def wire():
    app.on(".card", "click", lambda e: app.toast(e.target.text, "success"))
    app.append("#list", "<Text>新行</Text>")
    app.query("#title").add_class("highlight")
    app.inject_css("#title { radius: 8px; }")

ready(wire)
```

`query` / `query_all` / `on` / `append` / `prepend` / `remove` / `css` / `toast`，
事件会冒泡。大列表用 `<VirtualList rows="{$rows}">` —— 只渲染视口里的行，
实测 10 万行建树 139ms。

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
pawui inspect app.paw  # 控件树 + 命中的 CSS + state 订阅
pawui help             # 列出文档主题（线上获取，离线回落随包文档）
pawui help theming     # 查看某篇文档
pawui help --refresh   # 强制刷新线上文档
pawui --version
```

`pawui help` 的正文来自官网（`pawui.pages.dev/static/data.js`，6 小时缓存，
离线自动回落随包 `docs/`），所以文档更新不用等发版。
`PAWUI_DOCS_OFFLINE=1` 强制离线，`PAWUI_DOCS_LANG=zh|en` 指定语言。


## 发版

凭据放在仓库外（仓库是公开的）：`~/.pypirc` 存 PyPI 令牌，
`~/.pawui/secrets.env` 存 `GITHUB_TOKEN` / `SITE_REPO`。

```bash
python tools/release.py build     # 清 dist + build + twine check
python tools/release.py upload    # twine upload（读 ~/.pypirc，已存在的版本自动跳过）
python tools/release.py publish   # 打 tag + push + 建 GitHub Release
python tools/release.py site      # docs 同步到站点仓库 + 重建 data.js + 推送
python tools/release.py all       # build → upload → publish
```

Release 正文自动从 `CHANGELOG.md` 里对应版本那一段抠出来。
