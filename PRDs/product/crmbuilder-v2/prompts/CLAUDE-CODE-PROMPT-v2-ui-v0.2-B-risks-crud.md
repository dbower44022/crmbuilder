# CLAUDE-CODE-PROMPT-v2-ui-v0.2-B-risks-crud

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2
**Slice:** B (2 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-A (foundation refactor)

## Purpose

Slice B is the first user of the schema-driven CRUD framework that slice A delivered. It produces a full create/edit/delete surface for the Risks entity:

- A "New Risk" button in the Risks panel toolbar opens a modal create dialog. Saving sends `POST /risks` and on success closes the dialog, refreshes the panel, and selects the newly-created row.
- "Edit" and "Delete" buttons appear in the Risks detail pane (rendered when a row is selected, mirroring the Decisions detail-pane button strip from v0.1 slice G). Edit opens a pre-populated dialog with the identifier read-only; saving sends a partial-update PATCH with only the fields that changed. Delete opens a confirmation dialog; confirming sends DELETE.
- The `ReferencesSection` widget (delivered in slice A) lands on the Risks detail pane, rendering inbound and outbound references for the selected risk.
- Validation errors from the API surface inline on the offending field. When the API's error envelope carries a `field` key, the corresponding form widget shows the inline error label; the dialog stays open. When `field` is absent, a generic `ErrorDialog` appears.

After this slice, Risks have full UI write parity with Decisions, plus reference rendering on the detail pane.

## Project context

Slice A landed the foundation: `EntityCrudDialog` and `EntityCrudDeleteDialog` base classes, the `widgets/` subpackage with `DateField`, `ReferencesSection`, and `HierarchicalEntityPicker`, plus the migrated decisions dialogs that now use the base.

Slice B's per-entity work is mostly declarative: define the field schema for the Risk entity, instantiate the base class with that schema, wire the dialogs into the Risks panel, add the `ReferencesSection` to the detail pane. The heavy lifting was done in slice A.

The Risk SQLAlchemy model and Pydantic schema define the exact field set; this prompt's step 1 reads them as the source of truth before declaring the field schema. Vocabularies (`RISK_PROBABILITIES`, `RISK_IMPACTS`, `RISK_STATUSES`) are already in `crmbuilder_v2.access.vocab` from v0.1.

Risks are physically deleted today via `DELETE /risks/{id}` (verify by reading the access-layer repository — if v0.1 added soft-delete to risks at the same time as decisions, follow the existing semantics). If physical delete, the delete dialog's ConflictError path (referenced records prevent deletion) is reachable and is included in the dialog logic.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice A is on `main`: `git log --oneline -5` should show the slice A commits at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show all slice-A tests passing (estimated 290+).

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — re-read sections 4.2 (Risks CRUD), 4.6 (References rendering), 4.9 (general patterns).
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — re-read Step B in section 4.
4. Slice A's actual code (read for reuse patterns):
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — `EntityCrudDialog`, `EntityCrudDeleteDialog`, `FieldSchema`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_create.py`, `decision_edit.py`, `decision_delete.py` — reference patterns for instantiating the base.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py` — toolbar/button-strip integration patterns.
5. Risk surface (read-only — do not modify in this slice):
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — Risk SQLAlchemy model.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/risks.py` — repository (confirm physical-vs-soft delete; confirm field validation).
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — `RiskCreateIn`, `RiskUpdateIn`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/risks.py` — confirm endpoints exist for POST/PATCH/DELETE.
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `RISK_PROBABILITIES`, `RISK_IMPACTS`, `RISK_STATUSES`.
6. Existing Risks UI panel:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/risks.py` — currently read-only.
7. **Tier 2 orientation** (per DEC-011): current charter, current status (v0.7 after slice A), SES-006 (slice A planning record).

## Step 1 — Discover the Risk field set

Read the Risk SQLAlchemy model and Pydantic schema. Build the v0.2 dialog field schema to match. Check for any v2-specific field naming or constraints not already familiar.

The expected field set, per the Risk entity's purpose in v2 governance:

- `identifier` — text, required, format `RSK-NNN` (verify the existing convention by examining any existing Risk records in `db-export/risks.json` or the database).
- `title` — text, required.
- `description` — multi-line text.
- `probability` — combo, required, vocab from `RISK_PROBABILITIES`.
- `impact` — combo, required, vocab from `RISK_IMPACTS`.
- `status` — combo, required, vocab from `RISK_STATUSES`.
- `mitigation` — multi-line text.

If the Risk model has additional fields (e.g., a `risk_date` or `target_date`, an `owner`), include them in the schema. If a field is missing from this list but present in the model, add it. The model is source of truth.

If the storage system does not currently expose `POST /risks`, `PATCH /risks/{id}`, or `DELETE /risks/{id}` endpoints, the slice extends the storage layer minimally to add them. The existing v0.1 storage system has CRUD routers for decisions and likely follows the same pattern for risks; verify and add what's missing. The additions are mechanical (router file + access-layer repository methods + Pydantic schemas) and follow the existing patterns; stop and ask only if the additions turn out to be more invasive than expected.

## Step 2 — Extend `StorageClient` with risk write methods

In `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`, add three new methods (mirror the existing decision write methods from slice G):

```python
def create_risk(self, body: dict) -> dict:
    """POST /risks. Returns the created record dict.

    Raises ValidationError on 400, ConflictError on 409 (duplicate
    identifier), other StorageClientError subclasses per the standard
    error matrix.
    """
    return self._request("POST", "/risks", json=body)


def update_risk(self, identifier: str, body: dict) -> dict:
    """PATCH /risks/{identifier}. Body should contain only the fields
    that changed. Returns the updated record dict.
    """
    return self._request("PATCH", f"/risks/{identifier}", json=body)


def delete_risk(self, identifier: str) -> dict:
    """DELETE /risks/{identifier}. Returns the API's response data."""
    return self._request("DELETE", f"/risks/{identifier}")
```

Confirm `get_risk(identifier)` exists from v0.1. If not, add it.

### Tests

Extend `tests/crmbuilder_v2/ui/test_client.py`:

- `create_risk({...})` returns the created dict on 201.
- `create_risk` with a duplicate identifier raises `ConflictError`.
- `create_risk` with an invalid combo value raises `ValidationError`; `field_errors()` returns the right mapping.
- `update_risk("RSK-001", {"title": "new"})` returns the updated dict.
- `update_risk` with a non-existent identifier raises `NotFoundError`.
- `delete_risk("RSK-001")` returns the API response.

Use `httpx.MockTransport` consistent with v0.1's test patterns.

## Step 3 — Define the Risk field schema and dialog classes

### `dialogs/risk_create.py` (new)

```python
"""Risks Create dialog. Per ui-PRD-v0.2.md §4.2."""
from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.vocab import (
    RISK_IMPACTS, RISK_PROBABILITIES, RISK_STATUSES,
)
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient


_RISK_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="identifier", label="Identifier", widget="line",
        required=True, placeholder="RSK-NNN",
        regex=re.compile(r"^RSK-\d{3,}$"),
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="probability", label="Probability", widget="combo",
        required=True, vocab=RISK_PROBABILITIES,
    ),
    FieldSchema(
        key="impact", label="Impact", widget="combo",
        required=True, vocab=RISK_IMPACTS,
    ),
    FieldSchema(
        key="status", label="Status", widget="combo",
        required=True, vocab=RISK_STATUSES,
    ),
    FieldSchema(key="mitigation", label="Mitigation", widget="text"),
    # Add any additional fields discovered in step 1.
]


class RiskCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            _RISK_FIELDS,
            mode="create",
            title="New Risk",
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()
```

### `dialogs/risk_edit.py` (new)

```python
class RiskEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            _risk_edit_fields(),  # identifier read_only=True
            mode="edit",
            title=f"Edit {record['identifier']}",
            record=record,
            parent=parent,
        )
```

`_risk_edit_fields()` returns a copy of `_RISK_FIELDS` with the identifier field's `read_only` set to True.

### `dialogs/risk_delete.py` (new)

```python
class RiskDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_risk,
            parent=parent,
        )
```

If risks are physical-delete (verified in step 1), `EntityCrudDeleteDialog` already handles ConflictError appropriately (defensive ErrorDialog fallback per slice A). If risks become soft-delete in the future, the dialog's behavior is unchanged — soft-delete is a status PATCH on the API side, transparent to the dialog.

The `client.delete_risk` reference passed to the base class binds correctly because `EntityCrudDeleteDialog` accepts a callable.

## Step 4 — Wire dialogs into the Risks panel

`panels/risks.py` is currently a read-only panel. Slice B extends it.

### Toolbar "New Risk" button

Add to the panel's `__init__`, in the existing toolbar action layout (the slot from `ListDetailPanel`):

```python
self._new_risk_btn = QPushButton("New Risk")
self._new_risk_btn.clicked.connect(self._on_new_risk_clicked)
self._action_layout.addWidget(self._new_risk_btn)


def _on_new_risk_clicked(self) -> None:
    dialog = RiskCreateDialog(self._client, self)
    if dialog.exec() == QDialog.Accepted:
        new_id = dialog.created_identifier()
        if new_id:
            self.select_record_by_identifier(new_id)
```

### Detail pane "Edit" and "Delete" buttons

Mirror the Decisions panel's button-strip pattern. In `render_detail`, add a button strip at the top of the form layout:

```python
edit_btn = QPushButton("Edit")
delete_btn = QPushButton("Delete")
edit_btn.clicked.connect(lambda: self._on_edit_clicked(record))
delete_btn.clicked.connect(lambda: self._on_delete_clicked(record))


def _on_edit_clicked(self, record: dict) -> None:
    try:
        fresh = self._client.get_risk(record["identifier"])
    except NotFoundError:
        self.refresh()
        return
    except StorageClientError:
        ErrorDialog(
            "Could not load risk",
            "Could not load the latest version of this risk.",
            parent=self,
        ).exec()
        return

    dialog = RiskEditDialog(self._client, fresh, self)
    if dialog.exec() == QDialog.Accepted:
        self.refresh()


def _on_delete_clicked(self, record: dict) -> None:
    dialog = RiskDeleteDialog(
        self._client,
        record["identifier"],
        record["title"],
        self,
    )
    if dialog.exec() == QDialog.Accepted:
        self.refresh()
```

### `ReferencesSection` on the detail pane

Append the `ReferencesSection` widget to the detail pane layout, beneath the form fields. The widget connects its `navigate_requested` signal to the panel's existing navigate-out pattern (the same signal Decisions wires up):

```python
references_section = ReferencesSection(
    self._client,
    "risk",
    record["identifier"],
    parent=self,
)
references_section.navigate_requested.connect(self.navigate_requested)
```

No `exclude_relationships` — the Risks detail pane has no top-level relationship fields that would create redundancy.

## Step 5 — Tests

### `tests/crmbuilder_v2/ui/test_risk_dialogs.py` (new)

Tests for the three new dialog classes. Mirror the structure of `test_decision_create_dialog.py`, `test_decision_edit_dialog.py`, `test_decision_delete_dialog.py` from slice A (post-migration).

Key tests:

1. `RiskCreateDialog` construction renders the field set discovered in step 1.
2. Required-field check blocks empty submissions.
3. Combo widgets are bound to the correct vocab (probability, impact, status).
4. Successful create accepts with `created_identifier` set.
5. ValidationError populates inline errors.
6. ConflictError on duplicate identifier surfaces inline on Identifier.
7. `RiskEditDialog` pre-populates from the record.
8. Identifier is read-only on Edit.
9. No-changes Save accepts without API call.
10. Single-field change sends a one-field PATCH.
11. `RiskDeleteDialog` confirmation; successful delete accepts; ConflictError surfaces via ErrorDialog (defensive); NotFoundError accepts (treats as already deleted).

### `tests/crmbuilder_v2/ui/test_risks_panel_writes.py` (new)

Panel integration tests. Mirror `test_decisions_panel_writes.py` from v0.1 slice G (post-migration in slice A).

Key tests:

1. New Risk button is present in the toolbar.
2. Clicking New Risk opens the create dialog.
3. Successful create triggers `select_record_by_identifier`.
4. Detail pane has Edit and Delete buttons when a record is selected.
5. Edit click fetches fresh record and opens edit dialog.
6. Successful edit triggers `panel.refresh()`.
7. Delete click opens delete dialog.
8. Successful delete triggers `panel.refresh()`.
9. ReferencesSection is present on the detail pane after a row is selected.

## Step 6 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: slice A's tests + new tests from this slice. Estimated 305+ passing.

Manual verification:

1. **Create flow.** Launch UI, navigate to Risks, click "New Risk". Fill all required fields (e.g., `identifier="RSK-001"`, `title="Test risk"`, `probability="Low"`, `impact="Medium"`, `status="Open"`). Click Save. Confirm the dialog closes, the new row appears, and is selected.
2. **Create with duplicate identifier.** Click "New Risk" again with the same identifier. Confirm inline error on Identifier: "An identifier with this value already exists."
3. **Edit flow.** Select a risk; click Edit; modify the Title; click Save. Confirm the row in the table shows the new title.
4. **Edit with no changes.** Open Edit; click Save without changing anything. Confirm the dialog closes immediately; no API call.
5. **Delete flow.** Select a risk; click Delete; confirm the dialog body shows the identifier and title; click Delete. Confirm the row disappears.
6. **Watcher integration.** Use curl to POST a new risk while the panel is open. Confirm within ~1 second the row appears (file-watch path).
7. **References on detail pane.** Select a risk that has inbound or outbound references (create a reference via curl if none exists). Confirm the ReferencesSection renders with grouped sections.

Commit shape:

```
v2: ui risks CRUD — create, edit, delete + references section

Implements slice B of the v2-ui-v0.2 series. Per ui-PRD-v0.2.md §4.2
and §4.6:

- RiskCreateDialog, RiskEditDialog, RiskDeleteDialog as instances of
  EntityCrudDialog / EntityCrudDeleteDialog with the Risk field
  schema. Vocabularies (RISK_PROBABILITIES, RISK_IMPACTS,
  RISK_STATUSES) imported from access-layer vocab.

- panels/risks.py extended: New Risk button in toolbar; Edit and
  Delete buttons in detail-pane button strip; ReferencesSection on
  detail pane.

- StorageClient extended with create_risk, update_risk, delete_risk.

- ~15 new tests covering dialogs and panel integration.

Out of slice: write surfaces for any other entity (slices C, D, E).
```

If storage-system additions were needed (Risk router endpoints, repository methods), commit them separately first:

```
v2: storage adds POST/PATCH/DELETE for risks
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. New Risk button in the Risks panel toolbar opens the create dialog. Filling required fields and clicking Save creates the record, closes the dialog, refreshes the panel, and selects the new row. (PRD AC#2.)
2. Editing a selected risk via the Edit button opens a pre-populated dialog. Modifying a field and clicking Save updates the record. The panel reflects the change. (PRD AC#3.)
3. Deleting a selected risk via the Delete button opens a confirmation dialog. Confirming deletes the record. The panel reflects the deletion. (PRD AC#4.)
4. Submitting a duplicate identifier surfaces an inline error on the Identifier field; dialog stays open.
5. Submitting an edit with no changes closes the dialog immediately without making an API call.
6. ReferencesSection is rendered on the Risks detail pane and correctly fetches inbound/outbound references for the selected risk. (Partial AC#10.)
7. Live refresh: a `curl POST /risks` while the panel is open causes the new row to appear without manual refresh.
8. The full v2 test suite passes, including all new tests from this slice.
9. One main commit on `origin/main` (plus an optional storage-additions commit if needed).

## Out of slice

The following are explicitly NOT in scope for slice B:

- Create/edit/delete for any entity other than Risks. Planning Items, Topics, Charter, Status all defer to subsequent slices.
- ReferencesSection on any other panel beyond Risks. Slices C, D, E add it to their respective panels.
- Show-deleted toggle on Risks (not in v0.2 scope; risks have their own Closed status which serves a similar purpose).
- Bulk operations.

## Constraints

- **No new external dependencies.**
- **Storage-system additions only if needed** (Risk router endpoints) — keep them mechanical and follow existing patterns. If invasive, surface as an open question.
- **Do not modify the lifecycle, refresh service, or any other panel.**
- **Keep the schema-driven dialog pattern from slice A.** Do not add bespoke per-field logic to the Risks dialogs that doesn't have a counterpart in the base class.
- **Stop and ask if uncertain.** If the Risk model has fields not anticipated by this prompt's expected field set, the slice incorporates them and notes the discovery in the report.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the nine gates above.
- **Files created or modified** — full list, organized by step.
- **Field set discovered** — the actual Risk field schema declared, with any deltas from this prompt's expected list noted.
- **Storage-system additions** (if any) — endpoints/methods added.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — confirmation that the seven manual scenarios above all worked.
- **Deviations from this prompt** — anything that diverged.
- **What slice C will need** — anything from B's outputs that C's prompt should know about (e.g., if a UX detail emerged that suggests a small base-class polish).
