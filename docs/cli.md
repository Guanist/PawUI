# CLI Reference

## Commands

```bash
pawui <file.paw>           # Run a .paw file
pawui run <file.paw>       # Explicit run command
pawui check <file.paw>     # Syntax check only (no rendering)
pawui schema               # Print component JSON Schema
pawui render <file.paw>    # Offscreen render self-check
pawui --version            # Print version
pawui --help               # Show help
```

## Running Files

```bash
# Direct
pawui app.paw

# With path
pawui ./ui/main.paw
pawui /absolute/path/app.paw
```

## Python API

```python
import pawui

# Blocking run
pawui.run("app.paw")

# With context
pawui.run("app.paw", context={"api_key": "secret"}, theme="light")
```

For a non-blocking runtime instance, use `Runtime` directly:

```python
from pawui.runtime import Runtime

rt = Runtime(source, context=context)
rt.run(block=False)   # returns the root QWidget
rt.app.exec()         # start the event loop manually
```

## Runtime Methods

```python
rt = pawui.run("app.paw", block=False)

# Theme switching
rt.set_theme("light")
rt.set_theme(Theme.light())

# Force rebuild
rt.refresh()

# Access state
rt.state.count = 42

# Call handlers
rt.invoke(handler_fn, arg1, arg2)

# Get root widget
window = rt.root
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (parse, runtime, file not found) |
| 2 | Usage error |
| 130 | Keyboard interrupt (Ctrl+C) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `QT_QPA_PLATFORM` | Qt platform (e.g., `offscreen` for CI) |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | Enable auto scaling |
| `QT_SCALE_FACTOR` | Manual scale factor |

## Offscreen Rendering (CI)

```bash
QT_QPA_PLATFORM=offscreen pawui app.paw
```

Note: Offscreen has no CJK font - text may show as □□. This is a preview artifact, not a bug.