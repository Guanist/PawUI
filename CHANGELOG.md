# Changelog

所有 PawUI 的重要变更都会记录在此文件。

## [0.1.1] - 2026-09-10

### 新增
- `TextArea` 组件：多行文本输入，支持 `value` / `placeholder` / `on_change` / `readonly` / `height` / `bind`（双向绑定）。
- `Scroll` 组件：可滚动容器，支持 `axis="y|x"`、`padding` / `spacing` / `bg`。
- `Web` 组件：iframe 等价物，`src`(URL) 或 `html`（支持 `{$state}` 模板）；需要 PySide6-Addons。
- `Runtime.invoke_async(handler, done=fn)`：后台线程执行耗时任务，`done(result, error)` 经 Qt 信号回到主线程，避免卡 UI。

## [0.1.0.2] - 2026-09-10

### 新增
- `Runtime.reload(source)` API + `pawui watch <file.paw>`：文件变化自动重建窗口，保留 state 与 script 函数。

## [0.1.0.1] - 2026-09-10

### 新增
- 文档打包进 wheel/sdist（`share/pawui/docs`），新增 `pawui help [topic]` 命令。
- README 补充 PySide6 依赖说明。

## [0.1.0] - 2026-09-10

### 新增
- `<If condition>` / `<For each in>` 控制流（可嵌套）。
- 属性/索引路径插值：`{$item.name}`、`{$items[0]}`；`For` 的 `in="{$list}"` 取原始 list。
- 组件 `Slider`（min/max/value/step/on_change/accent/bg）、`Progress`（value 绑定）、`Tabs`（`<Tab label>` 页面）、`Image`（src/cover）、`Tooltip`。
- 双向绑定：`bind="name"` / `"{$name}"` 写入 state，Input/Checkbox/Slider 支持。
- 默认 props：`<Component>` 内 `<Prop name default/>`，调用方未传时回退默认值。

### 变更
- **闭源**：移除 LICENSE 与许可证声明，同步精简 CI（移除 PyPI 发布 job）。

## [0.1.0b0] - 2026-09-10

### 新增
- 首个可发布版本：HTML 风格声明式 UI → PySide6。
- 核心组件：`Window` `Column` `Row` `Text` `Button` `Input` `Checkbox` `Divider` `Spacer`。
- 状态系统（`state`）、script 块、主题、入场动画、`pawui run/check/schema/render` CLI。