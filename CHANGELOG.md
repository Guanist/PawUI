# Changelog

## [0.1.3.1] - 2026-09-30

### 修复
- **`<TextArea bind="…" value="{$…}">` 回声死循环（崩溃级）**：`QPlainTextEdit`
  的 `setPlainText` 在 Qt 6.11 下**即使内容没变也会发 `textChanged`**，
  于是 state → 控件 → textChanged → 推回 state → 监听器又写回控件……一直互相触发，
  最后 `RecursionError`。因为异常抛在 Qt 事件循环内部，本地看起来只是「界面卡一下」，
  换成 CI 的 pytest-qt 才被判定为失败。现在 state → 控件的写入统一压住回声
  （`_suppress` 守卫），`<Select>` 的 `setCurrentText` 同处理。
- **`QComboBox::down-arrow` 不再用 `image: none`**：那会让 Qt 去解析空 pixmap，
  改成 0 尺寸 + 无边框（箭头本来就是自绘的 chevron）。
- **应用级样式表的守卫**：`QApplication` 已销毁时跳过 `setStyleSheet`，不再碰野指针。
- CI 补 ubuntu 缺的系统库（`libegl1` 等，PySide6 缺了会 `ImportError: libEGL.so.1`）。

### 已知问题
- PySide6 6.11 的 **macOS + Python 3.12** 轮子，在 `QT_QPA_PLATFORM=offscreen` 下
  会在 `QApplication::setStyleSheet` 里段错误（崩溃帧全在 Qt 内部）。同代码在
  macOS 3.10 / 3.11 与 Linux / Windows 3.12 均正常，所以 CI 先排除这个组合，
  等 PySide6 更新后再加回来。图形界面的 cocoa 平台不受影响。

## [0.1.3] - 2026-09-30

### 新增 —— 样式系统（在 .paw 里直接写 CSS3）
- **`<Style>` 块**：任意层级的 `<Style>` 被抽到全局作用域，按控件编译成 QSS。
  选择器支持 `Tag` / `.class` / `.class.other` / `#id` / `[attr=value]` /
  后代 / 子代 `>` / 逗号分组 / `:hover` `:pressed` `:disabled` 等伪状态。
- **CSS 变量**：`:root { --brand: #ff7a1a; }` + `var(--brand)` / `var(--x, 兜底)`。
  Qt 不支持 `var()`，所以是编译期替换；主题的每个字段（`--bg` `--fg` `--accent`
  `--surface` `--border` `--danger` `--radius` …）与 `<Color>` 自定义色都是变量。
  缺失且无兜底时会被记录并提示，而不是静默丢声明。
- **盒模型与 flex**：`margin`（CSS 上右下左顺序）、`border` / `border_width` /
  `border_color`、通用的 `width` / `height` / `min_*` / `max_*`；
  `grow` / `shrink` / `wrap` / `justify` / `align` / `gap`。
  `Row wrap="true"` 走自绘 `FlowLayout`（挤不下自动换行），等价 `flex-wrap: wrap`。
- **长度单位**：长度类属性的裸数字自动补 `px`（`radius: 12` 等价 `radius: 12px`），
  `border: 1 solid #ccc` 也认。
- **文本属性进 CSS**：`wrap` / `ellipsis` / `align` / `selectable` / `line-height`
  在 CSS 里写就能生效（QSS 不认这几个，由运行时施加），也能直接当组件属性。
- **class / id**：落到动态属性与 `objectName` 上供选择器匹配，多来源 class 合并
  而不是覆盖。
- **运行时注入**：`app.inject_css(text)` 追加在 `<Style>` 之后（优先级更高、幂等），
  `app.css(selector, decls)` 与 `el.css(decls)` 按选择器 / 单元素注入。

### 新增 —— 脚本操作页面（DOM）
- `app.query(sel)` / `app.query_all(sel)`：选择器语法与 `<Style>` 完全一致。
- `Element` 句柄：`text` / `value` / `attr()` / `add_class()` / `remove_class()` /
  `toggle_class()` / `append()` / `prepend()` / `clear()` / `remove()` / `children()` /
  `closest()` / `query()` / `on()` / `css()`。
- `app.append(sel, markup)`：插入的片段按正常 `.paw` 解析（自定义组件、`{$state}`、
  `on_click` 都能用），追加位置在尾部弹簧之前。
- `app.on(sel, kind, fn)` / `el.on(kind, fn)`：`click` `change` `input` `enter`
  `hover` `leave` `focus` `blur`。回调拿到 `Event`（`type` / `target` / `value` /
  `checked`）。事件**会冒泡**，点卡片里的文字同样能触发绑在卡片上的处理函数。
- `ready(fn)`：控件树建好之后执行 —— 脚本里访问控件的正确时机。
- `app.toast(text, kind)`：浮动提示，自动淡入淡出、多条向上叠。

### 新增 —— 组件从 21 个扩到 44 个
- 布局：`Grid`、`SplitPane`、`Panel`、`Accordion`。
- 表单：`RadioGroup` / `Radio`、`Segmented`、`NumberInput`、`DatePicker`、
  `TimePicker`、`FilePicker`。
- 数据：`Table`（列头 / 排序 / 行选择 / dict 或 list 行）、`List`、`VirtualList`。
- 展示：`Badge`、`Avatar`、`Skeleton`、`Spinner`、`Link`、`CodeBlock`、`Markdown`。
- 绘图与杂项：`Canvas`（QPainter 自绘 + `Painter` 门面 API）、`Shortcut`。

### 新增 —— 表单校验画到页面上
- `app.validate()` 把错误画到出错字段上：红色描边 + 字段下方一行错误文字。
- `app.submit()`：先校验，全部通过才调 `<Form on_submit>`；失败时表单顶部显示汇总。
- `Input` / `TextArea` 支持 `required`、`min_length`、`error`。

### 新增 —— 性能与工具
- **`pawui help` 改成读线上文档**：正文拉到的是官网渲染用的同一份
  `static/data.js`（6 小时缓存，写进 `%LOCALAPPDATA%\pawui\docs.json`），
  离线 / 内网自动回落随包 `docs/`；`--refresh` 强制刷新，`--offline` 完全不联网，
  `PAWUI_DOCS_LANG=zh|en` 指定语言。每次输出末尾标明来源 —— 改文档不用发版。
- **`<VirtualList>` 虚拟滚动**：只渲染视口内的行。同一行模板实测：1000 行建树
  1300ms → 87ms，2000 行 3200ms → 88ms，100000 行 139ms 且只建几十个控件。
- **样式编译预解析**：规则编译期就切好选择器、解析好声明，匹配只做匹配本身；
  QSS 与文本属性两次遍历合并成一次，算出来没变就跳过 `setStyleSheet`。
- **`pawui inspect <file.paw>`**：打印控件树、每个控件**真正命中**的 CSS 选择器
  与 state 订阅关系。

### 新增 —— 无障碍
- `aria_label` → `accessibleName`，`aria_description` → `accessibleDescription`，
  `tabindex="-1"` 关掉 Tab 聚焦；没写 `aria_label` 时自动用控件文字兜底。

### 修复
- **`<Script>` / `</Script>` 大小写不一致就报错**：开标签判定大小写不敏感、
  闭合标签查找却是敏感的，`<Script>…</Script>` 会被认成脚本块然后死在
  「找不到闭合标签」上。
- **按钮点击不再重复派发**：鼠标点击由事件过滤器按最深子控件派发并向上冒泡，
  键盘激活与 `el.click()` 走 `clicked` 信号，两条路径互斥。
- **事件过滤器不再悬挂**：过滤器挂在控件自己身上（父对象即控件），控件销毁时
  一起回收，退出时不再越界崩溃。
- **`_ElidedLabel` 每次 resize 都重设文字**：没开省略号 / 行高时不再重算。
- **延迟动画 × 重建竞态（崩溃级）**：`animate` + `delay` 的控件在延迟窗口内被
  `<If>` / `<For>` 局部刷新、`app.refresh()` 全量重建或 `pawui watch` 热重载销毁后，
  延迟回调会抛 `RuntimeError: Internal C++ object already deleted`；异常发生在
  Qt 事件循环内部，用户代码无法捕获。现在延迟回调前统一做 `isValid()` 守卫。
- **`bool("False") == True`（崩溃级）**：`bind_state` 把模板渲染成字符串再交给控件，
  `Checkbox` 的 `setChecked(bool(v))` 于是恒为真 —— 复选框点不掉、主题切不动、
  开关 / state / 界面三者互相矛盾。改为传原始值 + 统一 `_truthy()` 判真。
- **`<Theme>` / `<Color>` 覆盖丢失**：`set_theme()` 会丢掉文件里定义的配色，切主题后
  再也回不去。现在切到别的内置主题时内置字段让位、自定义色保留，切回文件声明的
  主题则整份覆盖复原。
- **组件属性模板不穿透**：`<Card value="{$name}"/>` 里 `value` 本身是模板时，
  界面会显示字面量 `{$name}`。`resolve_raw` 现在会带防环地链式求值。
- **细节控件不跟随主题**：`QScrollBar` / `QMenu` / `QToolTip` / `QComboBox` 原本
  没有任何样式规则，Dialog 的按钮与 Menu 的 `QToolButton` 也是系统默认外观。
- **字体与圆角不可定制**：`theme.font_family` / `font_size` / `title_size` 是死字段
  （样式表里写死字体族、字号只在 `QLineEdit` 里写死）。现在真正走主题，且
  `Text` / `Input` / `TextArea` 支持 `font`，多个组件支持 `radius`。
- **`Progress` 百分比不居中**：`QProgressBar` 默认左对齐，还塞在固定 10px 高的条里，
  文字被裁。现在默认居中、高度自适应、字号跟随主题，可用 `align` 调整。
- **`Select` / `Menu` 的 `items` 字面量静默失效**：`items="[a, b, c]"` 会被当成
  一整个字符串，渲染成空下拉框且无任何提示。现在支持 `[a, b, c]` 与 `a, b, c`。
- **系统下拉箭头难看**：改为 `paintEvent` 自绘 chevron，跟随主题色。
- **颜色名解析失败时静默**：非法颜色会被原样拼进样式表让 Qt 丢掉整条声明，
  现在会打印一次明确警告。
- **CLI 在管道 / CI 下崩溃**：stdout 被重定向捕获时编码回落 cp936，`pawui check` /
  `render` 抛 `UnicodeEncodeError` 并返回 1（真实控制台反而正常）。现在有编码兜底，
  输出符号也改成 ASCII 安全形式。

### 变更
- **默认主题改为 light + 蓝色主色**：`Theme()` 默认即浅色，`Theme.dark()` 显式给暗色；
  `Runtime` / `cli.run` / `pawui render` 的默认主题与 `pawui schema` 同步更新。
- **开源**：加入 GPLv3 许可证（`LICENSE` + PEP 639 `license` 字段），补 `py.typed`、
  `[project.urls]`、`web` extra，classifier 由 Production/Stable 调整为 Beta。
- 新增 GitHub Actions CI：3 平台 × 3 Python 版本，含 ruff / mypy / pytest 与
  管道输出的 CLI 冒烟测试。
- `pawui` 顶层导出 `Runtime` / `State` / `Theme` 与全部错误类型（`except pawui.PawUIError`
  现在可用；`PyxError` 作为历史别名保留）。

### 测试
- 测试数 193 → 341（今天一共 +148 条）：动画竞态 6、主题切换 3、双向绑定 3、
  Select / Menu 字面量 3、样式系统 27、DOM 24、布局 16、表单校验 9、
  第二批组件 22、虚拟滚动 7、inspect / 无障碍 / toast 12、线上文档 16。
- CI：3 平台 × 3 Python + ruff / mypy / pytest + 管道 CLI 冒烟，全绿。

## [0.1.2.2] - 2026-09-12

### 文档
- README 增加官网 / 文档站链接。


## [0.1.2.1] - 2026-09-12

### 新增
- `Dialog`、`Menu`、`Form` 组件。
- `app.validate()` 和 Input 的 `required` / `min_length` / `error` 校验属性。


## [0.1.2] - 2026-09-12

### 修复
- `<If>` / `<For>` 监听状态变化并局部刷新。
- 修复 `Scroll axis="x"` 始终使用纵向布局。
- 补齐 Checkbox 双向绑定的 state → 控件同步。
- 重建失败时保留旧窗口并输出错误。

### 新增
- 原生 `Select` 下拉选择组件，支持 `items`、`value`、`on_change`、`bind`。


所有 PawUI 的重要变更都会记录在此文件。

## [0.1.1] - 2026-09-09

### 新增
- `TextArea` 组件：多行文本输入，支持 `value` / `placeholder` / `on_change` / `readonly` / `height` / `bind`（双向绑定）。
- `Scroll` 组件：可滚动容器，支持 `axis="y|x"`、`padding` / `spacing` / `bg`。
- `Web` 组件：iframe 等价物，`src`(URL) 或 `html`（支持 `{$state}` 模板）；需要 PySide6-Addons。
- `Runtime.invoke_async(handler, done=fn)`：后台线程执行耗时任务，`done(result, error)` 经 Qt 信号回到主线程，避免卡 UI。

## [0.1.0.2] - 2026-09-09

### 新增
- `Runtime.reload(source)` API + `pawui watch <file.paw>`：文件变化自动重建窗口，保留 state 与 script 函数。

## [0.1.0.1] - 2026-09-09

### 新增
- 文档打包进 wheel/sdist（`share/pawui/docs`），新增 `pawui help [topic]` 命令。
- README 补充 PySide6 依赖说明。

## [0.1.0] - 2026-09-09

### 新增
- `<If condition>` / `<For each in>` 控制流（可嵌套）。
- 属性/索引路径插值：`{$item.name}`、`{$items[0]}`；`For` 的 `in="{$list}"` 取原始 list。
- 组件 `Slider`（min/max/value/step/on_change/accent/bg）、`Progress`（value 绑定）、`Tabs`（`<Tab label>` 页面）、`Image`（src/cover）、`Tooltip`。
- 双向绑定：`bind="name"` / `"{$name}"` 写入 state，Input/Checkbox/Slider 支持。
- 默认 props：`<Component>` 内 `<Prop name default/>`，调用方未传时回退默认值。

### 变更
- **闭源**：移除 LICENSE 与许可证声明，同步精简 CI（移除 PyPI 发布 job）。

## [0.1.0b0] - 2026-09-09

### 新增
- 首个可发布版本：HTML 风格声明式 UI → PySide6。
- 核心组件：`Window` `Column` `Row` `Text` `Button` `Input` `Checkbox` `Divider` `Spacer`。
- 状态系统（`state`）、script 块、主题、入场动画、`pawui run/check/schema/render` CLI。
