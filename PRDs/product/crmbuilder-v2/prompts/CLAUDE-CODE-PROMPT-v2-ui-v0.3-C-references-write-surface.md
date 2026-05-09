# CLAUDE-CODE-PROMPT-v2-ui-v0.3-C-references-write-surface

**Last Updated:** 05-09-26 19:15
**Series:** v2-ui-v0.3
**Slice:** C (3 of 5)
**Status:** Ready to execute (after slice B is reported complete)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.3-B (right-click context menus across all existing panels)

## Purpose

This is the third of five slices that build the CRMBuilder v2 desktop UI v0.3. This prompt builds slice **C — References write surface**.

Slice C delivers the full References write surface: a create dialog with source-first cascading filters and strict `RELATIONSHIP_TYPES` vocab compliance, a hard-delete confirmation modal, a new `EntityIdentifierPicker` widget for autocomplete identifier selection, the `New Reference` toolbar button on the References panel, the `Add reference` affordance on every detail pane's `ReferencesSection`, and right-click `Delete reference` on reference rows in both the panel and the section widget.

After this slice, references can be authored end-to-end through the UI from either the References panel (free creation with no pre-population) or any detail pane (creation with the source pre-filled and disabled). Hard-delete is reachable from both surfaces. No edit affordance exists.

This slice does NOT add the Sessions create surface (slice D) or any closeout polish (slice E).

## Project context

Slices A and B landed:
- The `ListDetailPanel` factory refactor with `_create_master_widget` and `_build_context_menu`.
- The Topics panel migrated to the master-widget factory.
- Right-click context menus across all eight existing panels (slice B), including read-only `Go to source` / `Go to target` on References panel rows.
- Planning records SES-008, DEC-032 through DEC-037, six references, PI-NNN, status v0.9.

Per DEC-033, the References write surface combines:

- **Two entry points** — References panel toolbar `New Reference` button, and `Add reference` affordance on every detail pane's `ReferencesSection`.
- **Source-first cascading dialog** — source type → source identifier → relationship kind → target type → target identifier, with each subsequent field's choices filtered by the upstream selections from `RELATIONSHIP_TYPES`.
- **Strict vocab compliance** — invalid combinations are unrepresentable in the dialog. New kinds added to the access layer's `RELATIONSHIP_TYPES` surface in the dialog without UI changes.
- **Autocomplete identifier picker** — editable `QComboBox` + `QCompleter` with `Qt.MatchContains`, populated with `IDENTIFIER — title` items, packaged as a reusable `EntityIdentifierPicker` widget.
- **No edit affordance** — references are immutable identity-wise; "edit" is delete + create.
- **Hard-delete with confirmation modal** showing the edge text. No tombstone, no Show-deleted toggle, no Restore.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `git config user.name` returns `Doug`; `git config user.email` returns `doug@dougbower.com`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice B landed:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py`, `sessions.py`, `risks.py`, `planning_items.py`, `topics.py`, `references.py`, `charter.py`, `status.py` each define `_build_context_menu`.
   - `tests/crmbuilder_v2/ui/test_context_menus.py` exists with action-set assertions per panel.
6. Confirm storage system is operational. Verify-first: `curl -sf http://127.0.0.1:8765/health` — if 200, proceed. If it fails, start the API in the background (`uv run crmbuilder-v2-api &`), wait ~3 seconds, re-check; if still failing, stop and report.
7. Confirm test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Expected ~504 passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` §4.3 (References write surface) and §4.5 (`ReferencesSection` extensions) — the contracts.
3. `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` §4 Step C and §2.10 (cascading-filter framework decision).
4. **Storage layer surfaces** (read-only first; modify only if Step 1 finds gaps):
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `RELATIONSHIP_TYPES` structure. Critical: confirm whether the vocab keys kinds by `(source_type, target_type)` constraints, or only enumerates kinds without typed-source/target validity. The dialog's cascade depends on this.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` — `create_reference`, `delete_reference` (or whatever the access-layer methods are named).
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/references.py` — `POST /references`, `DELETE /references/{id}`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas/references.py` (or wherever the Pydantic models for references live).
5. **UI surfaces to extend**:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` — currently renders inbound/outbound references on detail panes; this slice adds an `Add reference` button and per-row right-click delete.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/__init__.py` — to add the new `EntityIdentifierPicker` to exports.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — `EntityCrudDialog` and `FieldSchema` from v0.2 slice A. Read `FieldSchema` carefully; this slice may extend it.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — to add `create_reference` and `delete_reference` client methods.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — confirm `references` is in the entity-type → signal map; extend if not.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py` — to add `New Reference` toolbar button and extend the slice-B context menu with `Delete reference` and `New reference`.

## Step 0 — Preliminary: `_create_master_widget` docstring capture

Slice A's factory refactor under-specified the `_create_master_widget` contract. The actual landed contract: a subclass may either return a model-less view (the base installs its default `_RecordTableModel`) or return a view with a model already attached (the base respects it and skips its default model installation). `TopicsPanel` exercises the second mode by installing its `QStandardItemModel` inside the factory.

Slice A's prompt said the factory returns a model-less widget. Slice A's actual implementation extended the contract to allow the factory to optionally pre-install a model. The change is sound — without it, `TopicsPanel` would have to either override `_build_ui` again (defeating the refactor) or fight the base post-init by re-replacing the model. All slice A and slice B tests pass with the extended contract.

Update the `_create_master_widget` docstring in `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` to capture this. Append two sentences to the existing docstring along these lines (adapt to match the existing prose):

```
Subclasses may optionally pre-install a model on the returned widget.
If a model is already set when _build_ui receives the widget, the base
skips its default _RecordTableModel installation; TopicsPanel exercises
this mode by installing its QStandardItemModel here.
```

This is the slice's first commit:

```
v2: ui v0.3 — _create_master_widget docstring captures factory may pre-install model
```

After this commit lands, proceed to Step 1.

## Step 1 — Investigate the storage layer surface

Before writing any UI code, verify the access-layer and REST API surface for references.

### `RELATIONSHIP_TYPES` vocab structure

Read `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. The cascading dialog requires the vocab to support these queries:

- "Given a source type, which kinds are valid?"
- "Given a source type and a kind, which target types are valid?"

Possible vocab shapes:

1. **Tuple-keyed dict** (preferred): `{("decision", "session"): ["decided_in"], ("decision", "decision"): ["supersedes", "is_superseded_by"], ...}`. Cascading queries are direct lookups.
2. **List of records**: `[{"kind": "decided_in", "source_type": "decision", "target_type": "session"}, ...]`. Queries filter the list.
3. **Flat list of kinds with no typed constraints**: `["decided_in", "supersedes", ...]`. Cascading is impossible without additional information.

If the vocab is shape (1) or (2), no reshape is needed. If shape (3), reshape to (1) or (2) as part of this slice — it's a mechanical refactor:
- Add the constraint structure to `vocab.py`.
- Update existing references-creating code (the access layer's create method, any tests) to validate against the new structure.
- The structure change is backward-compatible: existing valid references continue to validate.

The reshape decision lands here, in slice C. Document the decision in the slice's reporting.

### REST API surface

Read `crmbuilder-v2/src/crmbuilder_v2/api/routers/references.py`. Confirm:

- `POST /references` exists with the expected payload shape.
- `DELETE /references/{id}` exists.

If `DELETE /references/{id}` is missing, add it as a thin wrapper around the access-layer `delete_reference(id)` method. If `delete_reference` is also missing on the access layer, add it — hard-delete is a one-line `session.delete(record)` against the SQLAlchemy model. Mirror the existing pattern of any other access-layer hard-delete in the repo.

### Naming alignment — `relationship` vs `relationship_kind`

Slice A's reporting flagged a pre-existing v0.2 naming inconsistency: the `POST /references` body field is `relationship`, but the database column and the `references.json` snapshot field are `relationship_kind`. The cascading `ReferenceCreateDialog` and the `client.create_reference` method this slice builds need to know which name to use in the API payload.

Investigate the actual API field name by reading the Pydantic request schema (likely in `crmbuilder-v2/src/crmbuilder_v2/api/schemas/references.py`, or wherever `ReferenceCreateRequest` or its equivalent lives). Confirm the request body field name. The slice resolves between two paths:

**Option A — Align API to DB (rename API field).** Rename the request body field from `relationship` to `relationship_kind` in the Pydantic schema. Existing consumers using the `relationship` name need to be updated; check what's actually using the endpoint today (likely the v2 MCP server's references tool wrapper and any one-off scripts under `crmbuilder-v2/scripts/`). Run `git grep '"relationship"' crmbuilder-v2/` and `git grep "relationship=" crmbuilder-v2/` to inventory callers. If the surface is small and contained, Option A is the cleaner long-term choice — one consistent name across the API, DB, snapshots, and UI.

**Option B — Keep API as-is, translate at the client layer.** The Pydantic schema continues to use `relationship`. The UI's `client.create_reference` method accepts `relationship_kind` as a kwarg (matching the form-field naming and DB-column naming) and translates to `relationship` in the JSON payload. The dialog's form schema uses `relationship_kind` as the field key; nothing outside the client method has to know about the translation.

**Decision criterion:** if the only consumers of the existing `relationship` field name are inside v2 (MCP server, internal scripts), prefer Option A. If any external or hard-to-update consumer exists, take Option B.

Whichever option is chosen, capture the decision and the rationale in this slice's reporting. The example code blocks in Steps 4 and 6 below use `relationship_kind` for the form-field key, the kwarg name on `create_reference`, and the API payload field; if Option B is chosen, the API payload field becomes `relationship` while the kwarg and form key stay `relationship_kind` (the translation happens inside the client method).

### Refresh service entity-type map

Read `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py`. Confirm `references` is in the file → entity-type → signal map. If not, extend the map. The pattern:

```python
ENTITY_TYPE_FILE_MAP = {
    "decisions.json": "decision",
    "sessions.json": "session",
    # ...
    "references.json": "reference",
}
```

Plus the corresponding signal connection on the panel side (`references_changed` or whatever convention the existing service uses).

### Storage-layer commit

If any storage-layer change was made (vocab reshape, missing endpoint, refresh map extension, naming alignment per Option A above), commit it as a separate first commit (or split into multiple commits if the changes are independent):

```
v2: storage — references DELETE endpoint
v2: storage — RELATIONSHIP_TYPES vocab structure for cascading queries
v2: storage — align references API field name to relationship_kind  (if Option A chosen)
```

(Adjust the commit message based on what was actually changed.)

## Step 2 — `EntityIdentifierPicker` widget

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/entity_identifier_picker.py`.

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QCompleter, QWidget


class EntityIdentifierPicker(QComboBox):
    """Editable combo box for selecting an entity by identifier or title.

    Renders entries as 'IDENTIFIER — title' strings with a QCompleter
    configured for Qt.MatchContains substring matching. Emits
    selection_changed(identifier) when a valid selection is made.
    """

    selection_changed = Signal(str)  # the selected identifier

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self._entries: dict[str, str] = {}  # identifier -> "IDENTIFIER — title"
        self._completer = QCompleter(self)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(self._completer)
        self.activated.connect(self._on_activated)

    def set_entries(self, entries: list[tuple[str, str]]) -> None:
        """Populate the picker with (identifier, title) tuples.

        Clears any existing entries first.
        """
        self.clear()
        self._entries.clear()
        for identifier, title in entries:
            display = f"{identifier} — {title}"
            self._entries[identifier] = display
            self.addItem(display, userData=identifier)
        self._completer.setModel(self.model())

    def selected_identifier(self) -> str | None:
        """Return the identifier of the currently selected entry, or None
        if the current text doesn't match any known entry.
        """
        index = self.currentIndex()
        if index >= 0:
            return self.itemData(index)
        # Editable text may not match an item; try to resolve by display
        current_text = self.currentText().strip()
        for identifier, display in self._entries.items():
            if display == current_text or identifier == current_text:
                return identifier
        return None

    def clear_selection(self) -> None:
        self.setCurrentIndex(-1)
        self.setEditText("")

    def _on_activated(self, index: int) -> None:
        identifier = self.itemData(index)
        if identifier:
            self.selection_changed.emit(identifier)
```

Add to `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/__init__.py`:

```python
from .entity_identifier_picker import EntityIdentifierPicker
```

(Plus any existing exports, preserved.)

### Tests

Create `tests/crmbuilder_v2/ui/widgets/test_entity_identifier_picker.py`:

- `test_set_entries_populates_combo` — call `set_entries([("DEC-001", "First decision"), ("DEC-002", "Second")])`; assert `count()` is 2; assert items render as `"DEC-001 — First decision"` etc.
- `test_set_entries_clears_existing` — populate, call again, assert old entries gone.
- `test_selected_identifier_returns_id_for_active_index` — set entries, set current index, assert `selected_identifier()` returns the identifier.
- `test_selected_identifier_returns_none_for_unmatched_text` — set entries, set free-text that doesn't match any entry, assert `None`.
- `test_completer_match_contains` — set entries with substrings; type partial substring; assert completer filters to matching items.
- `test_selection_changed_signal_emitted` — set entries; programmatically select index 1; assert signal emitted with correct identifier.

## Step 3 — Cascading-filter strategy decision

Per implementation plan §2.10, slice C resolves the framework strategy on first contact:

**Option 1 — Extend `FieldSchema`.** Add optional `depends_on: list[str]` and `compute_options: Callable | None` fields. When a field with `depends_on` exists, the dialog wires upstream-field-changed signals to call `compute_options(form_state)` and repopulate the dependent combo.

**Option 2 — Parallel base.** Build a thin `CascadingDialog(QDialog)` that handles the cascade pattern without changing `EntityCrudDialog`. The reference create dialog extends this base.

Decision criterion: if extending `FieldSchema` is bounded (~50 lines added to `crud_dialog.py`, no ripple to existing dialogs), do that. Otherwise, build the parallel base.

**Recommended path:** Option 1. The change to `FieldSchema` is minor; existing dialogs ignore the new optional fields. The wiring inside `EntityCrudDialog.__init__` to subscribe to upstream changes is one new helper method. Cascading dialogs become a generalized capability of the framework rather than a one-off.

If you choose Option 2, document why in the slice reporting.

### If Option 1 — Extend `FieldSchema`

In `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py`:

```python
from typing import Callable

@dataclass
class FieldSchema:
    key: str
    label: str
    widget: Literal["line", "text", "combo", "date", "tree_picker", "identifier_picker"]
    required: bool = False
    placeholder: str | None = None
    vocab: frozenset[str] | None = None
    regex: re.Pattern | None = None
    read_only: bool = False
    depends_on: list[str] | None = None  # NEW — keys of upstream fields
    compute_options: Callable | None = None  # NEW — given form_state dict, return a list of option strings (or list of (id, label) tuples for identifier_picker)
```

Add the `identifier_picker` widget type to the construction switch in `EntityCrudDialog.__init__`. When the widget type is `identifier_picker`, instantiate `EntityIdentifierPicker` and store a reference; populate via `compute_options(form_state)` at dialog-open time and on every upstream-change event.

Wire upstream changes: for each field with `depends_on`, subscribe to the relevant signals on the upstream fields' widgets. When any upstream field changes, call the field's `compute_options(form_state)` and update the widget's options. The exact signal depends on widget type:

- `combo` → `currentTextChanged` or `currentIndexChanged`
- `identifier_picker` → `selection_changed` (the signal added in Step 2)

If a field with `depends_on` has any upstream value missing or invalid, set its widget to disabled and clear its current selection.

### If Option 2 — Parallel base

Create `crmbuilder-v2/src/crmbuilder_v2/ui/base/cascading_dialog.py` housing `CascadingDialog(QDialog)` with the same cascade pattern but bespoke. Reference create dialog extends this base instead of `EntityCrudDialog`. Document the rationale in the slice reporting.

### Tests for the framework extension

Add to `tests/crmbuilder_v2/ui/test_crud_dialog_base.py` (or create a new test if Option 2 was chosen):

- `test_field_schema_depends_on_repopulates_dependent_field` — construct a dialog with two fields, the second depending on the first; change the first; assert the second's options reflect the change.
- `test_field_schema_dependent_disabled_when_upstream_empty` — construct, leave the upstream field empty; assert dependent field is disabled.
- `test_identifier_picker_widget_constructed_for_identifier_picker_type` — construct a schema with an `identifier_picker` field; assert the rendered widget is an `EntityIdentifierPicker`.

## Step 4 — `ReferenceCreateDialog`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/reference_create.py`.

```python
from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.vocab import RELATIONSHIP_TYPES
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient


class ReferenceCreateDialog(EntityCrudDialog):
    """Source-first cascading dialog for creating a reference.

    pre_populated_source: optional (source_type, source_id) tuple.
    When supplied, source-type and source-identifier fields are
    pre-filled and disabled, and the cascade starts from kind.
    """

    def __init__(
        self,
        parent: QWidget,
        client: StorageClient,
        *,
        pre_populated_source: tuple[str, str] | None = None,
    ) -> None:
        self._client = client
        self._pre_populated_source = pre_populated_source

        # Build the field schema based on whether source is pre-populated
        schema = self._build_schema()

        super().__init__(
            parent=parent,
            title="New Reference",
            schema=schema,
            on_save=self._save_reference,
            initial_values=self._initial_values(),
        )

        # Disable source fields if pre-populated
        if pre_populated_source:
            self.set_field_enabled("source_type", False)
            self.set_field_enabled("source_id", False)

    def _build_schema(self) -> list[FieldSchema]:
        return [
            FieldSchema(
                key="source_type",
                label="Source type",
                widget="combo",
                required=True,
                vocab=frozenset(self._all_source_types()),
            ),
            FieldSchema(
                key="source_id",
                label="Source identifier",
                widget="identifier_picker",
                required=True,
                depends_on=["source_type"],
                compute_options=self._compute_source_identifiers,
            ),
            FieldSchema(
                key="relationship_kind",
                label="Relationship",
                widget="combo",
                required=True,
                depends_on=["source_type"],
                compute_options=self._compute_kinds,
            ),
            FieldSchema(
                key="target_type",
                label="Target type",
                widget="combo",
                required=True,
                depends_on=["source_type", "relationship_kind"],
                compute_options=self._compute_target_types,
            ),
            FieldSchema(
                key="target_id",
                label="Target identifier",
                widget="identifier_picker",
                required=True,
                depends_on=["target_type"],
                compute_options=self._compute_target_identifiers,
            ),
        ]

    def _initial_values(self) -> dict[str, str]:
        if self._pre_populated_source:
            source_type, source_id = self._pre_populated_source
            return {"source_type": source_type, "source_id": source_id}
        return {}

    def _all_source_types(self) -> list[str]:
        # Read RELATIONSHIP_TYPES at dialog-open time
        types = set()
        for key in RELATIONSHIP_TYPES:
            # If RELATIONSHIP_TYPES is tuple-keyed (source_type, target_type) -> [kinds]
            source_type = key[0] if isinstance(key, tuple) else None
            if source_type:
                types.add(source_type)
        return sorted(types)

    def _compute_source_identifiers(self, form_state: dict) -> list[tuple[str, str]]:
        source_type = form_state.get("source_type")
        if not source_type:
            return []
        return self._fetch_entity_list(source_type)

    def _compute_kinds(self, form_state: dict) -> list[str]:
        source_type = form_state.get("source_type")
        if not source_type:
            return []
        kinds = set()
        for (st, tt), kind_list in RELATIONSHIP_TYPES.items():
            if st == source_type:
                kinds.update(kind_list)
        return sorted(kinds)

    def _compute_target_types(self, form_state: dict) -> list[str]:
        source_type = form_state.get("source_type")
        kind = form_state.get("relationship_kind")
        if not (source_type and kind):
            return []
        target_types = set()
        for (st, tt), kind_list in RELATIONSHIP_TYPES.items():
            if st == source_type and kind in kind_list:
                target_types.add(tt)
        return sorted(target_types)

    def _compute_target_identifiers(self, form_state: dict) -> list[tuple[str, str]]:
        target_type = form_state.get("target_type")
        if not target_type:
            return []
        return self._fetch_entity_list(target_type)

    def _fetch_entity_list(self, entity_type: str) -> list[tuple[str, str]]:
        """Returns [(identifier, title), ...] for the given entity type.

        Uses the storage client; runs synchronously since the lists are
        small (<1000 entries per type).
        """
        method_map = {
            "decision": self._client.list_decisions,
            "session": self._client.list_sessions,
            "risk": self._client.list_risks,
            "planning_item": self._client.list_planning_items,
            "topic": self._client.list_topics,
            "charter": self._client.list_charter_versions,
            "status": self._client.list_status_versions,
        }
        list_method = method_map.get(entity_type)
        if not list_method:
            return []
        records = list_method()
        return [(r["identifier"], r.get("title", "")) for r in records]

    def _save_reference(self, values: dict[str, str]) -> None:
        """Called by the EntityCrudDialog base on Save."""
        self._client.create_reference(
            source_type=values["source_type"],
            source_id=values["source_id"],
            relationship_kind=values["relationship_kind"],
            target_type=values["target_type"],
            target_id=values["target_id"],
        )
```

The exact code above is illustrative — the actual `EntityCrudDialog` base may differ in its API (e.g., the `on_save` callback shape, the `set_field_enabled` method name). Read `crud_dialog.py` and adapt the dialog construction to match the existing v0.2 base contract. The key requirements are:

- Source-first picking order (source type → source id → kind → target type → target id).
- Cascading filters: each downstream field's options are computed from upstream values via `compute_options`.
- `pre_populated_source` mode: source fields filled and disabled; cascade starts from kind.
- Strict vocab: all `compute_options` callables read `RELATIONSHIP_TYPES` and produce only valid downstream choices.

If the `RELATIONSHIP_TYPES` shape differs from the assumed `dict[(source_type, target_type), list[kinds]]`, adapt the `_compute_*` helpers accordingly. The intent is the same in any shape: filter to valid combinations only.

### Tests

Create `tests/crmbuilder_v2/ui/test_reference_create_dialog.py`:

- `test_dialog_opens_with_empty_fields_when_no_pre_population`
- `test_dialog_opens_with_source_filled_and_disabled_when_pre_populated`
- `test_kind_combo_filtered_by_source_type` — set source type to "decision"; assert kind options include "decided_in", "supersedes" but exclude kinds where decision can never be the source.
- `test_target_type_combo_filtered_by_source_type_and_kind` — set source type "decision", kind "decided_in"; assert target type options are exactly ["session"] (or whatever the vocab actually says).
- `test_target_identifier_picker_repopulates_when_target_type_changes` — change target type; assert the picker's entries change to entities of the new type.
- `test_save_calls_client_create_reference_with_correct_args` — fill all fields; click Save; assert `client.create_reference(...)` was called with the expected kwargs.
- `test_save_handles_validation_error_envelope` — mock client raises `ValidationError({"field": "target_id", "message": "..."})`; assert the dialog renders the error inline on the target_id field.

## Step 5 — `ReferenceDeleteDialog`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/reference_delete.py`.

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient


class ReferenceDeleteDialog(QDialog):
    """Hard-delete confirmation modal for a reference.

    Shows the edge text and a stark "cannot be undone through the UI"
    notice. Confirming sends DELETE /references/{id}.
    """

    def __init__(
        self,
        parent: QWidget,
        client: StorageClient,
        *,
        reference_id: int,
        edge_text: str,  # e.g., "SES-006 → DEC-026: decided_in"
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Delete Reference")
        self._client = client
        self._reference_id = reference_id

        layout = QVBoxLayout(self)

        prompt = QLabel(
            f"Delete the reference [{edge_text}]?\n\n"
            "This cannot be undone through the UI."
        )
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Yes,
            parent=self,
        )
        delete_button = button_box.button(QDialogButtonBox.Yes)
        delete_button.setText("Delete")
        delete_button.setStyleSheet("color: #b00020;")  # red, light enough to inherit
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self._on_delete)
        layout.addWidget(button_box)

    def _on_delete(self) -> None:
        try:
            self._client.delete_reference(self._reference_id)
        except Exception as exc:
            # Surface via the existing error dialog pattern
            from crmbuilder_v2.ui.dialogs.error import ErrorDialog
            ErrorDialog(self, str(exc)).exec()
            return
        self.accept()
```

Adapt the error-handling shape to whatever the existing v0.2 dialogs use (probably worker-based, not synchronous). If v0.2 dialogs run delete through a `QThread` worker, do the same here.

### Tests

Create `tests/crmbuilder_v2/ui/test_reference_delete_dialog.py`:

- `test_dialog_renders_edge_text` — open with `edge_text="SES-006 → DEC-026: decided_in"`; assert the label contains that text.
- `test_dialog_cannot_be_undone_notice_present` — assert the "cannot be undone through the UI" string is in the dialog.
- `test_cancel_does_not_call_delete` — open; click Cancel; assert `client.delete_reference` not called.
- `test_confirm_calls_client_delete_reference_with_id` — open with `reference_id=42`; click Delete; assert `client.delete_reference(42)` called.
- `test_confirm_handles_error` — mock client raises; assert error dialog opens; assert main dialog stays open.

## Step 6 — Storage client extensions

In `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`, add:

```python
def create_reference(
    self,
    *,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship_kind: str,
) -> dict:
    response = self._post(
        "/references",
        json={
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship_kind": relationship_kind,
        },
    )
    return response

def delete_reference(self, reference_id: int) -> None:
    self._delete(f"/references/{reference_id}")
```

The exact method names on `self._post` / `self._delete` may differ — match the existing v0.2 client conventions. If `delete_reference` already exists for read purposes, extend or add the write counterpart.

### Tests

Add to `tests/crmbuilder_v2/ui/test_client.py` (or wherever client tests live):

- `test_create_reference_posts_correct_payload`
- `test_delete_reference_sends_delete_to_correct_url`
- `test_create_reference_propagates_validation_error`

## Step 7 — References panel write integration

Open `crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py`.

### Toolbar `New Reference` button

Add a button to the panel's toolbar (next to Refresh, before any existing buttons). On click, open `ReferenceCreateDialog` with `pre_populated_source=None`. On success, refresh the panel and select the new row by ID.

```python
self._new_reference_button = QPushButton("New Reference", self)
self._new_reference_button.clicked.connect(self._on_new_reference_clicked)
self._toolbar.addWidget(self._new_reference_button)

def _on_new_reference_clicked(self) -> None:
    dialog = ReferenceCreateDialog(self, client=self._client)
    if dialog.exec() == QDialog.Accepted:
        # File-watch will refresh; explicit refresh as fast-path safety net
        self._refresh()
```

### Extend `_build_context_menu` from slice B

Slice B added `Go to source` / `Go to target` to References panel rows. Extend to add `Delete reference` (row context) and `New reference` (whitespace context):

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        new_action = menu.addAction("New reference")
        new_action.triggered.connect(self._on_new_reference_clicked)
        return menu

    record = self._record_at_index(index)
    if record:
        go_source = menu.addAction("Go to source")
        go_source.triggered.connect(
            lambda: self._navigate_to(record["source_type"], record["source_id"])
        )
        go_target = menu.addAction("Go to target")
        go_target.triggered.connect(
            lambda: self._navigate_to(record["target_type"], record["target_id"])
        )
        menu.addSeparator()
        delete_action = menu.addAction("Delete reference")
        delete_action.triggered.connect(
            lambda: self._on_delete_reference_clicked(record)
        )
    return menu

def _on_delete_reference_clicked(self, record: dict) -> None:
    edge_text = (
        f"{record['source_id']} → {record['target_id']}: "
        f"{record['relationship_kind']}"
    )
    dialog = ReferenceDeleteDialog(
        self,
        client=self._client,
        reference_id=record["id"],
        edge_text=edge_text,
    )
    if dialog.exec() == QDialog.Accepted:
        self._refresh()
```

### Tests

Update or add to `tests/crmbuilder_v2/ui/test_references_panel_writes.py`:

- `test_new_reference_button_opens_create_dialog`
- `test_create_dialog_save_creates_reference_and_refreshes_panel`
- `test_context_menu_row_includes_delete_reference`
- `test_context_menu_whitespace_includes_new_reference`
- `test_delete_reference_action_opens_confirmation_modal`
- `test_delete_reference_confirm_calls_client_and_refreshes`

The slice-B `test_context_menus.py` file's References-panel tests need updating to assert the extended action set:

- Row context: `["Go to source", "Go to target", "Delete reference"]` (or with separator handled appropriately)
- Whitespace context: `["New reference"]`

## Step 8 — `ReferencesSection` widget extensions

Open `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`.

### `Add reference` button at the bottom

Add a button to the bottom of the rendered section (or a `+` icon in the section header — slice picks the more natural placement on first contact). Recommendation: button at the bottom for visual prominence; the `+` icon idiom is common but easily missed by users not familiar with the convention.

```python
self._add_button = QPushButton("Add reference", self)
self._add_button.clicked.connect(self._on_add_reference_clicked)
self._layout.addWidget(self._add_button)

def _on_add_reference_clicked(self) -> None:
    dialog = ReferenceCreateDialog(
        self,
        client=self._client,
        pre_populated_source=(self._entity_type, self._identifier),
    )
    if dialog.exec() == QDialog.Accepted:
        self._refresh()
```

### Per-row right-click

Each rendered reference row inside the section needs its own context menu. The exact implementation depends on how v0.2 rendered the rows — likely each is a `QLabel` or a custom row widget inside a `QVBoxLayout`. The pattern:

```python
def _add_reference_row(self, reference: dict) -> None:
    row_widget = ReferenceRow(reference, parent=self)
    row_widget.setContextMenuPolicy(Qt.CustomContextMenu)
    row_widget.customContextMenuRequested.connect(
        lambda pos, r=reference: self._on_row_context_menu(r, pos, row_widget)
    )
    self._layout.addWidget(row_widget)

def _on_row_context_menu(
    self,
    reference: dict,
    position: QPoint,
    row_widget: QWidget,
) -> None:
    menu = QMenu(row_widget)
    delete_action = menu.addAction("Delete reference")
    delete_action.triggered.connect(
        lambda: self._on_delete_reference_clicked(reference)
    )
    other_side_action = menu.addAction(self._other_side_label(reference))
    other_side_action.triggered.connect(
        lambda: self._navigate_to_other_side(reference)
    )
    menu.exec(row_widget.mapToGlobal(position))

def _other_side_label(self, reference: dict) -> str:
    # If the section's host is the source, the "other side" is the target
    if (reference["source_type"] == self._entity_type and
            reference["source_id"] == self._identifier):
        return f"Go to {reference['target_id']}"
    return f"Go to {reference['source_id']}"

def _navigate_to_other_side(self, reference: dict) -> None:
    if (reference["source_type"] == self._entity_type and
            reference["source_id"] == self._identifier):
        self._navigate_signal.emit(reference["target_type"], reference["target_id"])
    else:
        self._navigate_signal.emit(reference["source_type"], reference["source_id"])

def _on_delete_reference_clicked(self, reference: dict) -> None:
    edge_text = (
        f"{reference['source_id']} → {reference['target_id']}: "
        f"{reference['relationship_kind']}"
    )
    dialog = ReferenceDeleteDialog(
        self,
        client=self._client,
        reference_id=reference["id"],
        edge_text=edge_text,
    )
    if dialog.exec() == QDialog.Accepted:
        self._refresh()
```

The existing click-to-navigate behavior on the rows is preserved — right-click is a separate event from click.

### Tests

Update `tests/crmbuilder_v2/ui/widgets/test_references_section.py`:

- `test_add_reference_button_renders`
- `test_add_reference_button_opens_create_dialog_with_pre_populated_source`
- `test_row_right_click_opens_context_menu_with_delete_and_other_side`
- `test_other_side_label_reflects_correct_direction` — for inbound row, label says "Go to [source]"; for outbound, "Go to [target]".
- `test_delete_action_opens_delete_dialog_with_correct_edge_text`
- `test_delete_action_confirm_refreshes_section`
- `test_existing_click_to_navigate_preserved` — left-click on a row still emits the navigate signal as in v0.2.

## Step 9 — Run tests

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: ~504 tests from slice B + ~50 new tests across this slice. Total ~554 passing.

If any v0.2 or earlier-slice test breaks: debug. The widget extensions and dialog additions should not affect existing read-only behavior.

### Manual verification

Beyond automated tests, run the application (`uv run crmbuilder-v2-ui`) and verify:

1. References panel toolbar `New Reference` button opens the dialog.
2. Picking source type "decision" filters kind options; picking source type "session" filters to a different set.
3. The cascade for an existing valid combination (e.g., session → decided_in → decision) results in a Save that creates the reference.
4. Opening a Decision's detail pane shows the `Add reference` button at the bottom of the `ReferencesSection`. Clicking opens the dialog with source pre-filled.
5. Right-click on a reference row in the References panel surfaces `Delete reference`. Confirming hard-deletes; the row disappears.
6. Right-click on a reference row inside the `ReferencesSection` surfaces `Delete reference` and `Go to [other side]`. Both work.
7. Writing a reference via `curl POST /references` while the UI is open causes the panel and any open detail-pane sections to refresh (file-watch).

## Step 10 — Commit, push, report

Three commits suggested:

```
v2: ui v0.3 — EntityIdentifierPicker widget
v2: ui v0.3 — references create + delete dialogs
v2: ui v0.3 — references panel + ReferencesSection write integration
```

If a storage-layer commit was needed in Step 1, prepend it:

```
v2: storage — references DELETE endpoint + RELATIONSHIP_TYPES vocab structure
```

Push:

```
git pull --rebase origin main
git push origin main
```

## Acceptance gates

- [ ] Step 0: `_create_master_widget` docstring captures that subclasses may pre-install a model on the returned widget. Single preliminary commit landed.
- [ ] `relationship` vs `relationship_kind` naming decision resolved (Option A or Option B; documented in slice reporting).
- [ ] `RELATIONSHIP_TYPES` vocab supports cascading queries (or was reshaped in Step 1).
- [ ] `DELETE /references/{id}` endpoint exists.
- [ ] Refresh service map includes `references`.
- [ ] `widgets/entity_identifier_picker.py` houses `EntityIdentifierPicker` with the documented API.
- [ ] Cascading-filter framework strategy resolved (Option 1 or Option 2; documented in slice reporting).
- [ ] `dialogs/reference_create.py` houses `ReferenceCreateDialog` with source-first cascade and pre-population support.
- [ ] `dialogs/reference_delete.py` houses `ReferenceDeleteDialog` with edge-text display and confirmation.
- [ ] `client.py` extended with `create_reference` and `delete_reference`.
- [ ] References panel toolbar shows `New Reference` button; right-click row menu includes `Delete reference`; right-click whitespace shows `New reference`.
- [ ] `widgets/references_section.py` shows `Add reference` button at section bottom; right-click on each row shows `Delete reference` and `Go to [other side]`.
- [ ] No edit affordance on references anywhere.
- [ ] Manual verification cases all pass.
- [ ] Full v2 test suite passes (~554 tests).
- [ ] Commits pushed (one preliminary docstring commit + zero-to-three storage commits if applicable + three feature commits per the strategy in Step 10).

## Out of slice

- Sessions create surface (slice D).
- Reference filtering by relationship type on detail-pane sections (deferred to v0.4).
- Soft-delete on references (deferred per DEC-033).
- Edit affordance on references (rejected per DEC-033).
- Bulk-create references in a single dialog (out of scope; rejected per DEC-033 alternatives).
- Visual styling polish (deferred per DEC-037; minor adjustments allowed in slice E).

## Constraints

- The `RELATIONSHIP_TYPES` vocab is read at dialog-open time, not cached at module import. New kinds added to the access layer should appear in the UI without a code change.
- The cascading filters guarantee no invalid combination is reachable through the dialog. Save error paths exist for server-side validation (e.g., a target identifier that doesn't exist in the database) but never for vocab violations.
- Hard-delete is hard-delete. Do not add a soft-delete column or a Show-deleted toggle. The confirmation modal is the only safety net.
- No edit dialog. Do not add an `Edit` button or `Edit reference` action anywhere.
- The `Add reference` affordance on every detail pane uses the same dialog as the panel-level `New Reference` button — one dialog, two entry points.

## Reporting

After all eleven steps (Step 0 through Step 10) complete, report:

- Confirmation that all acceptance gates above are checked.
- The naming alignment path chosen (Option A — rename API field to `relationship_kind`; or Option B — keep API as `relationship` and translate at client layer) and rationale.
- The cascading-filter framework path chosen (Option 1 — extend `FieldSchema`; or Option 2 — parallel `CascadingDialog` base) and rationale.
- Any storage-layer additions made in Step 1.
- The final test count.
- Any deviations or surprises.
- Any open items for slice D.

Slice D (Sessions create dialog) is the next slice. Its prompt is `CLAUDE-CODE-PROMPT-v2-ui-v0.3-D-sessions-create-dialog.md`.
