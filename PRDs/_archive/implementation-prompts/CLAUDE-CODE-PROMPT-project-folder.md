# Claude Code Prompt — Project Folder Per Instance

## Context

Currently the tool uses hardcoded directories relative to the tool's
base directory for YAML program files and reports:
- `data/programs/` — YAML files
- `reports/` — run/verify reports
- `PRDs/Implementation Docs/` — generated documentation

This creates a mess when managing multiple clients — all client data
lives inside the tool repo.

The fix: each EspoCRM instance has a **project folder** — a directory
the user selects when adding/editing an instance. All file operations
for that instance use paths relative to that folder.

```
Project Folder (e.g. ~/Dropbox/Projects/CBM/)
├── programs/            ← YAML program files
├── Implementation Docs/ ← generated reference manual
└── reports/             ← run/verify reports
```

Switching instances automatically switches the working context.
The tool repo itself contains no client data.

Read these files carefully before making any changes:
- `espo_impl/core/models.py`
- `espo_impl/ui/instance_dialog.py`
- `espo_impl/ui/instance_panel.py`
- `espo_impl/ui/main_window.py`
- `espo_impl/ui/program_panel.py`
- `espo_impl/workers/run_worker.py`

---

## Task 1 — Update `espo_impl/core/models.py`

Add `project_folder` to `InstanceProfile`:

```python
project_folder: str | None = None  # path to client project directory
```

Add after `secret_key`.

Add a property:
```python
@property
def programs_dir(self) -> Path | None:
    """Path to the programs directory for this instance."""
    if self.project_folder:
        return Path(self.project_folder) / "programs"
    return None

@property
def reports_dir(self) -> Path | None:
    """Path to the reports directory for this instance."""
    if self.project_folder:
        return Path(self.project_folder) / "reports"
    return None

@property
def docs_dir(self) -> Path | None:
    """Path to the Implementation Docs directory for this instance."""
    if self.project_folder:
        return Path(self.project_folder) / "Implementation Docs"
    return None
```

---

## Task 2 — Update `espo_impl/ui/instance_dialog.py`

Add a project folder field to the dialog.

### 2a — Add imports

```python
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton
```

### 2b — Add folder picker to `_build_ui`

After the secret key row, add:

```python
        # Project folder
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText(
            "Select project folder (programs, reports, docs)"
        )
        self.folder_input.setReadOnly(True)
        self.folder_browse_btn = QPushButton("Browse...")
        self.folder_browse_btn.clicked.connect(self._on_browse_folder)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_browse_btn)
        layout.addRow("Project Folder:", folder_layout)
```

### 2c — Add browse handler

```python
    def _on_browse_folder(self) -> None:
        """Open folder picker dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Project Folder",
            self.folder_input.text() or str(Path.home()),
        )
        if folder:
            self.folder_input.setText(folder)
```

### 2d — Pre-populate in edit mode

In `__init__`, after the existing pre-population block, add:

```python
            if profile.project_folder:
                self.folder_input.setText(profile.project_folder)
```

### 2e — Update `get_profile`

Add `project_folder` to the returned profile:

```python
        return InstanceProfile(
            name=self.name_input.text().strip(),
            url=self.url_input.text().strip(),
            api_key=self.key_input.text().strip(),
            auth_method=auth_method,
            secret_key=secret_key,
            project_folder=self.folder_input.text().strip() or None,
        )
```

### 2f — Validation

Project folder is optional — do not require it. But if provided,
verify the path exists:

```python
        folder = self.folder_input.text().strip()
        if folder and not Path(folder).exists():
            QMessageBox.warning(
                self,
                "Validation Error",
                f"Project folder does not exist:\n{folder}",
            )
            return
```

---

## Task 3 — Update `espo_impl/ui/instance_panel.py`

### 3a — Update `_load_instances`

Load `project_folder` from JSON:

```python
                profile = InstanceProfile(
                    name=data["name"],
                    url=data["url"],
                    api_key=data["api_key"],
                    auth_method=data.get("auth_method", "api_key"),
                    secret_key=data.get("secret_key"),
                    project_folder=data.get("project_folder"),
                )
```

### 3b — Update `_save_instance`

Save `project_folder` to JSON:

```python
        if profile.project_folder:
            data["project_folder"] = profile.project_folder
```

### 3c — Show project folder in panel

After the API Key display, add a read-only project folder display:

```python
        group_layout.addWidget(QLabel("Project Folder:"))
        self.folder_display = QLineEdit()
        self.folder_display.setReadOnly(True)
        group_layout.addWidget(self.folder_display)
```

Update `_on_selection_changed` to populate it:

```python
            self.folder_display.setText(profile.project_folder or "")
```

---

## Task 4 — Update `espo_impl/ui/program_panel.py`

The program panel currently loads YAML files from a hardcoded directory
passed at construction time. Update it to accept a dynamic directory
that changes when the instance selection changes.

### 4a — Add `set_programs_dir` method

```python
    def set_programs_dir(self, programs_dir: Path | None) -> None:
        """Update the programs directory and reload the file list.

        :param programs_dir: New programs directory, or None to clear.
        """
        if programs_dir is None:
            self.programs_dir = None
            self.list_widget.clear()
            self._paths.clear()
            return

        self.programs_dir = programs_dir
        programs_dir.mkdir(parents=True, exist_ok=True)
        self._load_programs()
```

### 4b — Update `_load_programs`

Use `self.programs_dir` rather than the constructor argument. Handle
`None` gracefully — show empty list with a placeholder message.

---

## Task 5 — Update `espo_impl/ui/main_window.py`

This is the most impactful change — wire everything together.

### 5a — Update `_on_instance_selected`

When an instance is selected, update the program panel's directory:

```python
    def _on_instance_selected(self, profile: InstanceProfile | None) -> None:
        """Handle instance selection change."""
        self.state.instance = profile
        self.state.validated = False
        self.state.run_complete = False

        # Update program panel to use this instance's project folder
        if profile and profile.programs_dir:
            self.program_panel.set_programs_dir(profile.programs_dir)
        else:
            # Fall back to default programs dir
            self.program_panel.set_programs_dir(
                self.base_dir / "data" / "programs"
            )

        self._update_button_states()
```

### 5b — Update reporter initialization

The reporter currently uses a hardcoded reports directory. Move it to
be instance-aware — create it lazily when a run starts:

In `_start_worker`, before creating the worker:

```python
        # Use instance project folder for reports, fall back to default
        if self.state.instance and self.state.instance.reports_dir:
            reports_dir = self.state.instance.reports_dir
        else:
            reports_dir = self.base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        self.reporter = Reporter(reports_dir)
```

Remove the `self.reporter = Reporter(...)` from `__init__`.

### 5c — Update Generate Docs button handler

Use the instance's docs directory:

```python
    def _on_generate_docs(self) -> None:
        """Generate the CRM reference documentation from YAML files."""
        if not self.state.instance:
            self.output_panel.append_line(
                "[DOCGEN] No instance selected.", "red"
            )
            return

        if not self.state.instance.project_folder:
            self.output_panel.append_line(
                "[DOCGEN] No project folder configured for this instance. "
                "Edit the instance to add a project folder.",
                "red"
            )
            return

        programs_dir = self.state.instance.programs_dir
        output_dir = self.state.instance.docs_dir
        ...
```

### 5d — Update `_update_button_states`

Generate Docs button should be enabled when the selected instance has
a project folder with at least one YAML file:

```python
        has_programs = (
            self.state.instance is not None
            and self.state.instance.programs_dir is not None
            and self.state.instance.programs_dir.exists()
            and any(self.state.instance.programs_dir.glob("*.yaml"))
        )
        self.docgen_btn.setEnabled(has_programs and not in_progress)
```

---

## Task 6 — Backward Compatibility

Instances without a `project_folder` (existing configs) must continue
to work. When `project_folder` is None:

- Program panel falls back to `base_dir / "data" / "programs"`
- Reports go to `base_dir / "reports"`
- Generate Docs shows a message asking the user to configure a project folder

This ensures existing users aren't broken by the upgrade.

---

## Task 7 — Create Folder Structure on First Use

When a project folder is selected and an instance is saved, create the
standard subdirectories if they don't exist:

```python
def _ensure_project_structure(folder: Path) -> None:
    """Create standard project subdirectories if they don't exist."""
    (folder / "programs").mkdir(parents=True, exist_ok=True)
    (folder / "reports").mkdir(parents=True, exist_ok=True)
    (folder / "Implementation Docs").mkdir(parents=True, exist_ok=True)
```

Call this in `instance_panel._save_instance` after saving the JSON,
when `profile.project_folder` is set.

---

## Task 8 — Update `docs/process.md`

Update Section 2 (Repository Structure) and the Quick Start section to
reflect the new project folder concept:

```markdown
## Instance and Project Folder

Each EspoCRM instance is configured with a **project folder** — a
directory on your local machine containing all files for that client:

```
~/Projects/CBM/
├── programs/            ← YAML program files
├── Implementation Docs/ ← generated reference manual
└── reports/             ← run/verify reports
```

When you add an instance, click **Browse** to select the project folder.
The tool creates the `programs/`, `Implementation Docs/`, and `reports/`
subdirectories automatically.

To deploy a configuration, place YAML program files in the `programs/`
subfolder of the project folder. The Program File panel will show all
YAML files in that folder automatically when the instance is selected.
```

---

## Task 9 — Tests

Add to `tests/test_models.py` (create if needed):
- `InstanceProfile.programs_dir` returns correct path when set
- `InstanceProfile.programs_dir` returns None when not set
- `InstanceProfile.reports_dir` returns correct path
- `InstanceProfile.docs_dir` returns correct path

Run `uv run pytest tests/ -v` and confirm all tests pass.

---

## Implementation Order

1. Task 1 — models.py
2. Task 9 — model tests (confirm passing)
3. Task 2 — instance_dialog.py
4. Task 3 — instance_panel.py
5. Task 4 — program_panel.py
6. Task 5 — main_window.py
7. Task 6 — verify backward compatibility manually
8. Task 7 — folder structure creation
9. Task 8 — process.md

Confirm with me after step 2 before proceeding.

---

## Important Notes

### Existing instance JSON files
The existing `data/instances/cbm_test.json` (or similar) will not have
a `project_folder` key. Loading it must not crash — use `.get()` with
a `None` default throughout.

### Program panel constructor
The program panel currently takes `programs_dir` as a constructor argument.
Keep this for backward compatibility — it becomes the fallback directory
used when no instance is selected or the selected instance has no project
folder. The `set_programs_dir` method adds dynamic updating on top.

### Reporter initialization
The reporter is currently created once in `MainWindow.__init__`. After
this change it needs to be recreated when the reports directory changes.
The simplest approach is to create it lazily in `_start_worker` and
`_on_worker_finished` using the current instance's reports directory.
