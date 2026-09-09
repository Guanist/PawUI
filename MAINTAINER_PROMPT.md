# PawUI — maintainer context

Declarative UI: HTML-like `.paw` → PySide6/Qt. Product goal: **AI-authored UIs** → stable + guessable prop names, small vocabulary, precise errors.

## Map
`parser.py` HTML scanner → `Program` (tags, attrs, self-close, `<script>` raw, `<Component>`, `<Theme>/<Color>`) · `nodes.py` AST · `resolve.py` value/template/handler resolution (**no GUI imports**) · `components.py` Qt widgets + `BUILTINS` + `ToggleSwitch` · `runtime.py` QApplication, theme resolve, build, events, bindings, animation queue, `refresh` · `theme.py` `Theme` + `qss()` · `animate.py` · `state.py` · `cli.py` · `app.paw` demo · `AI_PROMPT.md` tracks the public API.

## Flow
`cli.run` → `Runtime` parse → `_prepare` (theme → components → script) → `_build_tree` (widgets → events/bindings → animation queue → show) → `app.exec`.

## API invariants
- Font size prop: `size` (`font_size` compat only).
- Events: `on_click` / `on_change` / `on_enter` = **function-name strings** from `<script>` or `run(context=...)`.
- Values: `{$x}` / `{x}` / `$x` with attribute/index paths (`{$item.name}`, `{$items[0]}`); no arbitrary expressions.
- Animation: `animate` + `duration`/`delay`/`easing`; containers `stagger`.
- `<Component name>` → `{$prop}` inside; `<Card label="x" value="{$count}"/>`.
- `<Theme extends="dark|light"><Color name value>`; overridable: `background surface text subtext accent border danger`; other names → `theme.custom`, usable as `color="brand"`.
- Exactly one root `<Window>`; everything else inside it.
- Rename/add a prop ⇒ update `AI_PROMPT.md` + `README.md`, keep it backward compatible.

## Gotchas
- No tkinter. Ever. Tk was fully replaced (corners/AA/CJK/IME all failed there).
- Widget `setStyleSheet` beats app stylesheet ⇒ keep `QPushButton` rules out of `theme.qss()`; per-button styles live in `components.py` (otherwise they fight and corners break).
- Qt `border-radius` does **not** clamp to half-height like CSS ⇒ pill = `min-height:34px; border-radius:17px`.
- Never leave `windowOpacity` mid-animation (window goes translucent). If you animate it, end at 1.0 and hold a reference.
- `QT_QPA_PLATFORM=offscreen` has no CJK font ⇒ `□□` is a preview artifact, not a bug. Visual check = real platform `root.grab()`, window `move(-4000,-4000)` first.
- `QApplication.instance() or QApplication([])`.
- Theme switch rebuilds via `QTimer.singleShot(0, refresh)` — colors are mostly per-widget inline styles.
- `<script>` is raw-captured; no `</script>` inside.

## Verify
`pawui app.paw` · offscreen smoke build · real-platform grab for any visual change · keep `AI_PROMPT.md` in sync.

## Gaps
tests · `pawui schema` + `pawui check` + `pawui render -o png` · `<If>/<For>` done, two-way binding, default props, slots · Slider/Progress/Tabs/Image/Tooltip, Text wrap/align/pad · hot reload, error messages, mypy/ruff, PyPI.
