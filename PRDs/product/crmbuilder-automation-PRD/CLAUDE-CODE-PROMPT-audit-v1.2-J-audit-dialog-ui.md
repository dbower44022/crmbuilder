# CLAUDE-CODE-PROMPT — audit-v1.2-J — Audit Dialog UI

**Repo:** `crmbuilder`
**Series:** `audit-v1.2` (eleven-prompt sequence implementing the v1.2
expansion of the Audit feature per
`PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md` v1.3)
**Last Updated:** 05-24-26 08:30
**Spec:** No schema doc edits — UI-only prompt. The behavior surfaces
DEC-180 (default-True for security and filtered-tab checkboxes) and
DEC-181 (overwrite-confirmation dialog) in the user-facing audit
configuration.
**Planning:** `PRDs/product/crmbuilder-automation-PRD/audit-v1.2-planning.md`
§5 Prompt J.
**Depends on:** Prompt H (commit `3a9aacdc` — `AuditOptions.include_security`
exists), Prompt I (commit `b1ef8652` — `AuditOptions.include_filtered_tabs`
exists). The UI plumbs preferences that the audit manager already
honors.
**Governance:** No new decisions in this prompt. Surfaces existing
DECs (180, 181) in operator-facing UI.

## Position in the Series

This is **Prompt J — UI work.** No new domain logic; this prompt
plumbs the operator's choices to the `AuditOptions` the audit
manager already honors after Prompts H and I. Three operator-visible
surfaces:

1. Entity-picker `QListWidget` populated by pre-flight
   `get_all_scopes()` discovery, supporting "Select All" / "Select
   None" buttons
2. Two new checkboxes: **Security (roles and teams)** and
   **Filtered tabs**, both default-checked per DEC-180
3. Pre-run overwrite-confirmation `QMessageBox` per DEC-181 when
   the output directory contains files matching the audit emission
   pattern

After this prompt:

- **Prompt K** documentation (`feat-audit.md` v1.2 + user-guide
  updates with new screenshots)

This is the penultimate prompt in the series.

**This prompt does NOT implement:**

- Schema edits — no new YAML surface, no new DECs
- Domain logic — `AuditOptions.include_security` /
  `include_filtered_tabs` / `selected_entities` already exist or
  get added here purely as UI-bound fields
- Documentation — Prompt K
- A diff-aware overwrite-confirmation dialog showing per-file
  changes — DEC-181 specifies a simple existence-check
  confirmation; the diff-aware variant is captured as a follow-on
  enhancement (the `(instance_id, entity_yaml_name, tab_id)`
  unique-key triple in the FilteredTab table from Prompt I makes
  this implementable later if operator feedback warrants it)
- Background-thread pre-flight discovery — synchronous call with a
  brief loading state per the planning doc; sub-second on local
  EspoCRM instances

## Scope

In scope:

1. `espo_impl/core/audit_manager.py`:
   - Add `selected_entities: set[str] | None = None` to
     `AuditOptions` (None preserves existing default: all
     discovered entities are audited)
   - Extend `_discover_entities` to filter by `selected_entities`
     when not None (post-discovery filter; the EspoCRM API doesn't
     support entity-name filtering on the scope-list endpoint, so
     filtering happens client-side)
2. `automation/ui/deployment/audit_entry.py`:
   - Add a `QListWidget` entity-picker between the existing instance
     picker and the Audit Scope group box
   - Add "Select All" / "Select None" buttons in a small button row
     above the picker
   - Add pre-flight discovery in `refresh()` — when an instance is
     active and the picker hasn't been populated for that instance,
     call `client.get_all_scopes()` synchronously with a brief
     loading state ("Loading entities..." label) and populate the
     picker with checkboxes (default all checked)
   - Add "Security (roles and teams)" checkbox below the existing
     Audit Scope checkboxes, default checked per DEC-180
   - Add "Filtered tabs" checkbox below Security, default checked
     per DEC-180
   - Extend `_on_start_audit` to:
     - Build `selected_entities` from the picker's checked items
     - Detect when no entities are selected and disable the Run
       button or show a "no work to do" message
     - Check the output directory for files matching the audit
       emission pattern (`*.yaml` at the program root OR
       `security/*.yaml` under the `security/` subdirectory) and
       fire the overwrite-confirmation dialog (DEC-181) before
       opening the progress dialog when the directory is non-empty
   - Extend `AuditOptions` construction in `_on_start_audit` to
     pass the new `include_security`, `include_filtered_tabs`, and
     `selected_entities` fields
3. Tests:
   - `tests/test_audit_entry.py` (if it exists; create if not) —
     Qt-test patterns covering the new UI plumbing
   - `tests/test_audit_manager.py` — `selected_entities` filtering
     in `_discover_entities`

Out of scope:

- Schema doc edits
- Documentation — Prompt K
- Background-thread pre-flight (synchronous is fine for sub-second
  calls)
- Diff-aware overwrite-confirmation dialog (deferred as a
  potential follow-on; the simple existence check matches DEC-181)
- Persistence of the operator's per-instance entity selection
  across sessions (each fresh launch starts with all entities
  checked)

## Working Method

Standard CRM Builder Python conventions:

```bash
uv run ruff check espo_impl/core/audit_manager.py automation/ui/deployment/audit_entry.py tests/
uv run pytest tests/ -v
```

**Precedents.**

- The existing `_setup_ui` in `audit_entry.py` (around line 100+)
  is the structural template for the new picker UI. Mirror its
  `QGroupBox` + layout patterns
- Other entries in `automation/ui/deployment/` use `QListWidget`
  with checkable items; check `program_panel.py` or
  `deployment_logic.py` for the canonical pattern in this codebase
- Existing Qt tests under `tests/` (whichever ones use
  `pytestqt`) — mirror their `qtbot`-based interaction patterns

## Files to Modify

### 1. `espo_impl/core/audit_manager.py` — `selected_entities`

Add the new field on `AuditOptions`:

```python
@dataclass
class AuditOptions:
    """Options controlling what the audit captures."""

    include_custom_fields: bool = True
    include_native_custom_fields: bool = True
    include_detail_layouts: bool = True
    include_list_layouts: bool = True
    include_relationships: bool = True
    include_native_fields: bool = False
    include_security: bool = True
    include_filtered_tabs: bool = True
    selected_entities: set[str] | None = None  # NEW per DEC-181
```

The `selected_entities` set holds EspoCRM wire-name entities (e.g.,
`{"Contact", "CEngagement"}`). `None` preserves existing behavior
(audit all discovered entities).

Extend `_discover_entities` to filter post-discovery:

```python
def _discover_entities(
    self, report: AuditReport,
) -> list[EntityAuditResult]:
    """Discover entities on the source instance."""
    # ... existing fetch via get_all_scopes ...
    entities: list[EntityAuditResult] = []
    for wire_name, scope_def in all_scopes.items():
        # ... existing classification / filter logic ...
        if (
            self._options.selected_entities is not None
            and wire_name not in self._options.selected_entities
        ):
            continue  # NEW — skip entities not in the operator's selection
        # ... existing append-to-entities path ...
    return entities
```

The filter sits inside the existing loop so that any entity-type
classification (custom-vs-native, etc.) is still applied before the
filter. The result: only entities that PASS classification AND are
in the operator's selection get audited.

### 2. `automation/ui/deployment/audit_entry.py` — UI work

**Add the entity-picker UI.** Insert a new `QGroupBox` between the
instance-info `QGroupBox` (around line 118) and the Audit Scope
`QGroupBox` (around line 121):

```python
# Entity picker
picker_group = QGroupBox("Entities to Audit")
picker_layout = QVBoxLayout(picker_group)

picker_button_row = QHBoxLayout()
self._btn_select_all = QPushButton("Select All")
self._btn_select_all.clicked.connect(self._on_select_all_entities)
picker_button_row.addWidget(self._btn_select_all)

self._btn_select_none = QPushButton("Select None")
self._btn_select_none.clicked.connect(self._on_select_none_entities)
picker_button_row.addWidget(self._btn_select_none)

picker_button_row.addStretch()
picker_layout.addLayout(picker_button_row)

self._entity_picker = QListWidget()
self._entity_picker.setMinimumHeight(180)
self._entity_picker.setSelectionMode(QListWidget.SelectionMode.NoSelection)
picker_layout.addWidget(self._entity_picker)

self._picker_loading_label = QLabel("Loading entities...")
self._picker_loading_label.setStyleSheet(
    "font-size: 12px; color: #757575; padding: 4px;"
)
self._picker_loading_label.setVisible(False)
picker_layout.addWidget(self._picker_loading_label)

content_layout.addWidget(picker_group)
```

Tracking state for the populated set:

```python
self._picker_populated_for_instance_id: int | None = None
```

Initialize in `__init__`.

**Add the two new scope checkboxes.** Inside the existing Audit
Scope `QGroupBox`, after the existing `_cb_include_native` (around
line 148):

```python
self._cb_security = QCheckBox("Security (roles and teams)")
self._cb_security.setChecked(True)  # DEC-180
scope_layout.addWidget(self._cb_security)

self._cb_filtered_tabs = QCheckBox("Filtered tabs")
self._cb_filtered_tabs.setChecked(True)  # DEC-180
scope_layout.addWidget(self._cb_filtered_tabs)
```

**Pre-flight discovery in `refresh`.** Add a helper invoked from
`refresh()`:

```python
def refresh(self, conn, instance, project_folder, has_instances):
    # ... existing setup ...
    if not instance:
        # ... existing empty-state handling ...
        return
    # ... existing visible-content setup ...

    # NEW: populate entity picker for this instance if not already
    if self._picker_populated_for_instance_id != instance.id:
        self._populate_entity_picker(instance)
        self._picker_populated_for_instance_id = instance.id

def _populate_entity_picker(self, instance: InstanceRow) -> None:
    """Pre-flight discovery to populate the entity-picker list.

    Fetches the scope list from the active instance synchronously
    (sub-second on local EspoCRM instances) and adds a checkable
    item per discovered entity. Filters out non-entity scopes (the
    metadata-only ones that aren't auditable as entities).

    Shows a brief loading state during the call; on failure, the
    picker stays empty and the loading label switches to an error
    message rather than tearing down the UI.
    """
    from espo_impl.core.api_client import EspoAdminClient
    from espo_impl.core.models import InstanceProfile

    self._entity_picker.clear()
    self._picker_loading_label.setText("Loading entities...")
    self._picker_loading_label.setVisible(True)
    QApplication.processEvents()  # Ensure label shows before blocking call

    detail = load_instance_detail(self._conn, instance.id)
    if not detail or not detail.url or not detail.username or not detail.password:
        self._picker_loading_label.setText(
            "Instance is missing URL or credentials; cannot load entities."
        )
        return

    profile = InstanceProfile(
        name=detail.name,
        url=detail.url,
        api_key=detail.username,
        auth_method="basic",
        secret_key=detail.password,
    )
    client = EspoAdminClient(profile)
    status, all_scopes = client.get_all_scopes()
    if status != 200 or not isinstance(all_scopes, dict):
        self._picker_loading_label.setText(
            f"Could not load entities (HTTP {status}). Audit can "
            f"still run; all entities will be audited by default."
        )
        return

    # Filter to actual entity scopes (skip metadata-only scopes,
    # tab-only scopes, etc.)
    entity_names = sorted(
        name for name, scope_def in all_scopes.items()
        if isinstance(scope_def, dict)
        and scope_def.get("entity") is True
    )

    for name in entity_names:
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self._entity_picker.addItem(item)

    self._picker_loading_label.setVisible(False)


def _on_select_all_entities(self) -> None:
    """Check every entity in the picker."""
    for i in range(self._entity_picker.count()):
        self._entity_picker.item(i).setCheckState(Qt.CheckState.Checked)


def _on_select_none_entities(self) -> None:
    """Uncheck every entity in the picker."""
    for i in range(self._entity_picker.count()):
        self._entity_picker.item(i).setCheckState(Qt.CheckState.Unchecked)


def _get_selected_entities(self) -> set[str] | None:
    """Return the set of checked entity names, or None for all-checked.

    Returning None when all are checked preserves the existing
    audit behavior (audit everything) without adding a redundant
    filter step.
    """
    selected: set[str] = set()
    total = self._entity_picker.count()
    if total == 0:
        return None  # Picker not populated; defer to audit_manager default
    for i in range(total):
        item = self._entity_picker.item(i)
        if item.checkState() == Qt.CheckState.Checked:
            selected.add(item.text())
    if len(selected) == total:
        return None  # All checked → audit everything; preserve None semantic
    return selected
```

**Overwrite-confirmation in `_on_start_audit`.** Add a check before
the progress-dialog launch:

```python
# Existing _on_start_audit body up through output_dir construction...

# NEW: warn the operator if the output directory contains prior
# audit YAML output (per DEC-181)
if output_dir.exists():
    existing_yaml = list(output_dir.glob("*.yaml")) + list(
        output_dir.glob("security/*.yaml")
    )
    if existing_yaml:
        reply = QMessageBox.warning(
            self,
            "Overwrite Existing Audit Output?",
            (
                f"Output directory contains {len(existing_yaml)} existing "
                f"audit YAML file(s); running this audit will overwrite "
                f"them. Proceed?"
            ),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,  # default focus on Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return  # Operator cancelled; do not start the audit

# NEW: detect no-entities-selected
selected = self._get_selected_entities()
if selected is not None and not selected:
    QMessageBox.information(
        self,
        "No Entities Selected",
        "No entities are selected for audit. Check at least one "
        "entity in the picker, or use 'Select All'.",
    )
    return

# Existing AuditOptions construction extended:
options = AuditOptions(
    include_custom_fields=self._cb_custom_fields.isChecked(),
    include_native_custom_fields=self._cb_native_fields.isChecked(),
    include_detail_layouts=self._cb_detail_layouts.isChecked(),
    include_list_layouts=self._cb_list_layouts.isChecked(),
    include_relationships=self._cb_relationships.isChecked(),
    include_native_fields=self._cb_include_native.isChecked(),
    include_security=self._cb_security.isChecked(),
    include_filtered_tabs=self._cb_filtered_tabs.isChecked(),
    selected_entities=selected,
)

# Rest of _on_start_audit unchanged...
```

The `output_dir.exists()` check is important because the timestamp-
based output directory naming (`audit-{timestamp}`) means a fresh
audit run with a new timestamp won't trigger the dialog. The
overwrite case arises only when the operator manually points at an
existing directory or somehow runs two audits within the same
second (timestamp collision — vanishingly rare but the check still
handles it).

**Note on the output-directory convention.** The current code at
line 295 builds `output_dir` with a timestamp suffix:

```python
output_dir = Path(self._project_folder) / "programs" / f"audit-{timestamp}"
```

This means the overwrite-confirmation dialog rarely fires in
practice — only on second-runs within the same second. **DEC-181 is
honored regardless**: the dialog logic is present and correct, even
if the conditions for it to fire are narrow. A future operator who
wants persistent audit output (e.g., always overwriting
`programs/audit-current/`) just needs to change the timestamp
suffix to a fixed name; the dialog protects them automatically.

### 3. Tests

**`tests/test_audit_manager.py` — `selected_entities` filtering:**

- `test_discover_entities_with_selected_entities_filters` — three
  entities discovered on the server (Contact, Account,
  CEngagement); `AuditOptions.selected_entities={"Contact"}`;
  result list has only the Contact entry
- `test_discover_entities_with_none_selected_entities_audits_all` —
  `selected_entities=None` (default); all three entities are
  audited (existing behavior preserved)
- `test_discover_entities_with_empty_set_audits_nothing` —
  `selected_entities=set()`; no entities audited (consistent with
  the picker UX where "Select None" produces an empty set, but the
  UI prevents starting an audit in that state)

**`tests/test_audit_entry.py` (create if missing):**

- `test_audit_entry_picker_populates_on_refresh` — mock the API
  client and conn; call `refresh` with a valid instance; picker
  receives the expected entities (mocked `get_all_scopes` response)
- `test_audit_entry_picker_select_all_button` — populated picker
  with three items; click "Select All"; all three are checked
- `test_audit_entry_picker_select_none_button` — populated picker;
  click "Select None"; none checked
- `test_audit_entry_security_checkbox_default_checked` — instantiate
  AuditEntry; `_cb_security.isChecked()` is True
- `test_audit_entry_filtered_tabs_checkbox_default_checked` — same
  for `_cb_filtered_tabs`
- `test_audit_entry_start_audit_passes_selected_entities` — mock
  the AuditProgressDialog; user unchecks one entity; clicks Start
  Audit; the AuditOptions passed to the progress dialog has
  `selected_entities=` the expected subset (not None)
- `test_audit_entry_start_audit_all_checked_passes_none` — all
  entities checked; Start Audit; AuditOptions has
  `selected_entities=None`
- `test_audit_entry_overwrite_confirmation_fires_on_existing_yaml`
  — output directory contains a stub `something.yaml`; click Start
  Audit; QMessageBox.warning is called; if user clicks Cancel, the
  progress dialog is not launched
- `test_audit_entry_overwrite_confirmation_skipped_when_empty` —
  empty output directory; Start Audit; no confirmation dialog;
  progress dialog launches
- `test_audit_entry_no_entities_selected_shows_warning` — Select
  None; click Start Audit; QMessageBox.information shown; progress
  dialog not launched
- `test_audit_entry_picker_failure_keeps_ui_usable` — mock
  `get_all_scopes` returning HTTP 500; picker stays empty; loading
  label shows the error; the rest of the audit-entry UI is usable
  (operator can still run the audit with default-all-entities
  behavior)

(Adapt the Qt-test invocation style to whatever this codebase
uses — `pytestqt`'s `qtbot` is the most common pattern.)

## Acceptance Criteria

1. `AuditOptions.selected_entities` exists and defaults to None.
2. `_discover_entities` filters by `selected_entities` when set.
3. AuditEntry has an entity-picker `QListWidget` with checkable
   items, populated on first `refresh` per instance via a
   synchronous `get_all_scopes()` call. The picker shows a brief
   loading state and degrades gracefully on API failure (UI
   remains usable).
4. "Select All" and "Select None" buttons modify the picker's
   check states correctly.
5. AuditEntry has two new checkboxes — "Security (roles and
   teams)" and "Filtered tabs" — both default-checked per
   DEC-180.
6. `_on_start_audit` builds an `AuditOptions` with the new
   `include_security`, `include_filtered_tabs`, and
   `selected_entities` fields populated from the UI.
7. When no entities are selected, Start Audit shows a clear
   warning message and does not launch the progress dialog.
8. When the output directory contains prior audit YAML output (
   `*.yaml` at root OR `security/*.yaml` under the subdirectory),
   a confirmation dialog fires per DEC-181 with Cancel as the
   default focus; Cancel returns to the audit-entry view without
   starting; Proceed launches the progress dialog normally.
9. All existing tests continue to pass.
10. New tests cover every path enumerated in §3 above.
11. `uv run ruff check espo_impl/ automation/ tests/` passes clean
    on touched files.
12. `uv run pytest tests/ -v` passes.
13. Commit and push to `main` with a clear message referencing
    this prompt.

## Out of Scope

- Schema doc edits
- Documentation — Prompt K
- Background-thread pre-flight discovery (synchronous suffices)
- Diff-aware overwrite-confirmation dialog (deferred; the
  unique-key triple in the FilteredTab table makes this
  implementable later)
- Persistence of operator's per-instance entity selection across
  sessions
- Pre-flight failure detail (e.g., distinguishing 401 from 500 in
  the loading-label message)

## Reporting Back

When finished, report:

- Modified file paths and line counts
- New tests added (count and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt K

The expected next step after Prompt J is green is **Prompt K** —
the final prompt in the series: documentation updates
(`PRDs/product/features/feat-audit.md` bumped from v1.1 to v1.2,
`docs/user/user-guide.md` updated section on the Audit feature,
`CLAUDE.md` entries for the new managers, dataclasses, and
pipeline step). No new domain logic; pure documentation rendering.
Should be the shortest prompt in the series.

After Prompt K, this conversation moves to close-out: seven DECs
to formalize in the SES-NNN close-out payload (next-available
identifier verified at close-out time against the engagement's
db-export snapshot), plus the apply prompt rendered inline.
