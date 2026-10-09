# Changelog

## [0.1.3.5.1] - 2026-10-09

### 许可证
- **GPL-3.0-or-later → LGPL-3.0-or-later**。用 PawUI 做的程序现在**可以闭源发布**，
  代价是要（1）声明用了 PawUI 并附带 `LICENSE` + `COPYING`，（2）允许用户替换这个库
  （Python 包天然满足）。
  换它的主要理由：**和 PySide6 一致**（它自己就是 LGPL-3.0），不额外给使用者加负担。
  文件结构：`LICENSE` = LGPL-3.0，`COPYING` = 它引用的 GPL-3.0。
- `docs/packaging.md` + 中文版新增「打包后要闭源？先看许可证」一节，并把它加进
  分发清单；`README.md` 新增「许可证」一节。

### 文档
- `pyproject.toml` 的 `description` 改成**英文前置**（GitHub search 主要按英文索引）：
  `Declarative UI for Python — HTML-like .paw files, native Qt/PySide6 widgets, no build step.`

## [0.1.3.5] - 2026-10-07

### 新增
- **8 个新组件**（都是 Qt 本来就有、之前没暴露的）：`<Alert>` 行内提示条、
  `<GroupBox>` 带标题分组、`<DoubleInput>` 浮点输入、`<DateTimePicker>` 日期+时间、
  `<ColorPicker>` 取色、`<Dial>` 旋钮、`<LCD>` 数码显示、`<Tree>` 树形列表。
  组件总数 **44 → 52**。
- **`<Window>` 支持菜单栏**：`Window` 改用 `QMainWindow`，因此可以用
  `menuBar()`；内容区仍是普通容器（`centralWidget`），布局行为不变。
- **主题 token 扩充成一套设计系统**（纯加法，旧字段全部保留）：

  | 类别 | 新增 |
  | --- | --- |
  | 状态色 | `success` / `warning` / `info`（进 `COLOR_FIELDS`，可当令牌名用） |
  | 层次色 | `surface_raised` / `surface_sunken` / `surface_hover` / `surface_active`（留空自动按明暗推导） |
  | 圆角分级 | `radius_sm=6` / `radius_md=10` / `radius_lg=16` |
  | 字号分级 | `font_xs=11` / `font_sm` / `font_md=13` / `font_lg=15` / `font_xl=20` |
  | 字重 | `weight_normal/medium/semibold` |
  | 间距刻度 | `space_xs=4` / `space_sm` / `space_md=12` / `space_lg=16` / `space_xl=24` |
  | 投影 | `shadow` / `shadow_blur` / `shadow_offset_y` / `shadow_color` |
  | 对比色 | `on_accent`（默认按主色明暗自动选黑/白） |

### 修复
- **`bg="{$token}"` 这类动态取主题色会静默失效**：`resolve_color()` 对模板
  **提前 return**，不再做令牌查表 —— 于是 `<Column bg="{$token}"/>`（token 取
  `"accent"`）拿到的是裸字符串 `"accent"`，Qt 当非法颜色整条丢弃，界面没上色、
  只在 stderr 留一条 `unknown color 'accent'`。现在模板解析出的字符串会**再过一次
  令牌查表**。showcase 里的 8 条 `unknown color` 警告随之归零。
- **`<Window>` 的内容布局访问方式变了**：`rt.root` 现在是 `QMainWindow`，
  内容布局在 `centralWidget()` 上；`Window` 新增 `body` 属性指过去。

### 改进
- **`theme.qss()` 重写**：补上以前完全没有规则的控件（`QRadioButton` / `QSlider` /
  `QProgressBar` / `QGroupBox` / `QTabBar` / `QMenuBar` / `QToolTip` / 数据视图 /
  日历），统一 hover / focus / disabled 态，颜色全部走 token（不再散落硬编码
  `#ffffff`）。滚动条、弹出层等既有规则保持不变。
- **组件圆角改成读分级 token**：`components.py` / `widgets.py` 里 50 处硬编码圆角
  （`10` / `8` / `9` / `12` / `17` / `24`…）统一换成 `theme.radius_sm/md/lg`，
  容器的默认圆角从 `radius`（24，偏大）降到 `radius_md`。
- **容器可选投影**：新增 `apply_shadow()`，`Panel` / `GroupBox` / `Dialog` / `Alert`
  支持 `shadow="true"`（Qt 没有 CSS 的 `box-shadow`，用 `QGraphicsDropShadowEffect`）。
- **`<Alert>` 配色改为读主题状态色**，不再硬编码 `#22c55e` / `#f59e0b`，和
  `app.toast()` 的 kind 配色统一。
- `example/showcase.paw` 补上 8 个新组件（表单页加 DoubleInput / DateTimePicker /
  ColorPicker，数据页加 Tree，交互页加 Alert ×4 / GroupBox / Dial / LCD / 带投影分组）。

### 文档
- 新增 `docs/component-extra-fields.md` + 中文版：8 个新组件的属性表与用法。
- `README.md`：组件数 44 → 52，组件表补 8 个（新增「反馈」一行）。
- `AI_PROMPT.md`：组件表同步补 8 行。
- 站点 `build.py` 的 `GROUPS` 注册新文档；`index.html` 三处数字（hero 徽标 /
  stats 卡片 / 组件区标题）44 → 52，组件卡片列表补 8 个。

## [0.1.3.4] - 2026-10-07

### 修复
- **`app.append()` 按文档写法调用会静默失败（不插元素、不报错）**：
  实现签名是 `append(markup, target)`，但文档、`pawui schema`、`cli.py` 的提示里
  一共 5 处都写成 `app.append("#list", "<Text>hi</Text>")`（目标在前）。照文档写的
  调用会把片段当选择器去查，查不到就 **静默返回空列表** —— 没有异常，用户几乎
  不可能猜到是参数顺序问题。现在两种顺序都认（靠「哪个参数以 `<` 开头」判断），
  也可以直接用关键字 `append(markup=…, target=…)`。`prepend` 同理。
- **`<Window>` 的根级尾簧抢走几乎全部空间**（#8）：`Window` 不是 `Container` 的
  子类，也没声明 `add_trailing_stretch`，于是根布局被塞了一个 stretch=1 的尾簧；
  中间那个没写 `expand` 的子容器（`<Window><Column>…</Column></Window>` 是很常见的
  骨架）竞争不过它，被压成 sizeHint 高 —— 600px 的窗口里只剩 36px，下方整片空白。
  现在 `Window` 显式 `add_trailing_stretch = False`。
  顺带修好了一个更隐蔽的问题：改前窗口里 `justify="center"` 的容器因为自身高度被
  压没，两个定位弹簧高度恒为 0，**垂直居中根本没生效**。
- **裸字符串被当成主题令牌，撞名的字面量全被悄悄替换**：`resolve_prop_value()` 对
  *所有* 属性的裸字符串做 `hasattr(theme, name)` 查找，于是 `<Badge text="text"/>`
  显示成 `#1d1d1f`、`text="radius"` 显示 `24`、`text="dark"` 直接渲染出
  `<bound method Theme.dark of …>`。现在裸字符串一律保留，「令牌名 = 颜色」只由
  `resolve_color()` 在颜色属性上处理；`{$accent}` 这类**明示引用**不受影响。
  （契约变更：`resolve_prop_value("accent")` 从返回颜色值改为返回字面量。）

### 示例
- 新增 `examples/dom-demo.paw`：一个能直接跑、能看见效果的 DOM 用法示例 ——
  5 个按钮分别演示 `query`/`text` 读写、`add_class`/`css`、事件冒泡、
  `append` 插入、`remove` 删除。

### 测试
- `tests/test_dom.py` 新增 4 条：文档顺序、关键字、`prepend` 文档顺序、
  文档顺序也要落在尾簧之前。
- `tests/test_layout.py` 新增 `TestWindowRootLayout`（3 条，来自 PR #9）。
- `tests/test_resolve.py` / `tests/test_widgets_extra.py` 新增字面量与颜色解析用例（来自 PR #10）。

### 文档
- `docs/dom.md` / `docs/zh/dom.md`：说明 `append` 两种参数顺序都支持。

## [0.1.3.3] - 2026-10-04

### 修复
- **`<TextArea bind value on_change>` 写回 state 时成环、界面冻结（崩溃级）**：
  `components.py` 里 `on_change` 的回调没检查 `_suppress`，而 `state.set()` 又没有
  相等判断。于是「state 回填控件 → `QPlainTextEdit.setPlainText` → `textChanged`
  → 回调写回同一个值 → 再回填」停不下来。`setPlainText` 在内容没变时**也会**发
  `textChanged`（它总是先 clear 再 insert），所以环一定会转起来，最终反复抛
  `RecursionError` 并在事件循环里重入，用户侧只看到「点了没反应」。
  现在 `on_change` 回调加上与 `_push_state` 一致的 `_suppress` 守卫。
  注：只有 `TextArea` 有这个环 —— `Select` / `Slider` / `NumberInput` /
  `DatePicker` / `TimePicker` / `Input` 的 setter 是幂等的，值相同时不发信号。
- **`<Table striped>` 在深色主题下白底白字（看不清）**：`_style_table()` 没设
  `alternate-background-color`，Qt 于是落回 `QPalette::AlternateBase` —— 那是平台
  默认的浅色 `#f7f7f7`，配上浅色文字（`#f8f8f2`）对比度只有 **1.005:1**，等于看不见。
  `striped` 默认就是 `true`，所以**所有**深色主题下的 `<Table>` 都会中招。
  现在用 `_blend(surface, background, 0.5)` 显式给出交替色（深色主题下 `#232432`，
  对比度提到 ~14:1）。
- **`<Tabs>` 丢弃页签内子元素的 `stretch()`，`expand` / `grow` 静默失效**：
  `Tabs.build()` 直接 `addWidget(widget)`，没带上 `inner_comp.stretch()`，再加上无条件
  `addStretch(1)`，页签里的内容永远只按 sizeHint 高显示。`examples/showcase.paw` 里
  就有 4 个页签的 `grow="1"` 被静默吃掉。现在透传 `stretch()`，且只在「没有子元素
  要伸展」时才补尾簧。

### 新增
- **`<Select placeholder="…">`**：这台属性此前**只写在了文档里、实现里没有**
  （0.1.3.3 补上）。没有任何选项被选中时显示灰色提示文字并保持「未选中」
  （`currentIndex = -1`）；一旦 `value` 命中列表项就正常显示该项，不写
  `placeholder` 时行为完全不变。

### 文档
- 新增 `CONTRIBUTING.md`：环境、提交前检查、代码地图、API 硬规矩、常见坑、
  文档/发版流程，以及「提 issue 前先自证」的要求。
- 新增 `docs/component-dialog-menu.md` + `docs/zh/component-dialog-menu.md`：
  `Dialog` / `Menu` / `Shortcut` / `Select` 四个组件此前在随包文档里完全没有说明，
  现在补齐了属性表与用法（含 `<Dialog>` 的 `cancel` / `accept` 是**按钮文案**、
  `<Menu>` 的 `items` 同时支持字面量与 `{$list}`、`<Shortcut>` 不占视觉位置等）。

### 测试
- 新增 `tests/test_regressions_0133.py`（10 条），钉住上面三条的触发路径：
  `on_change` 写回 state 不成环、回填期间不触发 `on_change`、深色表格有
  `alternate-background-color`、页签内 `expand` 能撑满、无 stretch 时尾簧仍在、
  `<Select placeholder>` 的四种取值场景。

## [0.1.3.2] - 2026-09-30

### 修复
- **`<Text>` 上的 class / id 样式全部失效（静默）**：`<Style>` 的用户规则是**按控件
  内联追加**到自带样式表后面的（`runtime._apply_user_css`），而 Qt 只在「整段没有 `{`」
  时才把样式表当裸声明解析 —— 一旦拼上 `.hl { … }` 这类规则，`<Text>` 前面那串
  裸声明（`color:…; font-size:…`）就会被当成选择器，整张表解析失败，Qt 在 stderr
  丢一句 `Could not parse stylesheet` 就完事。于是 `<Text class="x">` / `<Text id="x">`
  的样式**看起来配了、实际一点没生效**。现在 `Text` 的内联样式统一包成
  `QLabel { … }`。其余组件（Button / Input / Badge / Slider / Divider …）自带样式
  本来就带选择器前缀，不受影响。
- **`<Tabs>` 里放 `<Dialog>` 直接崩（`AttributeError: 'Dialog' object has no
  attribute '_justify'`）**：`Dialog` 自己搭布局、没走 `Container.build()`，因此
  没初始化 `_justify` / `_cross_align`；而 `Tabs` 建完子元素会对它调
  `Container.add_child()`，那里无条件读这两个字段。现在默认值提到 `Component`
  基类，并且 `Dialog` 自己也会读 `justify` / `align` 属性（不再被默认值吞掉）。
  同类隐患（`Grid` / `Accordion` 等自建布局的容器）一并消除。
- **`pawui check` 把 22 个组件误报成 `unknown component`**：`cli.py` 从
  `components` 导入了基础 22 项的 `BUILTINS`，而 runtime 用的是
  `widgets.BUILTINS`（合并后的 44 项）。于是 `Badge` `Table` `Canvas`
  `Markdown` `SplitPane` 等明明能跑，`check` 却一律报错 —— `pawui check` 在
  真实项目上基本不可用。现在两边共用同一份注册表。

### 测试
- 新增 `tests/test_regressions_0132.py`（13 条），分别钉住上面三条的触发路径：
  `cli.BUILTINS is widgets.BUILTINS`、`Tabs` × 8 种容器子类、以及用
  `qInstallMessageHandler` 捕获 Qt 的样式表解析告警断言为空。
- 全量 354 passed。

### 示例
- 新增 `examples/showcase.paw`：一窗 6 个标签页覆盖全部 44 个内置组件 +
  `If` / `For` / `Tab` 三个逻辑标签，`pawui check` / `render` 均干净通过。
  它也是上面三个问题的发现现场。

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
