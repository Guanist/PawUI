# PawUI — maintainer context

Declarative UI: HTML-like `.paw` → PySide6/Qt. Product goal: **AI-authored UIs** → stable + guessable prop names, small vocabulary, precise errors.

## Map
`parser.py` HTML scanner → `Program` (tags, attrs, self-close, `<script>` raw, `<Component>`, `<Theme>/<Color>`, `<Style>` hoisting) · `nodes.py` AST · `resolve.py` value/template/handler resolution (**no GUI imports**) · `components.py` core Qt widgets + `BUILTINS` + `ToggleSwitch` + `FlowLayout` · `widgets.py` second batch (Table / VirtualList / Canvas / Markdown / Panels / form fields) and the merged `BUILTINS` the runtime imports · `style.py` CSS3→QSS compiler + cascade engine + `var()` · `dom.py` `Element` / `Event` for scripting · `runtime.py` QApplication, theme resolve, build, events, bindings, animation queue, DOM API, `refresh`, `inspect_tree` · `theme.py` `Theme` + `qss()` · `animate.py` · `state.py` · `cli.py` (incl. `pawui inspect`) · `app.paw` demo · `AI_PROMPT.md` tracks the public API.

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
- New component ⇒ add it to `widgets.py` `EXTRA_BUILTINS` **and** `cli.py` `SCHEMA`, then write `docs/<id>.md` + `docs/zh/<id>.md` and register the id in the site repo's `build.py` `GROUPS`.
- CSS: user rules are appended to the widget's own stylesheet (later wins). `#id` > `.class` > tag by Qt specificity. Anything QSS cannot express (`var()`, text props, bare-number units) is handled **before** Qt sees it — `style.py`, not the widgets.
- Runtime CSS injection must stay idempotent (`inject_css` dedupes) and land after `<Style>`, otherwise live restyles regress.

## Gotchas
- No tkinter. Ever. Tk was fully replaced (corners/AA/CJK/IME all failed there).
- Widget `setStyleSheet` beats app stylesheet ⇒ keep `QPushButton` rules out of `theme.qss()`; per-button styles live in `components.py` (otherwise they fight and corners break).
- Qt `border-radius` does **not** clamp to half-height like CSS ⇒ pill = `min-height:34px; border-radius:17px`.
- Never leave `windowOpacity` mid-animation (window goes translucent). If you animate it, end at 1.0 and hold a reference.
- `QT_QPA_PLATFORM=offscreen` has no CJK font ⇒ `□□` is a preview artifact, not a bug. Visual check = real platform `root.grab()`, window `move(-4000,-4000)` first.
- `QApplication.instance() or QApplication([])`.
- Theme switch rebuilds via `QTimer.singleShot(0, refresh)` — colors are mostly per-widget inline styles.
- `<script>` is raw-captured; no `</script>` inside.
- Event filters must be parented to the widget they watch. A process-wide filter on `QApplication` crashes when a widget is destroyed mid-callback, and a Runtime-owned filter dies with the Runtime while Qt still holds the pointer.
- `_ElidedLabel` overrides `text()`/`setText()`: never re-render on resize unless eliding or line-height is on (1000-row lists get O(n) relayout storms otherwise).
- Clicks dispatch once: mouse goes through the event filter (deepest child, then bubbles up), keyboard/`.click()` goes through the `clicked` signal; `_mouse_clicked` keeps them from double-firing.

## Verify
`pawui app.paw` · offscreen smoke build · real-platform grab for any visual change · `pawui inspect app.paw` when a style rule does not land · keep `AI_PROMPT.md` in sync · `QT_QPA_PLATFORM=offscreen python -m pytest -q` + `ruff check .` + `mypy pawui`.

## Gaps
`pawui render -o png` · slots · `<For>` on very large lists should push people to `<VirtualList>` (documented, 100k rows ≈ 139ms) · full CommonMark (currently a small subset; `<Web html=...>` is the escape hatch) · no built-in chart widget (use `<Canvas>`).
