# CRM Builder — UI Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/application/app-ui-patterns.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of the CRM Builder UI —
the PySide6 components, state machine, threading model, and patterns
used across all UI features. It is maintained by Claude Code and
updated as the implementation evolves.

---

## 2. Framework and Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pyside6` | >= 6.10.2 | Qt6 GUI framework |

The application uses PySide6 (Qt6). All UI components are PySide6
widgets. Background operations use `QThread` with Qt signals for
thread-safe UI updates.

---

## 3. Application Entry Point

`espo_impl/main.py` is the entry point. It:
- Initializes the required directories (`data/instances/`,
  `data/programs/`, `reports/`) if they do not exist
- Creates the `QApplication` instance
- Instantiates and shows `MainWindow`
- Starts the Qt event loop

---

## 4. Main Window (`ui/main_window.py`)

### 4.1 Layout

The main window uses a `QSplitter` or fixed layout with four regions:

```
┌─────────────────────────┐  ┌─────────────────────────────────┐
│  INSTANCE               │  │  PROGRAM FILE                   │
│  [list]                 │  │  [list]                         │
│  [+ Add] [Edit] [Delete]│  │  [+ Add] [Edit] [Delete]        │
│  ─────────────────────  │  └─────────────────────────────────┘
│  URL: _______________   │
│  Folder: ___________    │  ┌─────────────────────────────────┐
│                         │  │  [Validate] [Run] [Verify]      │
└─────────────────────────┘  │  [Gen Docs] [Import] [Report]   │
                             └─────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT                                                     │
│  [monospace scrollable text area]                           │
└─────────────────────────────────────────────────────────────┘
[Clear Output]                                    [View Report]
```

### 4.2 UIState

All UI state is captured in a single dataclass:

```python
@dataclass
class UIState:
    instance: InstanceProfile | None = None
    program_path: Path | None = None
    program: ProgramFile | None = None
    validated: bool = False
    run_complete: bool = False
    operation_in_progress: bool = False
    last_report_path: Path | None = None
```

The state is updated after every significant event and drives the
output panel feedback messages.

### 4.3 Never-Disable Button Pattern

Buttons are never disabled. Every button click handler checks
preconditions and emits a message to the output panel if they are
not met:

```python
def _on_validate_clicked(self):
    if not self.state.instance:
        self._output("Select an instance first.", "yellow")
        return
    if not self.state.program_path:
        self._output("Select a program file first.", "yellow")
        return
    if self.state.operation_in_progress:
        self._output("An operation is already in progress.", "yellow")
        return
    self._start_validate()
```

### 4.4 Instance Selection

When an instance is selected in the instance panel,
`_on_instance_selected` is called. It:
1. Updates `self.state.instance`
2. Switches the program panel to the instance's `programs_dir`
   (or `base_dir/data/programs/` as fallback)
3. Resets `validated` and `run_complete` to False

After add/edit, the instance panel explicitly emits `instance_selected`
to guarantee the main window updates even when the list selection index
has not changed (e.g., single-instance case).

### 4.5 Worker Lifecycle

Starting a background operation:
```python
def _start_worker(self, worker):
    self.state.operation_in_progress = True
    worker.output_line.connect(self._on_output_line)
    worker.finished_ok.connect(self._on_finished_ok)
    worker.finished_error.connect(self._on_finished_error)
    worker.start()
```

On completion:
```python
def _on_finished_ok(self, report):
    self.state.operation_in_progress = False
    self.state.last_report_path = report.log_path
    self.state.run_complete = True
```

---

## 5. Output Panel (`ui/output_panel.py`)

The output panel is a `QTextEdit` set to read-only with a monospace
font and dark background.

### 5.1 Configuration

```python
font = QFont("Courier New", 10)
self.setFont(font)
self.setReadOnly(True)
self.setStyleSheet("background-color: #1e1e1e; color: #D4D4D4;")
```

### 5.2 Color Map

```python
COLOR_MAP = {
    "green":  "#4CAF50",
    "red":    "#F44336",
    "yellow": "#FFC107",
    "gray":   "#9E9E9E",
    "white":  "#D4D4D4",
}
```

### 5.3 Appending Output

```python
def append_line(self, message: str, color: str = "white"):
    hex_color = COLOR_MAP.get(color, COLOR_MAP["white"])
    cursor = self.textCursor()
    cursor.movePosition(QTextCursor.End)
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(hex_color))
    cursor.insertText(message + "\n", fmt)
    self.setTextCursor(cursor)
    self.ensureCursorVisible()
```

Output is appended, never replaced. `ensureCursorVisible()` auto-scrolls
to the latest line.

---

## 6. Instance Panel (`ui/instance_panel.py`)

### 6.1 Storage

Instance profiles are stored as JSON files in `data/instances/`.
One file per instance. Filename is slugified from the instance name:

```python
slug = name.lower().replace(" ", "_").replace("-", "_")
filename = f"{slug}.json"
```

The `data/instances/` directory is gitignored (contains credentials).

### 6.2 Profile JSON Format

```json
{
  "name": "CBM Production",
  "url": "https://cbm.espocloud.com",
  "api_key": "admin_username",
  "auth_method": "basic",
  "secret_key": "admin_password",
  "project_folder": "/home/user/Projects/CBM"
}
```

`project_folder` is optional. Existing files without it load normally
via `data.get("project_folder")` returning `None`.

### 6.3 Signals

```python
instance_selected = Signal(InstanceProfile)  # emitted on selection change
```

### 6.4 Project Folder Auto-Creation

When an instance with a `project_folder` is saved, the panel calls
`_ensure_project_structure(path)` which creates:
- `{path}/programs/`
- `{path}/reports/`
- `{path}/Implementation Docs/`

using `Path.mkdir(parents=True, exist_ok=True)`.

---

## 7. Program Panel (`ui/program_panel.py`)

### 7.1 Directory Source

The program panel displays `.yaml` files from its current directory.
The directory is set by the main window when an instance is selected:

```python
def set_directory(self, directory: Path):
    self._directory = directory
    self._refresh()
```

### 7.2 Version Display

Each file entry shows the `content_version` from the YAML alongside
the filename. The version is read from the YAML file's top-level
`content_version` key. Files without a `content_version` show no
version label.

### 7.3 Edit

Clicking Edit opens the selected YAML file in the system's default
text editor via:
```python
import subprocess
subprocess.Popen(["xdg-open", str(path)])  # Linux
# or os.startfile(str(path))              # Windows
```

---

## 8. Dialogs

### 8.1 Instance Dialog (`ui/instance_dialog.py`)

A `QDialog` for adding and editing instance profiles. Contains fields
for name, URL, auth method (combo box), credentials, and project
folder (with Browse button). Pre-populated when editing.

Auth method selection shows/hides the relevant credential fields:
- API Key: shows API Key field only
- HMAC: shows API Key and Secret Key fields
- Basic: shows Username and Password fields

### 8.2 Confirm Delete Dialog (`ui/confirm_delete_dialog.py`)

A `QDialog` triggered before any run containing `delete` or
`delete_and_create` entity actions.

**Entity name mapping** — this dialog currently contains
`ENTITY_NAME_MAP` and `get_espo_entity_name()`. These are core
business logic and should be refactored to `core/entity_manager.py`
in a future cleanup pass.

The Proceed button is connected to a `QLineEdit.textChanged` signal:

```python
def _on_text_changed(self, text):
    self.proceed_btn.setEnabled(text == "DELETE")
```

The dialog fires before any API calls — including non-destructive
ones in the same program run.

---

## 9. Background Workers (`workers/`)

All long-running operations run in `QThread` subclasses. Workers
communicate with the UI via signals only — never by calling UI
methods directly.

### 9.1 Signal Pattern

Every worker defines:

```python
output_line = Signal(str, str)    # (message, color)
finished_ok = Signal(object)      # result object
finished_error = Signal(str)      # error message string
```

Qt automatically queues signals across thread boundaries, making
`output_line.emit()` calls from the worker thread safe to receive
on the main thread.

### 9.2 RunWorker (`workers/run_worker.py`)

Orchestrates the full configuration run in sequence:

```
1. Entity deletions → rebuild_cache()
2. Entity creations → rebuild_cache()
3. Field operations (field_manager.run())
4. Layout operations (layout_manager.process_layouts())
5. Relationship operations (relationship_manager.run())
```

Each phase emits output via the `output_line` signal. On completion,
emits `finished_ok` with a `RunReport` object.

### 9.3 ImportWorker (`workers/import_worker.py`)

Runs the data import execute phase in the background. Follows the
same signal pattern as `RunWorker`. Emits `finished_ok` with an
`ImportReport` object.

---

## 10. File Structure

```
espo_impl/
├── main.py
├── ui/
│   ├── main_window.py
│   ├── instance_panel.py
│   ├── instance_dialog.py
│   ├── program_panel.py
│   ├── output_panel.py
│   ├── confirm_delete_dialog.py
│   └── import_dialog.py
└── workers/
    ├── run_worker.py
    └── import_worker.py
```

---

## 11. Known Issues and Technical Debt

- `ENTITY_NAME_MAP` and `get_espo_entity_name()` are in
  `confirm_delete_dialog.py` but belong in `core/entity_manager.py`
- Inline verification after field create/update is disabled due to
  EspoCRM cache staleness returning HTTP 500 immediately after writes.
  The standalone Verify action should be used instead.
- The Verify action currently checks fields only. Layouts and
  relationships are not re-verified by the Verify button.
