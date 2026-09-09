# API Reference

## Core Classes

### `pawui.Runtime`

Main runtime class.

```python
class Runtime:
    def __init__(self, source: str, filename: str = "<memory>", 
                 context: dict | None = None, theme: str = "dark")
    
    def run(self, block: bool = True) -> QWidget
    def set_theme(self, name_or_theme: str | Theme) -> None
    def refresh(self) -> None
    def invoke(self, handler: Any, *args: Any) -> Any
    def queue_animation(self, widget: QWidget, kind: str, 
                        duration: int, delay: int, curve: str) -> None
```

### `pawui.State`

Reactive state container.

```python
class State:
    def __init__(self, initial: dict[str, Any] | None = None)
    
    def get(self, key: str, default: Any = "") -> Any
    def set(self, key: str, value: Any) -> None
    def has(self, key: str) -> bool
    def watch(self, key: str, fn: Callable[[Any], None]) -> Callable[[], None]
    def keys(self) -> list[str]
    def snapshot(self) -> dict[str, Any]
    
    # Attribute access
    def __getattr__(self, key: str) -> Any
    def __setattr__(self, key: str, value: Any) -> None
    def __getitem__(self, key: str) -> Any
    def __setitem__(self, key: str, value: Any) -> None
    def __contains__(self, key: str) -> bool
```

### `pawui.Theme`

Theme configuration.

```python
class Theme:
    background: str
    surface: str
    text: str
    subtext: str
    accent: str
    border: str
    danger: str
    spacing: int
    padding: int
    radius: int
    font_family: str
    font_size: int
    title_size: int
    custom: dict[str, str]
    
    @classmethod
    def light(cls) -> "Theme"
    @classmethod
    def dark(cls) -> "Theme"
    
    def override(self, **kwargs) -> "Theme"
    def color(self, name: str, default: str | None = None) -> str | None
    def apply(self, overrides: dict[str, str]) -> "Theme"
    def qss(self) -> str
    def to_dict(self) -> dict[str, Any]
```

### `pawui.parser.parse`

```python
def parse(source: str, filename: str = "<memory>") -> Program
```

### `pawui.resolve`

```python
def resolve_prop_value(value: Any, scope: dict, runtime: Runtime) -> Any
def resolve_template(template: str, scope: dict, runtime: Runtime) -> str
def resolve_handler(value: Any, scope: dict, runtime: Runtime) -> Any
def is_template(v: Any) -> bool
def collect_refs(template: str, scope: dict, runtime: Runtime) -> set[str]
```

### `pawui.animate`

```python
def entrance(widget: QWidget, kind: str, duration: int = 260, 
             delay: int = 0, curve: str = "out-cubic") -> QParallelAnimationGroup
def easing(name: str) -> QEasingCurve.Type
def is_animation(kind: str) -> bool
```

## Built-in Components

Available via `pawui.components.BUILTINS`:

- `Window`
- `Column`
- `Row`
- `Text`
- `Button`
- `Input`
- `Checkbox`
- `Divider`
- `Spacer`

## Errors

```python
class PyxError(Exception)
class ParseError(PyxError)
class ComponentError(PyxError)
class RenderError(PyxError)
class ScriptError(PyxError)
```

## AST Nodes

```python
class Element
class ScriptBlock
class Program
class ComponentDef
class Symbol
class Position
```

## Module Exports

```python
# pawui/__init__.py
__all__ = ["run", "main"]
__version__ = "0.0.3"

# pawui.cli
run(path, context=None, theme="dark") -> None
main(argv=None) -> int
```