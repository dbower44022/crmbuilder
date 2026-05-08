# CLAUDE-CODE-PROMPT-v2-ui-v0.2-A-foundation-refactor

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2
**Slice:** A (1 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-H (UI v0.1 closeout — 264 v2 tests passing as of SES-005)

## Purpose

This is the first of six slices that build the CRMBuilder v2 desktop UI v0.2 per the companion PRD and implementation plan. This prompt builds slice **A — Foundation refactor**.

Slice A produces three deliverables, layered:

1. **Planning records.** The conversation that produced the v0.2 PRD and plan is captured in the v2 database — SES-006 (the planning session), DEC-026 through DEC-031 (the six architectural decisions made during that conversation), six `decided_in` references from SES-006 to those decisions, and a status update reflecting that v0.2 is now in build. Per DEC-025, SES-006's `conversation_reference` is descriptive text and `topics_covered` opens with the verbatim seed prompt.

2. **Reusable widgets and dialog base classes.** A new `crmbuilder_v2.ui.widgets` subpackage with three widgets — `DateField`, `ReferencesSection`, `HierarchicalEntityPicker`. A new `crmbuilder_v2.ui.base.crud_dialog` module housing `EntityCrudDialog` and `EntityCrudDeleteDialog`. A new `crmbuilder_v2.ui.base.versioned_replace_dialog` module housing the foundation of `VersionedReplaceDialog` (full implementation lands in slice E; the file is created with the class skeleton in this slice so subsequent slices can import without further scaffolding).

3. **Decisions migration.** The existing v0.1 decisions create / edit / delete dialogs are migrated to use the new base classes and widgets. v0.1's visible behavior is preserved exactly — DEC-NNN format validation, Active/Superseded/Withdrawn status dropdown, supersedes/superseded_by handling, the inline error UX, the soft-delete confirmation flow. The plain-text Decision Date input is replaced by `DateField`. The bespoke inbound-reference rendering on the Decisions detail pane is replaced by `ReferencesSection`. v0.1's existing 264 tests are the regression net.

After this slice, the foundation is in place and slices B through F build on it. This slice does NOT add any new entity write surface, charter/status replace flow, show-deleted toggle, or QTreeView for topics — those land in their own slices.

## Project context

UI v0.1 shipped 05-09-26 (SES-005, status v0.6, phase `"v0.1 complete"`). The v2 stack is end-to-end: SQLite + Alembic + access layer + REST API + MCP server + PySide6 UI. 264 v2 tests pass.

The v0.2 planning conversation (SES-006, this slice's planning record) confirmed v0.2's frame as "complete the write surface" — full CRUD for Risks, Planning Items, Topics; replace + history for Charter and Status; reference rendering everywhere; show-deleted toggle on Decisions; calendar widget on date inputs. Sessions and References are deferred to v0.3. The full styling pass per DEC-024 is deferred again to v0.3.

The v0.2 architecture introduces a schema-driven dialog framework: `EntityCrudDialog` is parameterized by a per-entity field schema (label, widget type, required flag, vocab source, regex). v0.1's decisions dialogs become the first user of the base. Subsequent slices instantiate the base for risks (B), planning items (C), topics (D). Charter and Status get a separate `VersionedReplaceDialog` base (foundation in this slice; full implementation in E).

Because v0.2 does not add any new transport, lifecycle, or refresh mechanics — those are settled at v0.1 — slice A's risk surface is bounded to the dialog refactor. v0.1's 264 tests are the regression net.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational:
   - `uv run crmbuilder-v2-api &` to start the API in the background.
   - `curl http://127.0.0.1:8765/health` should return 200.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 264 tests passing.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay particular attention to the "CRMBuilder v2 — Methodology Rearchitecture" section.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — the requirements you are implementing. All slices.
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — the slice breakdown. Pay particular attention to **Step A** in section 4.
4. **Tier 2 orientation** (per DEC-011), via either MCP or the JSON snapshots:
   - Current charter
   - Current status (v0.6, `"v0.1 complete"`)
   - SES-005 (most recent prior session, the v0.1 build closeout)
   - DEC-018 through DEC-024 (v0.1's architectural decisions, still in force)
   - DEC-025 (transcript-capture deferral and seed-prompt convention — load-bearing for SES-006's `topics_covered`)
5. v0.1's existing decisions dialog and panel code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_create.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_edit.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_delete.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/exceptions.py` — `ValidationError.field_errors()`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — existing decision write methods
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — to confirm the dialog refresh-on-success path doesn't need changes
6. Storage system surfaces (read-only — do not modify):
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — vocabularies for all entities
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — Decision SQLAlchemy model
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — `DecisionCreateIn`, `DecisionUpdateIn`

## Step 1 — Write planning records to the database

Capture the planning conversation that produced the companion PRD and plan. Write these records via the running REST API (or via MCP if your client is connected — both reach the same database).

### Decisions (six new records, DEC-026 through DEC-031)

Each decision below should be written as a `POST /decisions` call. All have `decision_date: "05-08-26"` and `status: "Active"`. Use the verbatim body text in **Appendix A** below for `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences`. Do not paraphrase or summarize.

- **DEC-026** — v0.2 frame: complete the write surface, with calendar widget and show-deleted toggle as carve-outs
- **DEC-027** — v0.2 entity scope: full CRUD for Risks, Planning Items, Topics; replace + history for Charter and Status; Sessions and References deferred to v0.3
- **DEC-028** — Extract shared dialog base classes; decisions becomes the first user
- **DEC-029** — Charter/Status replace via raw JSON editor with Validate button + Make Current affordance
- **DEC-030** — Topics master panel switches to QTreeView; parent_topic uses a reusable HierarchicalEntityPicker widget
- **DEC-031** — Reference rendering generalized via shared ReferencesSection widget on every detail pane

### Session (one new record, SES-006)

Per DEC-025, the `conversation_reference` is descriptive text identifying the conversation by its outputs (no transcript), and `topics_covered` opens with the verbatim seed prompt.

Write a `POST /sessions` call with:

- `identifier: "SES-006"`
- `title: "UI v0.2 planning"`
- `session_date: "05-08-26"`
- `status: "Complete"`
- `conversation_reference`: `"Claude.ai planning conversation that produced ui-PRD-v0.2.md, ui-v0.2-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.2 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`
- `topics_covered`: the text in **Appendix B** below verbatim. It opens with the seed prompt rendered as `Seed prompt: "<the task statement>"` per DEC-025, followed by a structured summary of the eight architectural questions discussed.
- `summary`: the text in **Appendix C** below.
- `artifacts_produced`: the text in **Appendix D** below.
- `in_flight_at_end`: `""`.

### References (six new records)

For each of DEC-026 through DEC-031, write a `POST /references` call:

- `source_type: "session"`
- `source_id: "SES-006"`
- `target_type: "decision"`
- `target_id: "DEC-NNN"` (one per decision)
- `relationship: "decided_in"`

### Status update

Append a new status version via `PUT /status`. The new payload should:

- Set `phase` to `"v0.2 in build"`.
- Set `sub_step` to `"Slice A foundation refactor in progress: extracting EntityCrudDialog and VersionedReplaceDialog base classes, adding widgets/ subpackage with DateField + ReferencesSection + HierarchicalEntityPicker, migrating decisions dialogs to the new base."`.
- Set `active_work` to `"Slice A — foundation refactor (this conversation's execution work)."`.
- Update `live_inventory.in_database` counts to reflect: 30 decisions (DEC-001 through DEC-031), 6 sessions (SES-001 through SES-006), charter unchanged, 7+ status versions, 30 references.
- Add a new field `pending.ui_v0_2_remaining_slices` listing slices B through F per the implementation plan.
- Preserve everything else from status v0.6 that remains accurate.
- Set `version_label` to `"0.7"`.
- Update `metadata.Last Updated` to today's date.

### Verify

After the writes:

- The `db-export/` directory should have updated `decisions.json`, `sessions.json`, `references.json`, `status.json`, and `change_log.json` files. Inspect them and confirm the expected records are present.
- Commit all changes under `db-export/` in a single commit:

```
v2: ui v0.2 planning records — SES-006, DEC-026 through DEC-031
```

## Step 2 — Reusable widgets

Create the new `widgets/` subpackage and its three widgets.

### `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/__init__.py`

Module docstring only. Export the three widget classes for convenient import:

```python
"""Reusable UI widgets used by panels and dialogs."""
from crmbuilder_v2.ui.widgets.date_field import DateField
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker

__all__ = ["DateField", "ReferencesSection", "HierarchicalEntityPicker"]
```

### `widgets/date_field.py`

```python
class DateField(QWidget):
    """QDateEdit wrapper configured for MM-DD-YY round-tripping.

    Round-trips the MM-DD-YY string format the v2 access layer expects.
    Calendar popup is enabled. Default value is today's date on a fresh
    construction; pre-populates from a string via `set_date(text)`.
    """

    def __init__(self, parent: QWidget | None = None) -> None: ...

    def date_text(self) -> str:
        """Return the current date as MM-DD-YY."""

    def set_date(self, text: str) -> None:
        """Pre-populate from MM-DD-YY string. Empty string sets to today."""
```

Implementation notes:
- Wraps `QDateEdit` with `setCalendarPopup(True)`.
- `setDisplayFormat("MM-dd-yy")`.
- `set_date` parses MM-DD-YY (two-digit year). Two-digit year should map to 2000+yy — the v2 dates are all in the 2020s, so the simple "+2000" approach is fine. If `text` is empty, default to today.
- `date_text` returns the current date formatted as MM-DD-YY (zero-padded).

### `widgets/references_section.py`

```python
class ReferencesSection(QWidget):
    """Renders inbound and outbound references for an entity.

    Constructor takes the storage client, entity_type (e.g., 'decision'),
    and identifier (e.g., 'DEC-018'). On construction, fires a worker that
    fetches references where the source matches (outbound) and where the
    target matches (inbound).

    Renders two grouped sections (Inbound, Outbound), each grouped by
    relationship type with a count header. Empty sections render '(none)'.

    Emits navigate_requested(entity_type: str, identifier: str) when the
    user clicks any reference link.
    """

    navigate_requested = Signal(str, str)

    def __init__(
        self,
        client: StorageClient,
        entity_type: str,
        identifier: str,
        *,
        exclude_relationships: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None: ...
```

Implementation notes:

- Layout: a vertical layout with a "References" header label, then a "Loading..." status label that swaps to the rendered content when the fetch completes.
- The fetch uses two client calls: `client.list_references(source_type=entity_type, source_id=identifier)` and `client.list_references(target_type=entity_type, target_id=identifier)`. If those exact methods don't exist on the v0.1 client, extend `client.py` to expose `list_references(**filters)` that maps to `GET /references` with query parameters.
- Render shape: see PRD §4.6 for the visual layout. Inbound and Outbound get their own labeled blocks with counts. Within each block, group by `relationship` and render a sub-header with count, then per-row `{target_type} {target_id} — {target_title}` (or source for outbound), styled as a clickable link.
- For each link row, connecting `clicked` to a slot that emits `navigate_requested(target_type, target_id)`.
- `exclude_relationships` filters out specific relationship types from the rendered output. Used by the Decisions detail pane to suppress the outbound `supersedes` reference (which is already shown as a top-level field).
- Empty inbound AND empty outbound: render a single "(none)" placeholder under the References header.

### `widgets/hierarchical_picker.py`

```python
class HierarchicalEntityPicker(QDialog):
    """Modal tree picker for selecting an entity from a hierarchy.

    Used for parent_topic and (future) other hierarchical entity selects.
    The constructor takes a list of nodes (each with id, label, and
    optional parent_id) and an optional 'selectable predicate' callable
    that returns False for nodes that should be non-selectable
    (e.g., the topic being edited and its descendants — cycle prevention).

    Renders a QTreeView with expand/collapse. The user clicks a node and
    OK to confirm, or 'No selection' to choose None, or Cancel to dismiss
    without changing anything.
    """

    @dataclass
    class Node:
        id: str        # the value used as the field's stored value
        label: str     # what's displayed in the tree
        parent_id: str | None = None

    def __init__(
        self,
        nodes: list[Node],
        *,
        selectable: Callable[[Node], bool] | None = None,
        title: str = "Select",
        current_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None: ...

    def selected_id(self) -> str | None:
        """The selected node's id after .accept(); None if 'No selection'
        was chosen or the dialog was cancelled.
        """
```

Implementation notes:
- Builds a `QStandardItemModel` from the flat node list, organizing by `parent_id`.
- Non-selectable nodes (per the predicate) are still visible (so the user understands the hierarchy) but rendered slightly grayed; clicking them does not enable OK.
- If `current_id` is provided, the tree opens scrolled to and selecting that node.
- An explicit "No selection" button (alongside OK and Cancel) clears the choice and accepts.
- O(N) construction is fine; O(N²) on N=1000 would be a problem but topics are far below that scale.

### Tests

Create `tests/crmbuilder_v2/ui/widgets/__init__.py` (empty) and these test files:

#### `tests/crmbuilder_v2/ui/widgets/test_date_field.py`

- Construction defaults to today's date; `date_text()` returns today as MM-DD-YY.
- `set_date("05-08-26")` followed by `date_text()` returns `"05-08-26"`.
- `set_date("")` resets to today.
- The internal `QDateEdit`'s calendar popup is enabled.

#### `tests/crmbuilder_v2/ui/widgets/test_references_section.py`

- Construction with stub client and entity ('decision', 'DEC-001') fires the inbound and outbound fetches.
- Renders inbound and outbound counts correctly.
- Click on a link row emits `navigate_requested(entity_type, identifier)` with the target's type and id.
- Empty result renders "(none)" placeholder.
- `exclude_relationships={"supersedes"}` filters out outbound supersedes references.

#### `tests/crmbuilder_v2/ui/widgets/test_hierarchical_picker.py`

- Construction with three nodes (root + two children) renders a tree with the root expanded.
- Selecting a child and clicking OK; `selected_id()` returns the child's id.
- "No selection" button accepts with `selected_id() is None`.
- Cancel rejects with `selected_id() is None` and exec returns `Rejected`.
- Selectable predicate that returns False for one node renders it grayed and refuses to enable OK while it's selected.
- `current_id` parameter scrolls and pre-selects.

Use `httpx.MockTransport` and pytest-qt fixtures consistent with v0.1's test patterns.

### Commit

```
v2: ui v0.2 widgets — DateField, ReferencesSection, HierarchicalEntityPicker
```

## Step 3 — Dialog base classes

### `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py`

```python
@dataclass
class FieldSchema:
    """Describes a single form field for an entity CRUD dialog."""
    key: str                                            # API field name
    label: str                                          # UI label
    widget: Literal["line", "text", "combo", "date", "tree_picker"]
    required: bool = False
    placeholder: str | None = None
    vocab: frozenset[str] | None = None                 # for combo
    regex: re.Pattern | None = None                     # client-side
    read_only: bool = False                             # Edit Identifier
    tree_picker_data: Callable[[StorageClient], list[HierarchicalEntityPicker.Node]] | None = None
    tree_picker_filter: Callable[[StorageClient, dict | None], Callable[[Node], bool]] | None = None


class EntityCrudDialog(QDialog):
    """Schema-driven create/edit dialog for an entity.

    Subclasses (or callers) supply:
    * fields: list[FieldSchema] — the form layout.
    * mode: 'create' | 'edit'.
    * client_method: callable that submits (identifier, body) → record.
    * For 'edit': record dict from a fresh API fetch.

    The base handles widget construction, inline error labels, the
    Save/Cancel button bar, the worker submission, the API error
    envelope routing, and partial-PATCH diff (Edit only).

    Subclasses can override post-construction hooks for entity-specific
    polish (e.g., setting tab order, adding side notes).
    """

    def __init__(
        self,
        client: StorageClient,
        fields: list[FieldSchema],
        *,
        mode: Literal["create", "edit"],
        title: str,
        record: dict | None = None,
        parent: QWidget | None = None,
    ) -> None: ...

    def saved_identifier(self) -> str | None:
        """The identifier of the saved record after .accept(); None
        otherwise. On Edit, this is the same as the input identifier.
        """


class EntityCrudDeleteDialog(QDialog):
    """Confirmation dialog for deleting an entity record.

    Constructor takes the storage client, an identifier, a display title,
    and the client delete method. On confirm, calls the method through
    a worker. On success, accepts. ConflictError → ErrorDialog
    (defensive fallback per slice H pattern). NotFoundError → accept
    (treats as 'already deleted'). StorageConnectionError → reject.
    """

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        delete_method: Callable[[str], dict],
        *,
        parent: QWidget | None = None,
    ) -> None: ...
```

Implementation notes:

- Widget construction maps `FieldSchema.widget` to a Qt widget:
  - `"line"` → `QLineEdit`. `placeholder` → `setPlaceholderText`. `read_only` → `setReadOnly(True)` (visual distinction via stylesheet — slightly grayed background).
  - `"text"` → `QPlainTextEdit`, min height ~80px.
  - `"combo"` → `QComboBox` with items from `sorted(field.vocab)`.
  - `"date"` → `DateField` from `widgets/date_field.py`.
  - `"tree_picker"` → A `QPushButton` labeled with the currently-selected option (or "No parent" / placeholder). Clicking opens `HierarchicalEntityPicker` constructed from `field.tree_picker_data(client)` and (if Edit) the filter from `field.tree_picker_filter(client, record)`.

- Each form field has a paired `QLabel` for inline errors. When an error is shown, the label becomes visible with red text (`color: #B22222`) and the input gains a navy outline (consistent with slice H's styling refinement). Clearing happens on the input's `textChanged` / `currentIndexChanged` / `dateChanged` signal.

- Save behavior:
  1. Client-side required-field check on every required field. Empty → inline error "This field is required." on each.
  2. Client-side regex validation on fields with a `regex`. Mismatch → inline error with a field-specific message (the schema can carry an `error_template` later if needed; for v0.2, the message is "Invalid format." or a per-field hardcode in the subclass — concrete text settled by the subclass in slices B/C/D).
  3. On Edit, build a partial body containing only fields whose value changed since the dialog opened. If the body is empty, accept immediately without an API call (mirrors v0.1).
  4. Submit through the worker. Disable Save during submission.
  5. On success: store the identifier on `self._saved_identifier`; call `self.accept()`.
  6. On `ValidationError` with `field_errors()`: populate inline error labels per field; surface field-less errors via `ErrorDialog`. Re-enable Save.
  7. On `ConflictError` with `field` populated (e.g., duplicate identifier): inline error on the corresponding field (likely Identifier).
  8. On `StorageConnectionError`: `self.reject()`. Banner takes over.
  9. On any other `StorageClientError`: `ErrorDialog`. Re-enable Save.

- The base class lives at `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py`. Existing v0.1 `base/list_detail_panel.py` and `base/versioned_panel.py` are unchanged.

### `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py`

For this slice, create the file with a class skeleton — the full implementation lands in slice E. The skeleton lets slice B/C/D import from `base/` without further scaffolding work.

```python
"""Foundation for VersionedReplaceDialog. Full implementation lands in
slice E (charter and status replace flows). This file exists in slice A
so the base/ package is laid out cleanly.
"""

from typing import Callable
from PySide6.QtWidgets import QDialog, QWidget


class VersionedReplaceDialog(QDialog):
    """Skeleton — full implementation lands in slice E.

    Will house the JSON payload editor with Validate button for
    versioned-replace entities (charter, status). Constructor takes
    the current payload (dict), a save callback, and a parent widget.
    """

    def __init__(
        self,
        current_payload: dict,
        save_callback: Callable[[dict], dict],
        *,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Slice E will fill this in.
        raise NotImplementedError("Full implementation in slice E.")
```

### Tests

#### `tests/crmbuilder_v2/ui/test_crud_dialog_base.py` (new)

- Construction with a minimal field schema (one required QLineEdit) renders the form correctly.
- `mode="create"`: empty required field → click Save → inline error appears, no API call made.
- `mode="create"`: filled form → click Save → worker fires; success accepts the dialog with `saved_identifier` set.
- `mode="edit"`: pre-population from the record dict.
- `mode="edit"`: identifier field is read-only.
- `mode="edit"`: no changes → click Save → dialog accepts without an API call.
- `mode="edit"`: one changed field → body contains only that field.
- `ValidationError` with `field_errors()` populates inline errors.
- `ConflictError` with explicit field surfaces inline.
- `StorageConnectionError` rejects the dialog.
- Other `StorageClientError` opens `ErrorDialog`, dialog stays open.
- Combo widget renders sorted vocab items.
- Date widget round-trips MM-DD-YY.

#### Skeleton test for VersionedReplaceDialog

`tests/crmbuilder_v2/ui/test_versioned_replace_dialog_base.py` (new):

- One test that imports the class and asserts that calling the constructor raises `NotImplementedError`. (The full test suite lands in slice E.)

### Commit

```
v2: ui v0.2 — EntityCrudDialog and EntityCrudDeleteDialog base classes
```

## Step 4 — Migrate decisions dialogs to the new base

This is the regression-sensitive step. v0.1's existing 264 tests are the formal regression net.

### `dialogs/decision_create.py`

Replace the existing concrete dialog with a thin subclass (or wrapper function) that:

1. Defines the decisions field schema as a module-level constant:

```python
_DECISION_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="identifier", label="Identifier", widget="line",
        required=True, placeholder="DEC-NNN",
        regex=re.compile(r"^DEC-\d{3,}$"),
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(
        key="decision_date", label="Decision Date", widget="date",
        required=True,
    ),
    FieldSchema(
        key="status", label="Status", widget="combo",
        required=True, vocab=DECISION_STATUSES,
    ),
    FieldSchema(key="context", label="Context", widget="text"),
    FieldSchema(key="decision", label="Decision", widget="text"),
    FieldSchema(key="rationale", label="Rationale", widget="text"),
    FieldSchema(key="alternatives_considered", label="Alternatives Considered", widget="text"),
    FieldSchema(key="consequences", label="Consequences", widget="text"),
    FieldSchema(key="supersedes", label="Supersedes", widget="line", placeholder="DEC-NNN or empty"),
    FieldSchema(key="superseded_by", label="Superseded By", widget="line", placeholder="DEC-NNN or empty"),
]
```

2. Subclasses or wraps `EntityCrudDialog`:

```python
class DecisionCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            _DECISION_FIELDS,
            mode="create",
            title="New Decision",
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()
```

The Identifier field's regex (`^DEC-\d{3,}$`) is the v0.1 slice H client-side validation. The Decision Date field's regex is removed because the `DateField` widget enforces format by construction.

### `dialogs/decision_edit.py`

```python
class DecisionEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            _decision_edit_fields(),  # identifier read-only
            mode="edit",
            title=f"Edit {record['identifier']}",
            record=record,
            parent=parent,
        )
```

`_decision_edit_fields()` returns a copy of `_DECISION_FIELDS` with the identifier field's `read_only=True`. The supersedes/superseded_by partial-PATCH semantics (empty string clears, None doesn't touch) are inherited from the base class — no special handling needed in the subclass.

### `dialogs/decision_delete.py`

```python
class DecisionDeleteDialog(EntityCrudDeleteDialog):
    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            identifier,
            title,
            client.delete_decision,
            parent=parent,
        )
```

The slice H ConflictError-as-defensive-fallback behavior continues — `EntityCrudDeleteDialog` routes ConflictError to `ErrorDialog`. The base class also handles NotFoundError as "already deleted, accept."

### `panels/decisions.py` updates

Two changes:

1. **Replace the bespoke inbound-reference rendering with `ReferencesSection`.** v0.1's slice D added rendering of inbound references on the Decisions detail pane. Locate the rendering code (likely in a method on the panel called from `render_detail`) and replace it with:

```python
references_section = ReferencesSection(
    self._client,
    "decision",
    record["identifier"],
    exclude_relationships={"supersedes"},  # already shown as top-level field
    parent=self,
)
references_section.navigate_requested.connect(self.navigate_requested)
```

The widget is appended to the detail pane layout in the same position as the v0.1 inbound-references rendering. The existing top-level Supersedes/Superseded By fields are not removed — they continue to show as direct columns.

2. **No other changes to the Decisions panel in this slice.** Show-deleted toggle is slice F.

### Tests

#### Existing test files updated

The existing test files are kept but their test bodies are refactored to assert behavior against the new base class:

- `tests/crmbuilder_v2/ui/test_decision_create_dialog.py` — same tests, but the construction call shape may change slightly (the `EntityCrudDialog` signature). The behavior tested is unchanged.
- `tests/crmbuilder_v2/ui/test_decision_edit_dialog.py` — same.
- `tests/crmbuilder_v2/ui/test_decision_delete_dialog.py` — same.

The DateField replacement may invalidate the existing date-format-error test (the calendar widget makes invalid format unreachable). Replace that test with a positive test: `DateField` round-trips MM-DD-YY correctly, and selecting a date via the calendar emits the expected string.

#### New tests for the migration's new behavior

If the migration introduces any new behavior beyond what v0.1 had (e.g., a different placement of the references section), add a smoke test in `test_decisions_panel_writes.py` covering it.

### Verify

Before the commit:

- `uv run pytest tests/crmbuilder_v2/ -v` should show all v0.1 tests + new framework/widget tests passing. Estimated 290+ passing.
- Manually launch `uv run crmbuilder-v2-ui`; verify:
  - Decisions panel renders the same as v0.1.
  - "New Decision" button opens the create dialog with all 11 fields, the same status dropdown values, and a calendar widget on Decision Date.
  - Filling the form and clicking Save creates the record.
  - Editing a decision opens with values pre-populated and identifier read-only.
  - Deleting works as v0.1 did.
  - Inline error rendering on validation failures still works.
  - The Decisions detail pane shows inbound and outbound references via the new `ReferencesSection` (the supersedes outbound is suppressed, so it should look mostly the same as v0.1 visually).

### Commit

```
v2: ui v0.2 — migrate decisions dialogs to shared base + ReferencesSection
```

## Step 5 — Push and report

1. Push all commits: `git push origin main`.
2. Report back to Doug per "Reporting" below.

## Acceptance gates

This slice is complete when all of the following are true:

1. The full v2 test suite passes. v0.1's 264 tests + new framework/widget/migration tests, estimated 290+ passing total.
2. Visible Decisions UI behavior is unchanged from v0.1 (manual verification): create, edit, delete, supersedes clear, error inline rendering, status dropdown vocab, format validation.
3. Decision Date input is now a calendar widget; selecting a date emits the correct MM-DD-YY string to the API.
4. Decisions detail pane renders inbound and outbound references via the `ReferencesSection` widget (the outbound supersedes is suppressed via `exclude_relationships`).
5. SES-006, DEC-026 through DEC-031, six `decided_in` references, and a status v0.7 update are all present in `db-export/`.
6. `widgets/` subpackage is in place with `DateField`, `ReferencesSection`, `HierarchicalEntityPicker` plus their tests.
7. `base/crud_dialog.py` houses `EntityCrudDialog` and `EntityCrudDeleteDialog` with full test coverage.
8. `base/versioned_replace_dialog.py` exists with the class skeleton (raises `NotImplementedError`); slice E will complete it.
9. Three commits on `origin/main`:
   - `v2: ui v0.2 planning records — SES-006, DEC-026 through DEC-031`
   - `v2: ui v0.2 widgets — DateField, ReferencesSection, HierarchicalEntityPicker`
   - `v2: ui v0.2 — EntityCrudDialog and EntityCrudDeleteDialog base classes` (or combined with the migration commit if that's cleaner)
   - `v2: ui v0.2 — migrate decisions dialogs to shared base + ReferencesSection`

## Out of slice

The following are explicitly NOT in scope for this prompt:

- Risks, Planning Items, Topics CRUD — slices B, C, D.
- QTreeView for Topics master panel — slice D.
- Charter/Status replace flow — slice E. This slice creates the `versioned_replace_dialog.py` skeleton only.
- Show-deleted toggle on Decisions — slice F.
- About dialog version bump — slice F.
- SES-007 closeout record — slice F.
- Full styling design pass — deferred to v0.3 per DEC-024.

Resist the urge to "get a head start" on later slices. Each slice has its own review pass.

## Constraints

- **No edits to v1 code or methodology.** v2 work is strictly additive to v1 per DEC-003.
- **No new external dependencies.** PySide6, httpx, pytest-qt are already present.
- **Do not modify the access layer or REST API surface in this slice.** Only the UI changes. (Subsequent slices may make small additive storage-system changes; A is pure UI.)
- **Do not modify `vocab.py`.** Vocabularies are imported, not redefined.
- **Visible Decisions UI behavior must match v0.1 after the migration.** Calendar widget on Decision Date and the unified ReferencesSection are the only allowed visible differences.
- **v0.1's 264 tests are the regression net.** Any test that needs updating to match the new dialog construction signature is fine; any test whose assertion changes meaning is a red flag — surface and ask.
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, stop and surface it rather than choosing silently.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the nine gates above.
- **Files created or modified** — full list, organized by step.
- **Records written** — confirmation that SES-006, DEC-026 through DEC-031, the six references, and the status update all wrote successfully and appear in `db-export/`.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Visual verification** — short description of what was visible when the Decisions surface was exercised after the migration. Note any cosmetic deltas from v0.1.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for the next planning conversation or for slice B onwards.
- **What slice B will need** — anything from A's outputs that B's prompt should know about (e.g., the exact field schema dataclass shape, the exact widget construction patterns, the regression-sensitive parts of decisions.py).

---

## Appendix A — Decision body text (verbatim)

The text below is to be written verbatim into the `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences` fields of each decision record. Multi-line fields are written as-is into the database.

### DEC-026 — v0.2 frame: complete the write surface, with calendar widget and show-deleted toggle as carve-outs

**context**

UI v0.1 shipped on 05-09-26 with full create/read/update/delete operations for decisions and read-only views for the other six governance entity types plus the references graph. v0.1's deliberate scope concentrated the architectural pieces (subprocess management, threading, error envelope handling, file-watch refresh, dialog patterns) on a single end-to-end CRUD path; other entities received read-only treatment. The v0.1 PRD anticipated that follow-on work would close the gap and called the workstream v0.2. The candidate backlog from SES-005's `in_flight_at_end` plus open items from the v0.1 build offers three plausible v0.2 framings: complete the write surface (CRUD parity for non-decision entities), polish the read surface (full styling pass + reference rendering everywhere + tree view for topics + small UX upgrades), or a hybrid (write surfaces for two entities + visual pass).

**decision**

v0.2 is framed as "complete the write surface." The primary work is generalizing the v0.1 decisions CRUD pattern to Risks, Planning Items, and Topics, plus a versioned-replace flow with version-history browsing for Charter and Status. Two small carve-outs are folded in because they would otherwise produce a low-leverage v0.3 of grab-bag items: a calendar widget for date inputs (replacing the plain-text MM-DD-YY input on Decisions and applying to all v0.2 dialogs that have date fields), and a "Show deleted" toggle on the Decisions panel toolbar (closing the v0.1 slice H deferred item that left soft-deleted decisions hidden with no UI affordance to surface them). The full styling design pass per DEC-024 is deferred again, to v0.3.

**rationale**

v0.1 proved the architectural pieces on a single CRUD path. Generalizing that path to other entities is the highest-leverage next move: it produces direct daily-use value (no more reaching for `curl` to record a risk or a planning item), the work is largely additive on top of patterns already validated, and the file-watch refresh mechanism plus error envelope handling carry over without new design. Styling, by contrast, is a separate kind of work — slower, more iterative, design-heavy. Doing both at once would make v0.2 a less coherent release and would mean every change to either the dialog code or the visual surface feels like it breaks the other. Deferring styling once more means more weeks of v0.1+v0.2 use to react to before committing to a full visual identity. The carve-outs (calendar widget and show-deleted toggle) are sufficiently small that holding them for v0.3 would produce a v0.3 that is mostly small items, which is its own anti-pattern.

**alternatives_considered**

- "Make the read surface excellent" — full styling pass + reference rendering everywhere + tree view for topics + calendar + show-deleted, with new entity write surfaces deferred to v0.3. Rejected — preserves the gap that "every governance write that isn't a decision still goes through curl or MCP" represents in daily use; the friction is real and immediate. Lower technical risk than the chosen frame, but the value delivered is less proportional to the build cost.
- Hybrid — write surfaces for the two highest-frequency non-decision entities plus the full styling pass plus reference rendering everywhere, with topics CRUD and charter/status replace deferred to v0.3. Rejected — tries to do two qualitatively different kinds of work (build features and design visual identity) in the same release; produces less coherent outcomes on each than doing one kind well.

**consequences**

v0.2 is decomposed into six prompts in the build series. Sessions write surface and References write surface are explicitly out of scope: Sessions because DEC-013/DEC-014 establish them as append-only-by-Claude-only, References because the edge-management UX is a separate design problem that v0.3 takes on as its own focused slice. Calendar widget and show-deleted toggle each get small carve-out treatment within v0.2 rather than being a slice of their own. The full styling pass is deferred again per DEC-024's "v0.2 or later" allowance; v0.3 is now its natural home, with the working v0.1+v0.2 surface to react to.

---

### DEC-027 — v0.2 entity scope: full CRUD for Risks, Planning Items, Topics; replace + history for Charter and Status; Sessions and References deferred to v0.3

**context**

The seven non-decision entity types are not uniform in their write semantics. Risks, Planning Items, and Topics are straightforward CRUD analogues to Decisions — list, detail, Create, Edit, Delete dialogs of the same shape. Charter and Status are versioned-replace: there is no Edit on a version, only "create new version" with history browsing. Sessions are append-only per DEC-013 and written exclusively by Claude at conversation close per DEC-014; they have no UI write surface in any v2 release without first revising those decisions. References are edges in the universal-references graph, not entity records; their create/delete UX involves a relationship-vocabulary picker, source/target selection, and inbound-link cleanup — a focused design conversation rather than an instance of the CRUD pattern.

**decision**

v0.2's write surface covers exactly five entities: Risks, Planning Items, Topics get full create/edit/delete dialogs using a shared CRUD framework. Charter and Status get a versioned-replace flow with version-history browsing including the ability to designate a non-current version as the new current. Sessions are explicitly excluded from the v0.2 write surface as a governance-level boundary, not a UI deferral. References-as-edges is deferred to v0.3 as its own focused slice — relationship vocabulary discoverability, source/target picker UX, and edge-deletion semantics warrant their own design conversation when v0.2 has surfaced what good edge-management UX should look like.

**rationale**

Five entities is the right v0.2 scope. The three CRUD entities (Risks, Planning Items, Topics) share a near-identical dialog shape, so a single CRUD framework written once produces three working write surfaces; the marginal cost beyond the framework itself is small per entity. Charter and Status share a near-identical replace-with-history shape and are handled by a single versioned-replace framework. Topics adds one wrinkle (hierarchical parent_topic field), which motivates a reusable hierarchical picker widget that lands once and serves Topics today plus future methodology entities (process step parents, requirement parents) tomorrow. Sessions are a governance-level exclusion — DEC-013 establishes append-only and DEC-014 establishes Claude-as-writer, so a UI write surface for Sessions is not on the roadmap without revising those decisions. References-as-edges is a different shape entirely; trying to fit it into v0.2's "complete the write surface" frame would either cramp the design or balloon the scope. Its own slice in v0.3 is the principled answer.

**alternatives_considered**

- Include References write surface in v0.2. Rejected — pushes v0.2's design surface up significantly. The reference-edge UX has no clean analogue in the existing CRUD pattern (it's not an entity Create/Edit/Delete; it's a graph-edge picker with two sides and a controlled-vocabulary middle), and the design questions (relationship vocab discoverability when the user doesn't know what relationships exist, what happens to inbound edges when a target is deleted, whether to support multi-edge creation in a single dialog) are heavier than any one CRUD slice. Holding References for v0.3 means it gets a focused design conversation rather than being squeezed into the v0.2 dialog framework.
- Include a "Create Session" UI surface for non-Claude work (in-person meetings, phone calls) while keeping Edit and Delete excluded per the append-only semantics. Rejected — the governance principle in DEC-014 is that v2 sessions are documenting Claude conversations specifically; non-Claude work doesn't produce a v2 session record. Adding a "Create Session" UI surface would partially undo that decision in practice, which is the wrong way to revise it.

**consequences**

The v0.2 build series has one foundation slice (A: framework + widgets), one slice per CRUD entity (B: Risks, C: Planning Items, D: Topics), one slice for versioned-replace + Sessions read-only references (E), and one closeout slice (F: show-deleted + polish + governance). v0.3's scope inherits Sessions write surface as a governance question (revisit DEC-013 and DEC-014 if the need actually surfaces), References write surface as its own focused slice, and the full styling design pass per DEC-024.

---

### DEC-028 — Extract shared dialog base classes; decisions becomes the first user

**context**

UI v0.1's three decisions dialogs (`decision_create.py`, `decision_edit.py`, `decision_delete.py`) are concrete classes with v0.1-specific dialog mechanics — error envelope handling, worker submission pattern, Save/Cancel framing, inline error label management, status-dropdown-from-vocab logic. v0.2 adds three more entities with the same CRUD shape (Risks, Planning Items, Topics) and two more entities with a different shape (versioned-replace for Charter, Status). The v0.1 dialog code is the closest reference; the v0.2 build will produce code that closely resembles it for each new entity.

**decision**

The v0.2 build extracts shared base classes — `EntityCrudDialog` and `EntityCrudDeleteDialog` for the four CRUD entities, and `VersionedReplaceDialog` for the two versioned-replace entities. v0.1's decisions dialogs become the first user of `EntityCrudDialog` / `EntityCrudDeleteDialog` and are migrated as part of slice A. Subsequent slices instantiate the bases for the new entities. The `EntityCrudDialog` is parameterized by a per-entity field schema (a list of FieldSchema dataclasses describing label, widget type, required flag, vocab source, regex). Visible behavior of the migrated decisions dialogs is unchanged from v0.1 except for the calendar widget on Decision Date (per DEC-026's carve-out) and the unified `ReferencesSection` widget on the Decisions detail pane (replacing v0.1's bespoke inbound-reference rendering).

**rationale**

The alternative is per-entity duplicates — keep decisions as-is and write each new entity's dialogs as concrete classes in the v0.1 shape. That would produce four nearly-identical CRUD dialog families, with the shared-but-not-DRY error envelope handling, worker pattern, Save/Cancel framing, and vocab-binding code spread across roughly twenty files. When a bug is fixed in one (or a UX detail like inline error label color is updated), the other three drift unless a maintainer remembers to fan out. The methodology entities planned post-v0.2 (personas, processes, requirements, manual-config items, test specs) would each clone the same pattern again, multiplying the drift surface. Extracting once with decisions as the first user prevents that drift. The premature-abstraction risk is bounded: the base is designed for the four CRUD entities currently in scope, and the methodology entities will evolve the base when they introduce affordances it doesn't have (rich text fields, attachments, multi-entity references). v0.1's existing 264 tests are the regression net for the decisions migration; the refactor risk is real but bounded.

**alternatives_considered**

- Per-entity duplicates. Rejected — produces four-way drift on the dialog mechanics surface, and the methodology entities post-v0.2 multiply that drift further.
- Hybrid: build new entities against a shared base; leave v0.1's decisions dialogs as concrete classes. Rejected — the most ugly long-term option. The codebase ends up with two patterns side-by-side; a fix to the new base doesn't reach decisions; a feature added to decisions doesn't propagate to others. Drift across patterns is the failure mode.

**consequences**

Slice A of the v0.2 build is the foundation refactor: extract base classes, build the widgets, migrate decisions, validate via the 264-test regression net plus new framework tests. Visible Decisions UI behavior is preserved exactly. Slices B, C, D each produce an entity's CRUD dialogs as schema declarations on top of the base — the heavy lifting is done once, and each entity-specific slice becomes a small declarative addition. Charter and Status share the parallel `VersionedReplaceDialog` base, which is intentionally schema-blind (presents JSON, validates JSON, submits JSON) so it serves both entities without a per-entity payload-form definition.

---

### DEC-029 — Charter/Status replace via raw JSON editor with Validate button + Make Current affordance

**context**

Charter and Status are versioned-replace entities. Each version's payload is a JSON dict whose schema is loose by construction — both payloads have known top-level keys (e.g., status's `phase`, `active_work`, `live_inventory`, `reading_order_for_new_sessions`, etc.), but the schema is not formally constrained at the storage layer and evolves with the project (methodology phases will add new keys to status; charter will gain new sections as the project matures). The v0.1 PRD §2 deferred the replace flow to v0.2 explicitly: "Charter and Status replace flows ... v0.1 UI does not expose that capability." v0.2's question is what shape the replace dialog takes — a raw JSON editor, a structured form bound to the known top-level keys, or a hybrid that surfaces known fields with a JSON fallback for the rest.

**decision**

The Charter/Status replace dialog uses a raw JSON text editor with a Validate button. The editor is a `QPlainTextEdit` with monospace font, ~600px tall, optionally with a `QSyntaxHighlighter` for JSON tokens if Qt makes that easy. Pre-populated with the current version's payload as pretty-printed JSON. Validate parses the editor text as JSON; valid → "Valid JSON" status, Save enabled; invalid → "Invalid: ..." status with the parse-error position. Save runs Validate first; on valid JSON, sends the parsed payload as a new version through the appropriate client method. Additionally, the panel's version-history list pane (already present from v0.1) gains a "Make Current" affordance on each non-current version row — clicking opens a confirmation modal; confirming flips `is_current` to the selected version. Versions remain append-only (no delete-version operation), but Make Current allows reverting to a prior version when a new version turns out to be wrong.

**rationale**

The structured-form alternative is significantly more complex to build and maintain. Charter and Status have different top-level shapes, so each would need its own form definition; the form would need updating whenever the payload schema evolves; and the form would still need a JSON-fallback escape hatch for unusual edits, doubling the implementation. The hybrid alternative (structured form for known fields, JSON fallback for the rest) carries the cost of both options. The raw JSON editor is the cheapest implementation that gives 90% of the safety: with a Validate button checking syntax client-side and the access layer's existing Pydantic validation rejecting structurally-wrong payloads, the worst-case typo (a key name spelled wrong) surfaces as an API validation error returned through the existing error envelope and shown in a generic ErrorDialog. The user fixes and resaves. The single-developer single-payload-shape-per-entity nature of v2 makes this acceptable; if the friction becomes significant in practice, v0.3 can introduce a structured form with the working v0.2 surface to react to. Make Current is included because it is the natural recovery move when a new version turns out to be wrong; without it, the only path back to a prior version is through MCP or curl, which is the friction the UI exists to remove.

**alternatives_considered**

- Structured form bound to a known schema. Rejected — significantly more complex to build, fragile to schema evolution, and the marginal usability gain over a JSON editor with Validate is small for a single-developer project where edits are infrequent and the user knows the payload shape.
- Hybrid (structured form for known top-level fields with a JSON fallback for unusual edits). Rejected — pays the cost of both options; the schema-detection-from-current-version logic has its own failure modes; the build cost is significant.
- Defer Make Current to v0.3 (replace creates a new version; reverting requires curl or MCP). Rejected — a small affordance with clear value; the access layer already supports flipping `is_current`; building it now matches v0.2's "complete the write surface" frame.
- Defer Make Current to v0.3 only if the access layer doesn't already support it. The access layer does support it, so the answer is to build the surface now.

**consequences**

Slice E of the v0.2 build implements `VersionedReplaceDialog` (full implementation; the file is created in slice A as a skeleton so subsequent slices can import without further scaffolding). Charter and Status panels get a New Version button in the toolbar and a Make Current affordance on each non-current version in the version-history list. v0.3 is a natural home for richer payload-editing features (diff view, structured form layered on, history-comparison rendering) if the working v0.2 surface motivates them.

---

### DEC-030 — Topics master panel switches to QTreeView; parent_topic uses a reusable HierarchicalEntityPicker widget

**context**

UI v0.1's Topics panel (slice E) renders the topics list as a flat `QTableView` with name-prefix indentation per hierarchy level. This works for the small topic counts v2 currently has but does not naturally express the parent-child structure in the data, and editing a topic's parent in a CRUD dialog has no good widget — a `QComboBox` with indented-flat items doesn't scale and doesn't visually express the hierarchy. The v0.1 backlog from SES-005 calls out "QTreeView for Topics" as a v0.2 candidate. Separately, the methodology entities planned for post-v0.2 work (process steps with parent steps, requirement parents) will introduce more hierarchical fields; the question is whether to design the hierarchy widget once for general reuse or per-feature each time.

**decision**

The Topics master panel switches from the indented `QTableView` to a `QTreeView` backed by a `QStandardItemModel`. Roots are top-level topics; children nest under parents via the `parent_topic_id` field. Single-row selection emits the existing `selection_changed` signal so the detail-pane behavior is unchanged. For the parent_topic field in the Topics CRUD dialog, a new reusable `HierarchicalEntityPicker` widget is added under `crmbuilder_v2.ui.widgets/`. The widget is a modal dialog containing a `QTreeView` of all available nodes, with a "selectable predicate" callback that filters out non-selectable nodes (used for cycle prevention on Edit — the topic itself and its descendants are non-selectable). The widget is general enough to serve future hierarchical fields (methodology entity parents) without redesign.

**rationale**

A `QTreeView` is the unambiguously right shape for hierarchical data display; the only tradeoff is implementation work versus the existing flat-with-indentation rendering. Building it once for Topics and using a reusable picker pattern that serves future entities means the implementation cost is paid once and the visual affordance is consistent across v2 as it grows. Cycle prevention on the picker side is structural correctness — without it, the user could create a cycle that the access layer rejects with a confusing error; with the picker filter, the cycle path is non-clickable and the user understands they can't choose it.

**alternatives_considered**

- Keep the flat-with-indentation `QTableView` for Topics and use an indented-flat `QComboBox` for the parent_topic field in the dialog. Rejected — visually inconsistent, doesn't scale, and the methodology entities post-v0.2 would need their own hierarchical-field solution that this decision has to design anyway.
- Build the QTreeView for Topics but use a typeahead text field for the parent_topic dialog input. Rejected — typeahead is fast for someone who knows the parent's name and ambiguous when names collide; for a single-developer dataset where the user often doesn't remember a parent's exact name, the visual tree picker is the better answer.
- Use a tree picker but build it specifically for Topics (not reusable). Rejected — the methodology entities post-v0.2 introduce more hierarchical fields; building twice is more work than building once with reuse in mind.

**consequences**

Slice D of the v0.2 build does the QTreeView swap and builds the `HierarchicalEntityPicker` widget. The widget lives at `crmbuilder_v2.ui.widgets.hierarchical_picker.HierarchicalEntityPicker`; topics is its first user. The `EntityCrudDialog` field-schema (per DEC-028) supports a `widget="tree_picker"` shape that instantiates the picker with the appropriate node-list-fetch and selectable-predicate callbacks. Methodology entities post-v0.2 inherit the picker for their hierarchical fields without redesign.

---

### DEC-031 — Reference rendering generalized via shared ReferencesSection widget on every detail pane

**context**

UI v0.1 slice D added rich rendering of inbound references on the Decisions detail pane: rows like "Decided in: SES-002" rendered as clickable text that navigates to the referenced session. The v0.1 backlog explicitly calls for generalizing this to every detail pane: "should generalize to Sessions, Risks, Charter, Status, Topics, Planning Items, and References themselves." v0.1's bespoke implementation is on the Decisions detail pane only; v0.2's question is whether to extract a shared widget from that implementation, what direction(s) to display, whether to group, and whether to support filtering by relationship type.

**decision**

A new `ReferencesSection` widget under `crmbuilder_v2.ui.widgets/` renders inbound and outbound references for a given entity, both directions in two clearly-labeled blocks, each grouped by relationship type with a count header. Empty sections render a "(none)" placeholder so the layout is consistent. Filtering by relationship type is deferred to v0.3 — v0.2's reference volume isn't pressuring readability, and the dropdown UI surface is best designed against a real "this is unreadable" moment rather than in the abstract. The widget lands on every entity's detail pane: Decisions (replacing v0.1's bespoke rendering), Sessions, Risks, Planning Items, Topics, Charter, Status. The References panel itself (the entity-list view of edges) keeps its v0.1 list-only treatment with no detail pane — an edge has nothing more to show beyond its source/relationship/target. The widget supports an `exclude_relationships` constructor parameter for the case where a relationship is already shown elsewhere on the detail pane (Decisions has top-level Supersedes/Superseded By fields; the outbound `supersedes` relationship is suppressed via this parameter to avoid redundancy).

**rationale**

Both directions are shown on every entity to keep the layout uniform — direction asymmetry varies per entity (Sessions are mostly source-side; Charter/Status are inbound-light), and a uniform shape reads better than a per-entity layout choice. Grouping by relationship type with counts scales: when reference volume grows past five per record, ungrouped flat lists become hard to scan. The empty-state placeholder ensures consistent layout. Filtering is deferred because the volume hasn't pressured it yet and the UI cost (a dropdown on every detail pane) is real; v0.3 adds it if real friction surfaces.

**alternatives_considered**

- Inbound only (matching the v0.1 Decisions implementation). Rejected — non-uniform across entities; some entities have substantive outbound references (sessions especially) that would be invisible on their detail pane.
- Flat list, no grouping. Rejected — fine at low volumes, hard to scan past five references per record.
- Filterable by relationship type in v0.2. Rejected — UI surface and complexity for a problem we don't have yet.
- Build the widget into each panel separately (per-entity reference rendering). Rejected — per-entity drift on rendering details is the failure mode; the widget exists once and is consumed by each panel.

**consequences**

Slice A of the v0.2 build creates the `ReferencesSection` widget under `widgets/` and migrates the Decisions detail pane to use it (replacing v0.1's bespoke rendering, with the supersedes outbound suppressed). Subsequent slices add the widget to each entity's detail pane: B (Risks), C (Planning Items), D (Topics), E (Charter, Status, Sessions). The widget supports the `navigate_requested(entity_type, identifier)` signal so click-to-navigate works uniformly on every detail pane. v0.3 is the natural place to add filtering or pagination if reference volume grows past what flat grouped lists handle gracefully.

---

## Appendix B — SES-006 `topics_covered` (verbatim)

The text below is the verbatim content for the `topics_covered` field of SES-006. Per DEC-025, the field opens with the seed prompt rendered as `Seed prompt: "..."` and is followed by a structured summary of the architectural questions discussed.

```
Seed prompt: "Plan v0.2 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables: (1) PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md — intent, scope, acceptance criteria, error handling matrix, open questions; (2) PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md — slice breakdown with deliverables and acceptance gates per slice; (3) Execution prompts under PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-{A..*}-*.md — one per implementation slice. The conversation that produces these deliverables is the v0.2 planning session and will be captured as SES-006 at the conversation's close."

The planning conversation worked through eight architectural questions in order:

1. Release shape — what kind of release v0.2 is. Three theses considered: complete the write surface (CRUD parity for non-decision entities), polish the read surface (full styling pass + reference rendering everywhere), or hybrid (writes for two entities + visual pass). Resolved as Thesis A (complete the write surface) with two carve-outs (calendar widget on date inputs, "Show deleted" toggle on Decisions). The full styling design pass per DEC-024 is deferred again, to v0.3.

2. Entity scope — which entities get which shape of write affordance. Resolved: Risks, Planning Items, Topics get full CRUD using a shared CRUD framework; Charter and Status get a versioned-replace flow with version-history browsing including Make Current; Sessions are excluded as a governance-level boundary per DEC-013/DEC-014; References are deferred to v0.3 as their own focused slice.

3. Dialog architecture — extract shared base classes versus per-entity duplicates. Resolved: extract EntityCrudDialog and EntityCrudDeleteDialog parameterized by a per-entity field schema; v0.1's decisions dialogs become the first user of the base. Charter/Status share a parallel VersionedReplaceDialog base.

4. Charter/Status payload editor + version-history UX. Resolved: raw JSON editor with Validate button, sufficient for v2's loose payload schema and infrequent-edit use case. Make Current affordance on non-current versions is included for v0.2 to support reverting.

5. Topics — tree view in master panel + parent picker in dialog. Resolved: QTreeView replacing the v0.1 indented QTableView. Parent picker is a reusable HierarchicalEntityPicker widget with cycle filtering via a selectable-predicate callback. The widget lands once and serves future hierarchical fields in methodology entities.

6. Reference rendering generalization. Resolved: shared ReferencesSection widget on every detail pane, both inbound and outbound, grouped by relationship type with counts, empty state with "(none)" placeholder, no filtering in v0.2. References-as-edges panel keeps its v0.1 list-only treatment with no detail pane.

7. Small batched items — calendar scope, Show-deleted toggle behavior, vocabulary handling. Resolved: DateField widget wrapping QDateEdit replaces every plain-text date input that v0.2 touches; Show-deleted is a checkbox toggle on the Decisions panel toolbar with strikethrough rendering for deleted rows and a Restore button on the detail pane for soft-deleted records; vocabularies for new entities are imported from access-layer vocab.py (RISK_PROBABILITIES/IMPACTS/STATUSES, PLANNING_ITEM_TYPES/STATUSES — all already present from v0.1).

8. Slice breakdown. Resolved: six slices (A foundation refactor, B Risks CRUD, C Planning Items CRUD, D Topics CRUD + QTreeView + HierarchicalEntityPicker, E Charter and Status replace + Sessions ReferencesSection, F Show-deleted + polish + closeout). A is the prerequisite for all subsequent slices; B/C/D could be parallelized in principle but are sequential in practice for single-developer execution.
```

## Appendix C — SES-006 `summary` (verbatim)

```
The planning conversation worked through the eight architectural questions and produced three artifacts: ui-PRD-v0.2.md (intent, scope, acceptance criteria, error handling matrix, open questions, six forthcoming decisions DEC-026 through DEC-031), ui-v0.2-implementation-plan.md (six-slice breakdown with per-slice deliverables and acceptance gates), and the CLAUDE-CODE-PROMPT-v2-ui-v0.2-A through F prompt series. v0.2 is framed as "complete the write surface" — full create/edit/delete for Risks, Planning Items, and Topics; versioned-replace with history for Charter and Status; standardized reference rendering on every detail pane; calendar widget on date inputs; "Show deleted" toggle on Decisions. Sessions write surface and References write surface are deferred to v0.3 as governance-level and design-conversation-needing items respectively. The full styling pass is deferred again per DEC-024.
```

## Appendix D — SES-006 `artifacts_produced` (verbatim)

```
- PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md
- PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-A-foundation-refactor.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-B-risks-crud.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-C-planning-items-crud.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-D-topics-and-tree-picker.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-E-charter-status-replace.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-F-show-deleted-and-closeout.md
- DEC-026 through DEC-031 (six decision records, written via the v2-ui-v0.2-A foundation-refactor prompt)
- This session record (SES-006)
- Six decided_in references from SES-006 to DEC-026 through DEC-031
- Status update bumping to v0.7 reflecting v0.2 in build, slice A in progress
```
