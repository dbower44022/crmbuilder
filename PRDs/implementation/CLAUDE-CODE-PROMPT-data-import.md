# Claude Code Prompt — Data Import Feature

## Context

CRM Builder is adding a Data Import feature that allows an administrator
to import records from a JSON file into an EspoCRM instance. This is the
first data-level operation in the tool — all existing operations work on
schema (fields, layouts, relationships), not records.

Read these files carefully before writing any code:

- `PRDs/crmbuilder-spec-data-import.md` — full feature specification (read first)
- `espo_impl/core/api_client.py` — existing API client to extend
- `espo_impl/ui/main_window.py` — main window to modify
- `espo_impl/workers/run_worker.py` — worker pattern to follow
- `espo_impl/core/models.py` — existing data models

---

## Overview of Changes

1. Add 5 new methods to `core/api_client.py`
2. Create `core/import_manager.py` — CHECK and ACT logic
3. Create `workers/import_worker.py` — QThread background worker
4. Create `ui/import_dialog.py` — four-step wizard dialog
5. Update `ui/main_window.py` — add Import Data button

Implement in the order listed. Confirm with me after each task before
proceeding to the next.

---

## Task 1 — Update `core/api_client.py`

Add the following five methods to the `EspoAdminClient` class. Do not
modify any existing methods.

### 1a — `get_entity_field_list()`

```python
def get_entity_field_list(
    self, entity: str
) -> tuple[int, dict[str, dict] | None]:
    """Fetch all field definitions for an entity.

    :param entity: Entity name (e.g., "Contact").
    :returns: Tuple of (status_code, {fieldName: {label, type, ...}} or None).
    """
```

Endpoint: `GET /api/v1/Metadata?key=entityDefs.{entity}.fields`

Returns the full fields dict from Metadata. On success the body is a dict
where each key is an internal field name and each value contains at minimum
`type` and `label`.

### 1b — `search_by_email()`

```python
def search_by_email(
    self, entity: str, email: str
) -> tuple[int, list[dict] | None]:
    """Search for records matching an email address.

    :param entity: Entity name (e.g., "Contact").
    :param email: Email address to search for.
    :returns: Tuple of (status_code, list of matching records or None).
    """
```

Endpoint:
```
GET /api/v1/{entity}?where[0][type]=equals&where[0][attribute]=emailAddress&where[0][value]={email}&maxSize=2
```

Parse the `list` array from the response body and return it. Return an
empty list (not None) if no records match.

### 1c — `get_record()`

```python
def get_record(
    self, entity: str, record_id: str
) -> tuple[int, dict[str, Any] | None]:
    """Fetch a single record by ID.

    :param entity: Entity name.
    :param record_id: EspoCRM record ID.
    :returns: Tuple of (status_code, record dict or None).
    """
```

Endpoint: `GET /api/v1/{entity}/{record_id}`

### 1d — `create_record()`

```python
def create_record(
    self, entity: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any] | None]:
    """Create a new record.

    :param entity: Entity name.
    :param payload: Field values to set.
    :returns: Tuple of (status_code, created record or None).
    """
```

Endpoint: `POST /api/v1/{entity}`

### 1e — `patch_record()`

```python
def patch_record(
    self, entity: str, record_id: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any] | None]:
    """Patch specific fields on an existing record.

    Only the fields included in payload are updated.
    Fields not in payload are left unchanged.

    :param entity: Entity name.
    :param record_id: EspoCRM record ID.
    :param payload: Partial field values to update.
    :returns: Tuple of (status_code, response or None).
    """
```

Endpoint: `PATCH /api/v1/{entity}/{record_id}`

---

## Task 2 — Create `core/import_manager.py`

This module contains the business logic for CHECK and ACT. It has no
dependency on PySide6 — it is pure Python.

### 2.1 Data structures

Define these dataclasses at the top of the module:

```python
from dataclasses import dataclass, field
from enum import Enum


class ImportAction(Enum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class RecordPlan:
    """The plan for a single record determined during CHECK."""
    source_name: str             # display name from JSON
    email: str | None            # email used for matching
    action: ImportAction
    espo_id: str | None = None   # set if existing record found
    fields_to_set: dict = field(default_factory=dict)
    fields_skipped: list = field(default_factory=list)  # had existing value
    error_message: str | None = None


@dataclass
class ImportResult:
    """The outcome of ACT for a single record."""
    source_name: str
    email: str | None
    action: ImportAction
    success: bool
    fields_set: list = field(default_factory=list)
    fields_skipped: list = field(default_factory=list)
    error_message: str | None = None


@dataclass
class ImportReport:
    """Complete report for an import operation."""
    timestamp: str
    instance_name: str
    entity: str
    source_file: str
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[ImportResult] = field(default_factory=list)
```

### 2.2 `ImportManager` class

```python
class ImportManager:
    def __init__(self, client: EspoAdminClient, emit_line=None):
        """
        :param client: Authenticated API client.
        :param emit_line: Optional callable(message, color) for live output.
        """
```

### 2.3 `check()` method

```python
def check(
    self,
    entity: str,
    records: list[dict],
    field_mapping: dict[str, str],
    fixed_values: dict[str, str],
) -> list[RecordPlan]:
    """Determine the action for each record without making changes.

    :param entity: EspoCRM entity name.
    :param records: List of source records (each has a 'fields' dict).
    :param field_mapping: {json_field_key: espo_field_name}.
                          Keys mapped to "(skip)" are excluded.
    :param fixed_values: {espo_field_name: value} applied to all records.
    :returns: List of RecordPlan, one per source record.
    """
```

For each record:

1. Build the candidate payload by applying `field_mapping` to the record's
   `fields` dict. Skip any JSON key mapped to `"(skip)"` or with an empty
   value. Apply `fixed_values` on top.

2. Extract the email address. The email field is whatever `field_mapping`
   key maps to `"emailAddress"`, or if `emailAddress` is in `fixed_values`.
   If no email address can be found → `RecordPlan(action=ERROR, ...)`.

3. Call `client.search_by_email(entity, email)`.
   - Connection error → `RecordPlan(action=ERROR, ...)`.
   - 0 results → `action = CREATE`. `fields_to_set` = full candidate payload.
   - 1 result → fetch full record via `client.get_record()`. For each field
     in candidate payload: if the existing EspoCRM value is `None`, `""`,
     or the key is absent → include in `fields_to_set`. Otherwise → append
     field name to `fields_skipped`.
     If `fields_to_set` is empty → `action = SKIP`.
     Otherwise → `action = UPDATE`, `espo_id` = existing record ID.
   - 2 results → use first result (same logic as 1 result), but log a
     WARNING about duplicate email addresses.

### 2.4 `execute()` method

```python
def execute(
    self,
    entity: str,
    plans: list[RecordPlan],
) -> ImportReport:
    """Execute a list of RecordPlans produced by check().

    :param entity: EspoCRM entity name.
    :param plans: Plans from check().
    :returns: ImportReport with per-record results.
    """
```

For each plan:

- `SKIP` → log as skipped, append `ImportResult(success=True)`.
- `ERROR` → log as error, append `ImportResult(success=False)`.
- `CREATE` → call `client.create_record(entity, plan.fields_to_set)`.
  - On HTTP 200/201 → `ImportResult(success=True, action=CREATE, ...)`.
  - On error → `ImportResult(success=False, error_message=...)`.
  - Continue to next record regardless of outcome.
- `UPDATE` → call `client.patch_record(entity, plan.espo_id, plan.fields_to_set)`.
  - On HTTP 200 → `ImportResult(success=True, action=UPDATE, ...)`.
  - On error → `ImportResult(success=False, error_message=...)`.
  - Continue to next record regardless of outcome.

Emit output lines via `self.emit_line(message, color)` if set:
```
[IMPORT]  {name} ... CREATING
[IMPORT]  {name} ... OK
[IMPORT]  {name} ... UPDATE (patching N fields)
[IMPORT]  {name} ... SKIP (no email / all fields have values)
[IMPORT]  {name} ... ERROR — {message}
```

Colors: green for OK, yellow for SKIP, red for ERROR, white for in-progress.

---

## Task 3 — Create `workers/import_worker.py`

Follow the exact same pattern as `workers/run_worker.py`. Read that file
before writing this one.

```python
class ImportWorker(QThread):
    output_line = Signal(str, str)        # message, color
    finished_ok = Signal(object)          # ImportReport
    finished_error = Signal(str)          # error message
```

The worker receives:
- `client: EspoAdminClient`
- `entity: str`
- `records: list[dict]`
- `field_mapping: dict[str, str]`
- `fixed_values: dict[str, str]`
- `plans: list[RecordPlan]` — pre-computed from CHECK step

The `run()` method calls `import_manager.execute(entity, plans)` and
emits results via signals. The manager's `emit_line` callback should
forward to `self.output_line.emit`.

---

## Task 4 — Create `ui/import_dialog.py`

A four-step modal wizard dialog (subclass of `QDialog`). Read the spec
in `PRDs/crmbuilder-spec-data-import.md` Section 3 carefully.

The dialog is initialized with the `InstanceProfile` and the
`EspoAdminClient`.

### 4.1 Overall structure

Use a `QStackedWidget` to hold the four steps. Navigation buttons
(Back / Next / Import / Close) sit in a fixed bottom bar.

The dialog minimum size should be 800×600 and should be resizable.

### 4.2 Step 1 — Setup widget

**File selection:**
- `QLineEdit` (read-only) showing selected file path
- `QPushButton("Browse...")` — opens `QFileDialog.getOpenFileName`
  filtered to `*.json`
- On file selection: parse JSON, extract records array, display
  record count (e.g. `"72 records found"`)
- If JSON is malformed or does not contain a recognizable records array,
  show an error label and do not advance the record count

**Entity type:**
- `QComboBox` with current options: `Contact`
  (add more later by extending this list)
- On selection change: trigger API call to fetch field list via
  `client.get_entity_field_list(entity)`. Show a loading indicator
  while the call is in progress (can be synchronous for this call since
  it is brief — do not use a worker thread)
- Cache the returned field dict as `self._espo_fields`

**Fixed-value fields:**
- `QTableWidget` with columns: Field | Value | [✕]
- `QPushButton("+ Add Field")` adds a new row
- Field column: `QComboBox` populated from `self._espo_fields`
  (sorted by label; display as "Label (internal_name)")
- Value column: `QLineEdit`
- [✕] column: `QPushButton` that removes the row
- Fixed-value field dropdowns must update whenever a field is added or
  removed — fields already chosen in another row should not be selectable
  (or should be visually marked as already used)

**Next button:** enabled when file is selected and at least one field is
fetched (i.e., entity type chosen and API call succeeded).

### 4.3 Step 2 — Field Mapping widget

Built when the user enters this step (on Next from Step 1).

**Mapping table:**
- `QTableWidget` with columns: JSON Field | EspoCRM Field
- One row per unique JSON key found across all records (sorted alphabetically)
- JSON Field column: read-only `QLabel`-style cell showing the key name
- EspoCRM Field column: `QComboBox` per row
  - First item: `(skip)`
  - Remaining items: all fields from `self._espo_fields` sorted by label
    (display: "Label — internal_name")
  - Fields used in fixed-value Step 1 are excluded from these dropdowns
- Auto-mapping applied on first build using the alias table in spec
  Section 4 plus normalized label matching
- When a dropdown changes, recompute the Unmapped Fields list

**Unmapped Fields panel:**
- `QGroupBox("Fields with no EspoCRM mapping")`
- `QListWidget` inside, updated live as the user makes mapping selections
- A JSON key appears here if its dropdown is set to `(skip)` AND it was
  not auto-mapped AND the user has not manually mapped it
- Actually: a field appears in Unmapped if its EspoCRM dropdown is `(skip)`.
  The user is informed these fields will not be imported.

**Next button:** enabled when at least one mapping is set (i.e. at least
one row has something other than `(skip)` selected).

### 4.4 Step 3 — Preview widget

Built when the user enters this step (on Next from Step 2). Runs CHECK
via `ImportManager.check()` with a progress indicator while the API
calls are in progress (use a worker thread for this step since it makes
N API calls).

**During check:**
- Show a progress bar (indeterminate)
- Show a status label: "Checking record N of 72..."
- Back and Next buttons disabled while checking

**After check:**
- `QScrollArea` containing one collapsible row per record (or a
  `QTableWidget` with expandable rows is also acceptable)
- Each row shows: name, email, action (CREATE / UPDATE / SKIP / ERROR),
  and the list of fields to be set / skipped
- Summary counts shown at the bottom (fixed, not scrollable):
  ```
  To create: N  |  To update: N  |  To skip: N  |  Errors: N
  ```
- Import button enabled if at least one record has action CREATE or UPDATE

**Import button label:** `"Import (N records)"` where N = creates + updates.

### 4.5 Step 4 — Execute widget

Runs ACT via `ImportWorker`. Layout matches the main window output panel.

- `QTextEdit` (read-only, monospace font) for scrolling output
- Progress bar (indeterminate) while running
- On completion: show summary block in output; enable Close and View Report
- `QPushButton("View Report")` — opens the import report log file using
  `QDesktopServices.openUrl`
- `QPushButton("Close")` — closes the dialog

### 4.6 Navigation rules

| From | To | Condition |
|---|---|---|
| Step 1 → Step 2 | Next | File selected + entity fields loaded |
| Step 2 → Step 3 | Next | At least one field mapped |
| Step 3 → Step 4 | Import | At least one CREATE or UPDATE in plan |
| Step 4 | Close | Import complete |
| Any → previous | Back | Always allowed (except during active operations) |

Back is disabled during active operations (CHECK, ACT).

---

## Task 5 — Update `ui/main_window.py`

Add the Import Data button to the bottom bar. Make only the minimal changes
needed.

### 5a — Import button

In `_build_ui()`, add to `bottom_layout` between `self.docgen_btn` and
`bottom_layout.addStretch()`:

```python
self.import_btn = QPushButton("Import Data")
self.import_btn.clicked.connect(self._on_import_data)
bottom_layout.addWidget(self.import_btn)
```

### 5b — Button state

In `_update_button_states()`, add:

```python
self.import_btn.setEnabled(
    self.state.instance is not None and not in_progress
)
```

### 5c — Handler

```python
def _on_import_data(self) -> None:
    """Open the import wizard dialog."""
    if not self.state.instance:
        return

    from espo_impl.core.api_client import EspoAdminClient
    from espo_impl.ui.import_dialog import ImportDialog

    client = EspoAdminClient(self.state.instance)
    dialog = ImportDialog(self.state.instance, client, self)
    dialog.exec()
```

---

## Implementation Order

1. Task 1 — api_client.py additions
2. Task 2 — import_manager.py
3. Task 3 — import_worker.py
4. Task 4 — import_dialog.py
5. Task 5 — main_window.py

Confirm with me after Task 2 and after Task 4 before proceeding.

---

## Important Notes

### Field list caching
The entity field list (from `get_entity_field_list`) is fetched once in
Step 1 and reused throughout the wizard. Do not re-fetch it on each
step transition.

### "name" field on Person entities
EspoCRM's Contact entity (Person type) has `name` as a computed field
built from `firstName` and `lastName`. Do not map JSON fields to `name`
directly — the auto-mapping alias table maps "Contact Name" to `name`
only as a fallback; in practice users should map to `firstName`/`lastName`
separately. The tool does not perform automatic name splitting.

### Empty value handling
When applying field_mapping to a source record, skip any JSON field whose
value is an empty string `""` even if it is mapped. Do not send empty
strings to EspoCRM.

### Boolean fixed values
Fixed-value field values are entered as strings in the UI. When building
the EspoCRM payload, convert `"true"` / `"false"` (case-insensitive) to
Python booleans `True` / `False` before sending.

### CHECK is re-run on ACT
The `execute()` method in `ImportManager` does NOT re-run the CHECK logic.
It uses the `RecordPlan` objects produced by `check()`. This means the
wizard's plan can become stale if EspoCRM data changes between Step 3 and
Step 4 — this is acceptable for v1.

### Records array detection
The JSON file may use any top-level key name for the records array. Detect
it by looking for the first top-level key whose value is a list of dicts
each containing a `"fields"` key.

### Error isolation
Errors on individual records during ACT must not abort the import. Log each
error and continue to the next record.

### Report file location
Write the import report to the instance's `reports_dir` (same as run
reports). Use the filename pattern: `import_{timestamp}.log` and
`import_{timestamp}.json`. Reuse or extend `Reporter` if practical;
otherwise write the report directly in `ImportManager`.
