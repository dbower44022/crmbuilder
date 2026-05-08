# CLAUDE-CODE-PROMPT-v2-ui-v0.2-C-planning-items-crud

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2
**Slice:** C (3 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-B (risks CRUD)

## Purpose

Slice C produces a full create/edit/delete surface for the Planning Items entity, mirroring slice B's shape. It is structurally a near-copy of slice B with planning-item-specific fields and vocabularies.

After this slice:

- A "New Planning Item" button in the Planning Items panel toolbar opens a modal create dialog using `EntityCrudDialog`.
- "Edit" and "Delete" buttons appear in the Planning Items detail pane.
- The `ReferencesSection` widget renders on the Planning Items detail pane.
- Vocabularies (`PLANNING_ITEM_TYPES`, `PLANNING_ITEM_STATUSES`) are imported from `crmbuilder_v2.access.vocab`.

## Project context

Slice B established the per-entity CRUD pattern: read the SQLAlchemy model and Pydantic schema; declare the field schema; instantiate `EntityCrudDialog` and `EntityCrudDeleteDialog` with that schema; wire toolbar and detail-pane buttons; add `ReferencesSection`. Slice C follows the exact same pattern for Planning Items.

The Planning Item entity in v2 represents discrete planning concerns — open questions, planning dimensions, pending work — that are tracked but not yet promoted to Decisions. Per the access-layer vocab:

- `PLANNING_ITEM_TYPES = frozenset({"planning_dimension", "open_question", "pending_work"})`
- `PLANNING_ITEM_STATUSES = frozenset({"Open", "Resolved", "Deferred"})`

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice B is on `main`: `git log --oneline -5` should show the slice B commit at or near the top.
6. Confirm the v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show all slice-A and slice-B tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — re-read section 4.3 (Planning Items CRUD).
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — Step C in section 4.
4. Slice B's actual deliverables (Planning Items mirrors them):
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/risk_create.py`, `risk_edit.py`, `risk_delete.py`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/risks.py` — toolbar/detail-pane integration.
5. Planning Item surface (read-only — do not modify):
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — PlanningItem SQLAlchemy model.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/planning_items.py` — repository.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — `PlanningItemCreateIn`, `PlanningItemUpdateIn`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/planning_items.py` — confirm endpoints exist.
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `PLANNING_ITEM_TYPES`, `PLANNING_ITEM_STATUSES`.
6. Existing Planning Items UI panel:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/planning_items.py` — currently read-only.
7. **Tier 2 orientation**: current charter, current status, SES-006 (planning), DEC-027 (entity scope), DEC-028 (dialog architecture).

## Step 1 — Discover the Planning Item field set

Read the PlanningItem SQLAlchemy model and Pydantic schema. Build the v0.2 dialog field schema to match.

Expected field set:

- `identifier` — text, required, format pattern (verify against existing records — e.g., `PLAN-NNN`, `PI-NNN`, or whatever convention is in use).
- `title` — text, required.
- `description` — multi-line text.
- `type` — combo, required, vocab from `PLANNING_ITEM_TYPES`.
- `status` — combo, required, vocab from `PLANNING_ITEM_STATUSES`.
- (any additional fields the access layer defines — e.g., `resolution_note`, `target_date`).

If the model has additional fields, include them. If a date field is present, use the `DateField` widget from slice A.

If the storage system does not currently expose `POST /planning_items`, `PATCH /planning_items/{id}`, or `DELETE /planning_items/{id}`, the slice extends the storage layer minimally. The pattern is the same as slice B: router file + access-layer repository methods + Pydantic schemas. Mechanical work; surface only if invasive.

## Step 2 — Extend `StorageClient` with planning-item write methods

In `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`:

```python
def create_planning_item(self, body: dict) -> dict:
    return self._request("POST", "/planning_items", json=body)


def update_planning_item(self, identifier: str, body: dict) -> dict:
    return self._request("PATCH", f"/planning_items/{identifier}", json=body)


def delete_planning_item(self, identifier: str) -> dict:
    return self._request("DELETE", f"/planning_items/{identifier}")
```

Confirm `get_planning_item(identifier)` exists from v0.1; if not, add it.

### Tests

Extend `tests/crmbuilder_v2/ui/test_client.py` with the same shape of tests as slice B's risk methods.

## Step 3 — Define the Planning Item dialog classes

### `dialogs/planning_item_create.py` (new)

```python
"""Planning Items Create dialog. Per ui-PRD-v0.2.md §4.3."""
import re

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.vocab import (
    PLANNING_ITEM_STATUSES, PLANNING_ITEM_TYPES,
)
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient


_PLANNING_ITEM_FIELDS: list[FieldSchema] = [
    FieldSchema(
        key="identifier", label="Identifier", widget="line",
        required=True, placeholder="<verify convention>",
        regex=re.compile(r"^<verified pattern>$"),
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="type", label="Type", widget="combo",
        required=True, vocab=PLANNING_ITEM_TYPES,
    ),
    FieldSchema(
        key="status", label="Status", widget="combo",
        required=True, vocab=PLANNING_ITEM_STATUSES,
    ),
    # Add any additional fields discovered in step 1.
]


class PlanningItemCreateDialog(EntityCrudDialog):
    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None:
        super().__init__(
            client,
            _PLANNING_ITEM_FIELDS,
            mode="create",
            title="New Planning Item",
            parent=parent,
        )

    def created_identifier(self) -> str | None:
        return self.saved_identifier()
```

### `dialogs/planning_item_edit.py` (new)

```python
class PlanningItemEditDialog(EntityCrudDialog):
    def __init__(
        self,
        client: StorageClient,
        record: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            _planning_item_edit_fields(),  # identifier read_only=True
            mode="edit",
            title=f"Edit {record['identifier']}",
            record=record,
            parent=parent,
        )
```

### `dialogs/planning_item_delete.py` (new)

```python
class PlanningItemDeleteDialog(EntityCrudDeleteDialog):
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
            client.delete_planning_item,
            parent=parent,
        )
```

## Step 4 — Wire dialogs into the Planning Items panel

`panels/planning_items.py`. Mirror slice B's wiring on the Risks panel:

- "New Planning Item" button in the toolbar action layout.
- Edit and Delete buttons in the detail-pane button strip rendered by `render_detail`.
- `ReferencesSection` widget appended to the detail pane.
- Same `_on_new_clicked` / `_on_edit_clicked` / `_on_delete_clicked` handler pattern.

```python
references_section = ReferencesSection(
    self._client,
    "planning_item",
    record["identifier"],
    parent=self,
)
references_section.navigate_requested.connect(self.navigate_requested)
```

The entity_type string passed to `ReferencesSection` is `"planning_item"` — verify the exact spelling matches the storage layer's `ENTITY_TYPES` vocab in `vocab.py`.

## Step 5 — Tests

### `tests/crmbuilder_v2/ui/test_planning_item_dialogs.py` (new)

Mirror `test_risk_dialogs.py` from slice B. Adjust for planning-item-specific vocab. ~12 tests.

### `tests/crmbuilder_v2/ui/test_planning_items_panel_writes.py` (new)

Mirror `test_risks_panel_writes.py` from slice B. ~9 tests.

## Step 6 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: slice A + slice B tests + new tests from this slice. Estimated 320+ passing.

Manual verification:

1. Create flow with all required fields.
2. Edit flow modifying a single field.
3. Delete flow.
4. Watcher integration.
5. ReferencesSection renders on the Planning Items detail pane.

Commit shape:

```
v2: ui planning items CRUD — create, edit, delete + references section

Implements slice C of the v2-ui-v0.2 series. Per ui-PRD-v0.2.md §4.3
and §4.6:

- PlanningItemCreateDialog, PlanningItemEditDialog,
  PlanningItemDeleteDialog as instances of EntityCrudDialog /
  EntityCrudDeleteDialog with the PlanningItem field schema.
  Vocabularies (PLANNING_ITEM_TYPES, PLANNING_ITEM_STATUSES) imported
  from access-layer vocab.

- panels/planning_items.py extended: New Planning Item button in
  toolbar; Edit and Delete buttons in detail-pane button strip;
  ReferencesSection on detail pane.

- StorageClient extended with create_planning_item,
  update_planning_item, delete_planning_item.

- ~21 new tests covering dialogs and panel integration.

Out of slice: topics, charter, status, show-deleted (slices D, E, F).
```

If storage additions were needed:

```
v2: storage adds POST/PATCH/DELETE for planning_items
```

Push to origin/main.

## Acceptance gates

1. New Planning Item button opens the create dialog. Successful create refreshes panel and selects new row.
2. Edit flow updates a planning item; partial PATCH; panel reflects.
3. Delete flow removes a planning item; panel reflects.
4. Inline validation works.
5. ReferencesSection renders on Planning Items detail pane. (PRD AC#5, partial AC#10.)
6. Live refresh works.
7. Test suite passes.
8. Commit(s) on origin/main.

## Out of slice

- Create/edit/delete for any other entity. Slices D, E, F.
- ReferencesSection on any panel besides Planning Items.

## Constraints

- **No new external dependencies.**
- **Storage-system additions only if needed.** Mechanical and aligned with existing patterns; surface if invasive.
- **Reuse the schema-driven dialog pattern.** No bespoke per-field logic.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- Acceptance gates pass/fail.
- Files created or modified.
- Field set discovered.
- Storage-system additions (if any).
- Test results.
- Manual verification confirmation.
- Deviations.
- What slice D will need.
