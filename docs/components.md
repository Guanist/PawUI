# Components Reference

## Window

Root element (exactly one per file).

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | string | "PawUI" | Window title |
| `width` | int | 480 | Initial width |
| `height` | int | 640 | Initial height |
| `theme` | "dark" \| "light" | "dark" | Base theme |
| `padding` | int | 0 | Window padding |
| `spacing` | int | theme.spacing | Child spacing |

```html
<Window title="My App" width="800" height="600" theme="dark" padding="24" spacing="16">
  <!-- content -->
</Window>
```

## Column / Row

Container layouts.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `padding` | int \| tuple | theme.padding | Inner padding |
| `spacing` | int | theme.spacing | Child gap |
| `bg` | color | - | Background color |
| `radius` | int | theme.radius | Border radius |
| `expand` | bool | false | Expand to fill |
| `stagger` | int | 0 | Child animation delay increment |

```html
<Column padding="20" spacing="12" bg="surface" radius="12" stagger="60">
  <Text>Item 1</Text>
  <Text>Item 2</Text>
</Column>

<Row spacing="8">
  <Button>Left</Button>
  <Spacer width="10"/>
  <Button>Right</Button>
</Row>
```

## Text

Display text content.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `size` | int | theme.font_size | Font size (px) |
| `bold` | bool | false | Bold weight |
| `italic` | bool | false | Italic style |
| `color` | color | theme.text | Text color |
| `fg` | color | theme.text | Alias for color |

```html
<Text size="24" bold="true" color="accent">Title</Text>
<Text size="14" color="subtext">{$description}</Text>
<!-- Content between tags -->
<Text>Static text</Text>
```

## Button

Clickable button.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `on_click` | string | - | Handler function name |
| `bg` | color | theme.accent | Background color |
| `fg` | color | theme.background | Text color |
| `size` | int | theme.font_size | Font size |
| `radius` | int | 17 | Border radius |
| `disabled` | bool | false | Disable button |

```html
<Button on_click="submit" bg="accent" fg="background">Submit</Button>
<Button on_click="cancel" bg="surface" fg="text" disabled="true">Cancel</Button>
```

## Input

Text input field.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `placeholder` | string | "" | Placeholder text |
| `value` | string | "" | Initial value (bindable) |
| `on_change` | string | - | Handler(text) |
| `on_enter` | string | - | Handler(text) on Enter |
| `size` | int | 14 | Font size |
| `show` | string | "" | Set to "password" for masked |

```html
<Input placeholder="Name" on_change="on_name" value="{$name}"/>
<Input placeholder="Password" show="password" on_enter="login"/>
```

## Checkbox (Toggle Switch)

iOS-style toggle switch.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `checked` | bool | false | Initial state |
| `on_change` | string | - | Handler(checked) |
| `size` | int | theme.font_size | Label font size |

```html
<Checkbox checked="true" on_change="on_toggle">Enable feature</Checkbox>
```

## Divider

Horizontal line.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `color` | color | theme.border | Line color |
| `thickness` | int | 2 | Line height (px) |

```html
<Divider color="border" thickness="1"/>
```

## Spacer

Empty space.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `width` | int | 1 | Width (px) |
| `height` | int | 1 | Height (px) |

```html
<Spacer height="20"/>
<Spacer width="10"/>  <!-- In Row -->
```

## Animation Props (All Elements)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `animate` | string | - | "fade" \| "reveal" \| "slide-up" \| "slide-down" \| "slide-left" \| "slide-right" |
| `duration` | int | 260 | Animation duration (ms) |
| `delay` | int | 0 | Initial delay (ms) |
| `easing` | string | "out-cubic" | Easing curve |

```html
<Text animate="slide-up" duration="400" delay="100" easing="out-back">Animated</Text>
```