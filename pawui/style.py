"""PawUI 样式引擎：把 ``.paw`` 里的 CSS 编译成 Qt 能吃的 QSS。

Qt 的样式表是 CSS 的子集，而且有两处硬限制：

1. **没有自定义 class 选择器**：``.card`` 在 Qt 里表示「类名叫 card 的 C++ 类」，
   永远不会命中。所以自定义 class 必须靠动态属性 + 属性选择器实现。
2. **组件 tag 不是 C++ 类名**：``Button`` 要映射到 ``QPushButton``，
   自定义组件（``<Card>``）没有任何 Qt 类可用，只能靠属性选择器。

因此这里把作者写的类 CSS3 选择器重写成 Qt 支持的形式：

==============  ====================================
作者写法        Qt 实际收到
==============  ====================================
``Button``      ``QPushButton``
``Card``        ``[pw-tag="Card"]``
``.card``       ``[pw-class~="card"]``
``#submit``     ``#submit``（objectName，Qt 原生支持）
``Button:hover````QPushButton:hover``
==============  ====================================

后代 / 子代组合器、逗号分组、伪状态原样保留。同时把 PawUI 的简写属性
（``radius`` / ``bg`` / ``fg``）翻译成标准 CSS 属性名。
"""

from __future__ import annotations

import re
from typing import Any

# .paw 里的内置 tag -> Qt 类名
TAG_TO_QT = {
    "Window": "QWidget",
    "Column": "QWidget",
    "Row": "QWidget",
    "Grid": "QWidget",
    "Text": "QLabel",
    "Button": "QPushButton",
    "Input": "QLineEdit",
    "Checkbox": "QWidget",
    "Divider": "QFrame",
    "Spacer": "QWidget",
    "Slider": "QSlider",
    "Progress": "QProgressBar",
    "Select": "QComboBox",
    "Dialog": "QWidget",
    "Menu": "QToolButton",
    "Form": "QWidget",
    "Tabs": "QTabWidget",
    "Image": "QLabel",
    "Tooltip": "QWidget",
    "TextArea": "QPlainTextEdit",
    "Scroll": "QScrollArea",
    "Web": "QWebEngineView",
}

# PawUI 简写属性 -> 标准 CSS 属性
PROPERTY_ALIASES = {
    "radius": "border-radius",
    "bg": "background-color",
    "fg": "color",
}

# 不属于 QSS、需要运行时施加到控件上的文本属性
TEXT_PROPERTIES = ("wrap", "ellipsis", "align", "selectable", "line-height")

# 这些属性的裸数字要补 `px`，不然 Qt 会当无效值直接丢掉（CSS 里可以不写单位）
_LENGTH_PROPERTIES = frozenset({
    "border-radius", "border-width", "padding", "margin", "width", "height",
    "min-width", "min-height", "max-width", "max-height", "font-size",
    "letter-spacing", "word-spacing", "gap", "spacing", "outline-width",
    "top", "right", "bottom", "left", "indent",
})
_LENGTH_SHORTHANDS = frozenset({"border", "border-left", "border-right",
                                "border-top", "border-bottom", "outline"})
_BARE_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _with_units(name: str, value: str) -> str:
    """给裸数字补 `px`（只对长度类属性生效）。"""
    if name in _LENGTH_PROPERTIES:
        tokens = value.split()
        if tokens and all(_BARE_NUMBER_RE.match(t) for t in tokens):
            return " ".join(f"{t}px" for t in tokens)
        return value
    if name in _LENGTH_SHORTHANDS:
        return re.sub(r"(?<![\w.%])(-?\d+(?:\.\d+)?)(?![\w.%])", r"\1px", value)
    return value


def normalize_value(name: str, value: str) -> str:
    """公开的裸数字补单位工具（组件层拼 QSS 时会用）。"""
    return _with_units(name.strip().lower(), value.strip())

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_TYPE_RE = re.compile(r"[A-Za-z][\w-]*")
_VAR_RE = re.compile(r"var\(\s*--([\w-]+)\s*(?:,\s*([^()]*?)\s*)?\)")


def theme_variables(theme: Any) -> dict[str, str]:
    """把主题令牌变成 CSS 变量，让 ``var(--accent)`` 在 QSS 里真的能用。

    Qt 的样式表**不支持** ``var()``，所以这些变量是在编译期被替换掉的，
    不是运行时求值 —— 对用户来说写法是 CSS，实现是编译。
    """
    out: dict[str, str] = {}
    for name, value in theme.to_dict().items():
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            out[f"--{name}"] = str(value)
    # 常用别名，写 CSS 时少打几个字
    if "--background" in out:
        out.setdefault("--bg", out["--background"])
    if "--text" in out:
        out.setdefault("--fg", out["--text"])
    out.setdefault("--bg", theme.background)
    out.setdefault("--fg", theme.text)
    out.setdefault("--radius", str(theme.radius))
    out.setdefault("--accent", theme.accent)
    for name, value in getattr(theme, "custom", {}).items():
        out[f"--{name}"] = value
    return out


def resolve_vars(text: str, variables: dict[str, str], on_missing: Any = None) -> str:
    """把 ``var(--x)`` / ``var(--x, 兜底)`` 替换成实际值。"""
    if "var(" not in text:
        return text

    def repl(match: re.Match[str]) -> str:
        name = f"--{match.group(1)}"
        fallback = (match.group(2) or "").strip()
        if name in variables:
            return variables[name]
        if fallback:
            return fallback
        if on_missing is not None:
            on_missing(name[2:])  # 记名字时不带 `--`，报错信息更好读
        return match.group(0)

    return _VAR_RE.sub(repl, text)


def collect_variables(css_text: str) -> dict[str, str]:
    """收集样式里的 ``--x: value;`` 自定义变量定义。"""
    out: dict[str, str] = {}
    body = _COMMENT_RE.sub("", css_text or "")
    # 必须先按 `}` 切成规则块再找声明，否则 `:root {` 这类前缀会被并进变量名里。
    for block in _split_top_level(body, "}"):
        if "{" not in block:
            continue
        _selector, _, decl_text = block.partition("{")
        for decl in _split_top_level(decl_text, ";"):
            if ":" not in decl:
                continue
            name, _, value = decl.partition(":")
            name = name.strip()
            value = value.strip()
            if name.startswith("--"):
                out[name] = value
    return out


def _split_top_level(text: str, sep: str) -> list[str]:
    """按分隔符切分，忽略括号与引号里的分隔符。"""
    out: list[str] = []
    depth = 0
    quote = ""
    buf: list[str] = []
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    return out


def _read_balanced(token: str, i: int) -> int:
    """从 ``token[i]``（``[`` 或 ``(``）读到配对的收尾字符，返回其后一位。"""
    opener = token[i]
    closer = "]" if opener == "[" else ")"
    depth = 0
    quote = ""
    j = i
    while j < len(token):
        ch = token[j]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(token)


def _rewrite_simple_selector(token: str, custom_tags: set[str]) -> str:
    """重写**一个复合选择器**（不含组合器）。

    要处理 ``.card.primary`` 这种多 class 复合写法：每个 class 都要变成一个属性
    选择器，不能只认最前面那个点。``#id`` / ``[attr]`` / ``:pseudo`` 原样保留，
    开头的类型选择器按 tag 表替换。
    """
    token = token.strip()
    if not token:
        return token

    out: list[str] = []
    i = 0
    n = len(token)
    while i < n:
        ch = token[i]
        if ch == "#":
            j = i + 1
            while j < n and (token[j].isalnum() or token[j] in "_-"):
                j += 1
            out.append(token[i:j] or "#")
            i = max(j, i + 1)
        elif ch == ".":
            j = i + 1
            while j < n and (token[j].isalnum() or token[j] in "_-"):
                j += 1
            name = token[i + 1:j]
            out.append(f'[pw-class~="{name}"]' if name else "")
            i = max(j, i + 1)
        elif ch in "[":
            j = _read_balanced(token, i)
            out.append(token[i:j])
            i = j
        elif ch == ":":
            j = i + 1
            while j < n and (token[j].isalnum() or token[j] in "_-"):
                j += 1
            if j < n and token[j] == "(":
                j = _read_balanced(token, j)
            out.append(token[i:j] or ":")
            i = max(j, i + 1)
        elif ch == "*":
            out.append("*")
            i += 1
        else:
            match = _TYPE_RE.match(token, i)
            if not match:
                out.append(token[i])
                i += 1
                continue
            name = match.group(0)
            i = match.end()
            if name in TAG_TO_QT:
                out.append(TAG_TO_QT[name])
            elif name in custom_tags:
                out.append(f'[pw-tag="{name}"]')
            else:
                out.append(name)
    return "".join(out) or token


def _normalize_combinators(text: str) -> str:
    """规范组合器两侧空格；属性选择器里的 ``~=`` / ``*=`` 不能被动到。"""
    out: list[str] = []
    depth = 0
    quote = ""
    for ch in text:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if depth > 0:
            out.append(ch)
            continue
        if ch in ">+~":
            while out and out[-1] == " ":
                out.pop()
            out.extend([" ", ch, " "])
            continue
        if ch == " " and out and out[-1] == " ":
            continue
        out.append(ch)
    return "".join(out).strip()


def _rewrite_selector(selector: str, custom_tags: set[str]) -> str:
    """重写一个完整选择器（可能带后代 / 子代组合器）。"""
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    for ch in selector:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in " \t\n>+~":
            if buf:
                out.append(_rewrite_simple_selector("".join(buf), custom_tags))
                buf = []
            out.append(ch if ch in ">+~" else " ")
            continue
        buf.append(ch)
    if buf:
        out.append(_rewrite_simple_selector("".join(buf), custom_tags))

    return _normalize_combinators("".join(out))


def _translate_declarations(body: str) -> str:
    """把 PawUI 简写属性名换成标准 CSS 属性名，并规范 `;` 分隔。"""
    parts = [p for p in _split_top_level(body, ";") if p.strip()]
    out: list[str] = []
    for part in parts:
        if ":" not in part:
            continue
        name, _, value = part.partition(":")
        key = name.strip().lower()
        key = PROPERTY_ALIASES.get(key, key)
        out.append(f"{key}: {value.strip()}")
    return "; ".join(out)


def normalize_units(decls: str) -> str:
    """给长度属性的裸数字补 `px`。

    必须在 ``var()`` 替换**之后**跑 —— ``var(--radius)`` 编译前看不出是个长度。
    """
    out: list[str] = []
    for part in _split_top_level(decls, ";"):
        if ":" not in part:
            continue
        name, _, value = part.partition(":")
        key = name.strip().lower()
        if not key:
            continue
        out.append(f"{key}: {_with_units(key, value.strip())}")
    return "; ".join(out)


def compile_css(text: str, custom_tags: set[str] | None = None) -> str:
    """把一段（类 CSS3 的）样式文本编译成 Qt 可用的 QSS。"""
    if not text or not text.strip():
        return ""
    custom_tags = set(custom_tags or ())
    body = _COMMENT_RE.sub("", text)
    rules: list[str] = []
    for block in _split_top_level(body, "}"):
        if "{" not in block:
            continue
        selector_text, _, decl_text = block.partition("{")
        selector_text = selector_text.strip()
        if not selector_text:
            continue
        decls = normalize_units(_translate_declarations(decl_text))
        if not decls:
            continue
        rewritten = [
            _rewrite_selector(sel, custom_tags)
            for sel in _split_top_level(selector_text, ",")
            if sel.strip()
        ]
        rewritten = [sel for sel in rewritten if sel]
        if rewritten:
            rules.append(f"{', '.join(rewritten)} {{ {decls}; }}")
    return "\n".join(rules)


def parse_declarations(text: str) -> dict[str, str]:
    """把一段声明块解析成字典（用于读取运行时文本属性）。"""
    out: dict[str, str] = {}
    for part in _split_top_level(text, ";"):
        if ":" not in part:
            continue
        name, _, value = part.partition(":")
        out[name.strip().lower()] = value.strip()
    return out


def text_props_from_css(text: str) -> dict[str, dict[str, str]]:
    """从样式文本里抽出「按选择器分组的文本属性」。

    QSS 不认识 ``wrap`` / ``ellipsis`` / ``align`` / ``selectable`` / ``line-height``，
    这些得由运行时施加到具体控件上，所以单独抽出来。
    """
    if not text or not text.strip():
        return {}
    body = _COMMENT_RE.sub("", text)
    out: dict[str, dict[str, str]] = {}
    for block in _split_top_level(body, "}"):
        if "{" not in block:
            continue
        selector_text, _, decl_text = block.partition("{")
        decls = {k: v for k, v in parse_declarations(decl_text).items() if k in TEXT_PROPERTIES}
        if decls and selector_text.strip():
            out[selector_text.strip()] = decls
    return out


def truthy(value: Any) -> bool:
    """样式值里的布尔判断：``wrap: true`` / ``wrap: 1`` / ``wrap: yes`` 都算真。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


# ---------------------------------------------------------------- 级联引擎

_ATTR_RE = re.compile(r"\[\s*([\w-]+)\s*(?:([~^$*|]?=)\s*\"?([^\"]*?)\"?)?\s*\]")
_ID_RE = re.compile(r"#([\w-]+)")
_PSEUDO_RE = re.compile(r"::?[\w-]+(?:\([^)]*\))?")


def _split_compounds(selector: str) -> list[tuple[str, str]]:
    """把选择器拆成 ``[(组合器, 复合选择器), ...]``，第一个组合器为空串。"""
    parts: list[tuple[str, str]] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    pending = ""
    for ch in selector:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if depth == 0 and ch in " >+~":
            if buf:
                parts.append((pending, "".join(buf).strip()))
                buf = []
                pending = "descendant" if ch == " " else ch
            continue
        buf.append(ch)
    if buf:
        parts.append((pending, "".join(buf).strip()))
    return [(comb, comp) for comb, comp in parts if comp]


def _match_compound(compound: str, widget: Any) -> bool:
    """判断一个复合选择器是否命中控件。

    只认结构（类型 / #id / [属性]），伪状态交给 Qt 自己处理 —— 因此匹配前先把
    ``:hover`` 这类去掉，命中之后再把带伪状态的原文整条写进控件样式表。
    """
    structural = _PSEUDO_RE.sub("", compound)
    if not structural:
        return True

    head_type = ""
    m = re.match(r"[A-Za-z][\w]*", structural)
    if m:
        head_type = m.group(0)
        structural = structural[m.end():]

    if head_type and head_type != "*":
        # 用 MRO 而不是 __name__：组件内部可能用 QLabel 的子类实现，
        # 但作者写的选择器是 Text -> QLabel，必须照样命中。
        if head_type not in {cls.__name__ for cls in type(widget).__mro__}:
            return False

    obj_id = widget.objectName() or ""
    for name in _ID_RE.findall(structural):
        if obj_id != name:
            return False

    for name, op, value in _ATTR_RE.findall(structural):
        actual = widget.property(name)
        actual_s = "" if actual is None else str(actual)
        if op == "":
            if not actual_s:
                return False
        elif op == "~=":
            if value not in actual_s.split():
                return False
        elif op == "=":
            if actual_s != value:
                return False
        elif op == "*=":
            if value not in actual_s:
                return False
        elif op == "^=":
            if not actual_s.startswith(value):
                return False
        elif op == "$=":
            if not actual_s.endswith(value):
                return False
    return True


def _matches(parts: list[tuple[str, str]], widget: Any) -> bool:
    """从右往左匹配复合选择器链，处理后代与子代组合器。"""
    if not parts:
        return False
    combinator, compound = parts[-1]
    if not _match_compound(compound, widget):
        return False
    rest = parts[:-1]
    if not rest:
        return True

    if combinator == ">":
        parent = widget.parentWidget()
        while parent is not None and not parent.isWindow():
            if _matches(rest, parent):
                return True
            break
        return False

    # 后代 / 相邻兄弟：逐级往上找
    node = widget.parentWidget()
    while node is not None:
        if _matches(rest, node):
            return True
        node = node.parentWidget()
    return False


def selector_matches(widget: Any, selector: str, custom_tags: set[str] | None = None) -> bool:
    """控件是否被这个 CSS 选择器命中（支持逗号分组、后代/子代组合器、伪状态）。

    ``app.query(".card Button")`` 这类脚本侧查询和 ``<Style>`` 走的是同一套匹配，
    所以「CSS 里命中的」和「脚本里查到的」是一致的。
    """
    if not selector or widget is None:
        return False
    tags = set(custom_tags or ())
    for raw in _split_top_level(selector, ","):
        raw = raw.strip()
        if not raw:
            continue
        parts = _split_compounds(_rewrite_selector(raw, tags))
        if parts and _matches(parts, widget):
            return True
    return False


class StyleEngine:
    """把用户 ``<Style>`` 文本按控件做选择器匹配，产出该控件该追加的 QSS。

    为什么不用「全局样式表 + 去掉内联样式」那条路：组件默认样式是按实例属性算出来
    的（``bg="surface"`` 之类），塞不进类型规则；而 Qt 里控件自己的样式表优先级
    高于全局表。所以这里的策略是 —— 匹配到的用户规则**追加到控件自己的样式表末尾**，
    同一张表里后写的胜出；``#id`` / ``.class`` 还会按 CSS 特异度压过默认的类型规则。
    于是级联顺序是：用户 CSS > 组件默认样式 > 主题基线。
    """

    def __init__(self, css_text: str, custom_tags: set[str] | None = None,
                 variables: dict[str, str] | None = None):
        self.raw = css_text or ""
        self.rules: list[tuple[str, str, str]] = []  # (原始选择器, 编译后, 声明)
        self._compiled: list[dict[str, Any]] = []  # 预解析好的规则（匹配时就靠它）
        self.custom_tags = set(custom_tags or ())
        # 主题令牌 + 用户自己声明的 --x，编译期替换进声明里
        self.variables = dict(variables or {})
        self.variables.update(collect_variables(self.raw))
        self.missing_vars: set[str] = set()
        self._compile()

    def _resolve(self, decls: str) -> str:
        return resolve_vars(decls, self.variables, on_missing=self.missing_vars.add)

    def _compile(self) -> None:
        """把用户样式编译成「已算好」的规则表。

        每条规则在这里就把声明解析、文本属性拆分、选择器的复合段切好，
        控件匹配时只做匹配本身 —— 1000 个控件就是 1000 次匹配，
        而不是 1000 × 规则数 次重新解析字符串。
        """
        if not self.raw.strip():
            return
        body = _COMMENT_RE.sub("", self.raw)
        for block in _split_top_level(body, "}"):
            if "{" not in block:
                continue
            selector_text, _, decl_text = block.partition("{")
            decls = normalize_units(self._resolve(_translate_declarations(decl_text)))
            if not decls:
                continue
            if selector_text.strip() in (":root", "html", "*"):
                continue  # 只是变量声明块，不产生规则
            parsed = parse_declarations(decls)
            qss_body = "; ".join(
                f"{k}: {v}" for k, v in parsed.items() if k not in TEXT_PROPERTIES
            )
            text_body = {k: v for k, v in parsed.items() if k in TEXT_PROPERTIES}
            for sel in _split_top_level(selector_text, ","):
                sel = sel.strip()
                if not sel:
                    continue
                compiled = _rewrite_selector(sel, self.custom_tags)
                if compiled:
                    self.rules.append((sel, compiled, decls))
                    self._compiled.append({
                        "selector": sel,
                        "compiled": compiled,
                        "qss": f"{compiled} {{ {qss_body}; }}" if qss_body else "",
                        "text": text_body,
                        "parts": _split_compounds(compiled),
                    })

    def _text_rules(self) -> list[tuple[str, str, dict[str, str]]]:
        return [
            (sel, compiled, {k: v for k, v in parse_declarations(decls).items()
                             if k in TEXT_PROPERTIES})
            for sel, compiled, decls in self.rules
        ]

    def css_for(self, widget: Any) -> str:
        """返回该控件应当追加到自身样式表的 QSS 片段。"""
        return self.apply(widget)[0]

    def matched_selectors(self, widget: Any) -> list[str]:
        """这个控件命中了哪些选择器（``pawui inspect`` 用它解释级联）。"""
        out: list[str] = []
        for sel, compiled, _decls in self.rules:
            parts = _split_compounds(compiled)
            if parts and _matches(parts, widget):
                out.append(sel)
        return out

    def text_props_for(self, widget: Any) -> dict[str, str]:
        """返回该控件命中的文本属性（wrap / ellipsis / align / selectable / line-height）。

        多条规则命中时按书写顺序覆盖，后面的赢。
        """
        return self.apply(widget)[1]

    def apply(self, widget: Any) -> tuple[str, dict[str, str]]:
        """一遍扫描同时算出「要追加的 QSS」和「命中的文本属性」。

        以前这两个是两次独立遍历，每个控件要把规则表走两遍。
        """
        qss: list[str] = []
        props: dict[str, str] = {}
        for rule in self._compiled:
            parts = rule["parts"]
            if not parts or not _matches(parts, widget):
                continue
            body = rule["qss"]
            if body:
                qss.append(body)
            if rule["text"]:
                props.update(rule["text"])
        return "\n".join(qss), props
