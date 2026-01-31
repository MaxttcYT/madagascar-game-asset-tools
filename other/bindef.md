# BinDef Viewer VS Code Extension

A **powerful VS Code extension** for viewing and inspecting Hex data from files by parsing them with **BinDef files**.  
It provides **syntax highlighting, semantic tokens, autocompletion, linting, folding, and an interactive hex + structure viewer**.

---

## Features

- **Syntax Highlighting**
- **Autocompletion**
  - Base types: `uint8`, `uint16`, `uint32`, `uint64`, `int8`, `int16`, `int32`, `int64`, `float32`, `float64`, `color32`, `string`
  - User-defined types are dynamically collected from the document
  - Snippets for `#for` loops
- **Folding**
  - Supports sections starting with `-- SectionName`
  - Collapsible regions for long BinDef structures
- **Linting**
  - Warns about undefined base types or variable types
  - Updates in real-time on document changes
- **Interactive Webview Viewer**
  - Hex view with color-coded sections
  - Clickable BinDef structure lines
  - Section legend for fast navigation
  - Cursor-based **data inspector**
  - Supports custom types and array expansions
- **Keyboard Shortcuts**
  - `←` / `→`: Move cursor by 1 byte
  - `↑` / `↓`: Move cursor by 16 bytes
  - `Shift + ← / →`: Jump between loop iterations
  - `PgUp` / `PgDn`: Move cursor by 128 bytes
  - `Ctrl + Home / End`: Jump to start/end of file

---

## Language Specification

### **Base Types**
| Type      | Size (bytes) | Notes |
|-----------|-------------|-------|
| uint8     | 1           | Unsigned 8-bit integer |
| int8      | 1           | Signed 8-bit integer |
| uint16    | 2           | Unsigned 16-bit integer, little-endian |
| int16     | 2           | Signed 16-bit integer, little-endian |
| uint32    | 4           | Unsigned 32-bit integer, little-endian |
| int32     | 4           | Signed 32-bit integer, little-endian |
| uint64    | 8           | Unsigned 64-bit integer, little-endian |
| int64     | 8           | Signed 64-bit integer, little-endian |
| float32   | 4           | 32-bit IEEE floating point |
| float64   | 8           | 64-bit IEEE floating point |
| color32   | 4           | RGBA 32-bit color (displayed as `#AARRGGBB` and rgba) |
| string    | variable    | Null-terminated or handled by context |

### **Custom Types**
```text
#type <BaseType>[ArraySize] <NewTypeName>
```

#### Example
```text
#type uint32[3] MyVector
```

#### Can be used as a variable type in the document:
```text
MyVector position;
```

### Variables
```text
<Type>[ArraySize] <VariableName>;
```

#### Example
```text
uint8[4] colorData;
float32 speed;
```

### Loops
```text
#for (loopVariable)
    <Type> <variable>;
#endfor
```

loopVariable must be defined earlier and integer-based.
Expands variable definitions in sequence, supports nested loops.

### Sections
Sections start with -- SectionName

Automatically folded and color-coded in the viewer

### Keyboard shortcuts in viewer

| Shortcut              | Action                       |
| --------------------- | ---------------------------- |
| `←` / `→`             | Move cursor by 1 byte        |
| `↑` / `↓`             | Move cursor by 16 bytes      |
| `Shift + ← / →`       | Jump between loop iterations |
| `PgUp` / `PgDn`       | Move cursor by 128 bytes     |
| `Ctrl + Home` / `End` | Jump to start/end of file    |
