# 贡献手册

PawUI 是一个「AI 写 UI」的声明式 UI 层：`.paw`（HTML 风格）→ PySide6/Qt。
仓库是自用项目，不追求大而全的社区流程，但欢迎 **能落地的改动**。

## 一句话原则

**有问题别光提 issue，请直接开 PR。** 能自己修的就自己修，附上复现和 diff。
提 issue 请先自证（见下文），别把「猜测的根因」当结论发出来。

## 环境

```bash
git clone https://github.com/LK-BLOG/PawUI.git
cd PawUI
python -m pip install -e ".[dev]"     # 依赖 PySide6>=6.5 + pytest/ruff/mypy
```

Windows 上建议用系统 Python 3.11+（与 CI 的 3.11 对齐）。

## 提交前必须全绿

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q   # 测试（Windows PowerShell: $env:QT_QPA_PLATFORM='offscreen'）
ruff check .
mypy pawui
pawui check examples/showcase.paw               # 示例必须一直可跑（CI 也守这条）
```

改了**视觉**相关的代码，还要用真实平台跑一次 `root.grab()` 看截图 ——
`offscreen` 没有 CJK 字体，出现 `□□` 是预览假象，不是 bug。

## 代码地图

| 文件 | 职责 |
| --- | --- |
| `parser.py` | HTML 扫描 → `Program`（标签、属性、自闭合、`<script>` 原文、`<Component>`、`<Theme>/<Color>`、`<Style>` 提升） |
| `nodes.py` | AST |
| `resolve.py` | 值 / 模板 / handler 解析（**不 import GUI**） |
| `components.py` | 第一批 Qt 控件 + `BUILTINS` + `ToggleSwitch` / `FlowLayout` |
| `widgets.py` | 第二批（Table / VirtualList / Canvas / Markdown / 面板 / 表单字段）+ 合并后的 `BUILTINS` |
| `style.py` | CSS3 → QSS 编译器 + 层叠 + `var()` |
| `dom.py` | 脚本侧的 `Element` / `Event` |
| `runtime.py` | QApplication、主题、建树、事件、绑定、动画队列、DOM API、`refresh`、`inspect_tree` |
| `theme.py` | `Theme` + `qss()` |
| `animate.py` / `state.py` | 动画 / 响应式状态 |
| `cli.py` | `pawui` 命令（含 `inspect`、`SCHEMA`） |

## 改动的硬规矩

改代码前请先读 `MAINTAINER_PROMPT.md` 的「API 不变式 / 坑」两节。几条最容易踩的：

- **字号属性是 `size`**（`font_size` 只做兼容）。
- **事件是「函数名字符串」**：`on_click` / `on_change` / `on_enter`，函数定义在 `<script>` 里。
- **值只支持 `{$x}` / `{x}` / `$x`** 加属性/下标路径（`{$item.name}`、`{$items[0]}`），**没有任意表达式**，计算逻辑放 `<script>`。
- **改/加属性 → 同步 `AI_PROMPT.md` + `README.md`**，并保持向后兼容。
- **新增组件** → 加进 `widgets.py` 的 `EXTRA_BUILTINS` **和** `cli.py` 的 `SCHEMA`，
  再写 `docs/<id>.md` + `docs/zh/<id>.md`，并在站点仓库 `build.py` 的 `GROUPS` 里注册 id。

### 几个真实踩过的坑（写进这里省得再犯）

- 用户 `<Style>` 规则是**追加**到控件自身样式表后面的，**后者胜**。
  `#id` > `.class` > tag 由 Qt 特异性决定。
- 控件 `setStyleSheet` 会**压过** app 样式表 —— 所以 `QPushButton` 的规则不要放进 `theme.qss()`。
- **`QPlainTextEdit.setPlainText()` 即使内容没变也会发 `textChanged`**（先 clear 再 insert）。
  任何「state → 回填控件」的回调都必须用 `_suppress` 把回声压住，否则会成环卡死。
  其它控件（`QComboBox` / `QSlider` / `QLineEdit` …）的 setter 是幂等的，值相同时不发信号，
  **不要**照搬这个担忧去改它们。
- Qt 的 `border-radius` **不会**像 CSS 那样夹到半高：胶囊按 `min-height:34px; border-radius:17px` 写。
- `QT_QPA_PLATFORM=offscreen` **没有** CJK 字体。

## 文档

- 中英各一份：`docs/<id>.md` 与 `docs/zh/<id>.md`。
- `pawui help` 的正文优先取线上（`pawui.pages.dev/static/data.js`），离线才回落随包 `docs/`。
- 站点由仓库外的 `PawUI-Site` 构建，`python tools/release.py site` 会把 `docs/` 同步过去并重建 `data.js`。
- **新文档记得在站点 `build.py` 的 `GROUPS` 里注册**，否则线上站和 `pawui help` 都看不到。

## 提 issue 的姿势

这个仓库不欢迎「刷单子」。提之前请务必：

1. **跑一遍最小复现**，把命令和输出贴上，而不是只写一段推测的调用链。
2. **核实行号与数值**（源码会变，行号会漂）。
3. **先搜已有 issue**，重复的请合并讨论。
4. **把范围讲准**：一个组件的问题不要外推到「所有组件都有」。
5. 能给出**建议 diff** 最好；只写「建议改法」但不验证，会误导后来的人。

## 发版（维护者）

凭据放仓库外：`~/.pypirc` 存 PyPI 令牌，`~/.pawui/secrets.env` 存 `GITHUB_TOKEN` / `SITE_REPO`。

```bash
python tools/release.py build     # 清 dist + build + twine check
python tools/release.py upload    # 上传 PyPI（读 ~/.pypirc，已存在版本自动跳过）
python tools/release.py publish   # 打 tag + push + 建 GitHub Release
python tools/release.py site      # docs 同步到站点 + 重建 data.js + 推送
python tools/release.py all       # build → upload → publish
```

发版前先确认：`pyproject.toml` / `pawui/__init__.py` 版本一致、`CHANGELOG.md` 有对应段落、
`tag`（`v<version>`）与版本号一致 —— `python tools/release_check.py` 一次全查。
