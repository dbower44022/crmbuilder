# CRMBuilder v2 — UI v0.2 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-08-26
**Status:** Draft — pending approval
**Companion PRD:** `ui-PRD-v0.2.md`
**Predecessor plan:** `ui-implementation-plan.md` (v0.1, shipped per SES-005)
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.2-{A..F}-*.md`

---

## 1. Overview

This plan implements the v0.2 desktop UI specified in `ui-PRD-v0.2.md`. v0.2 is decomposed into six independently testable slices, each delivered as its own Claude Code prompt. Each prompt produces a working state of the application that exercises a coherent subset of the PRD's acceptance criteria.

The slice boundaries are dictated by dependency and natural review checkpoints. Foundation refactor before per-entity work; CRUD entities before charter/status replace flow; replace flow before closeout polish. v0.1's eight slices were necessary because v0.1 built every architectural piece from scratch (lifecycle, threading, error envelope, refresh, dialog mechanics). v0.2 inherits all of those — six slices is appropriate.

After all six prompts execute cleanly, every acceptance criterion in PRD section 6 is satisfied. The application is functional and useful from prompt B onward (each entity slice ships its write surface and its detail-pane references), with each subsequent prompt strictly additive.

---

## 2. Implementation Choices

### 2.1 Language and runtime

Unchanged from v0.1. Python 3.12+, matching the existing repository's `requires-python` pin in `pyproject.toml`.

### 2.2 Desktop framework — PySide6

Unchanged from v0.1. PySide6 is already the desktop framework for v1 and v0.1.

### 2.3 HTTP client — httpx (sync mode)

Unchanged from v0.1. `httpx.Client` synchronously inside `QThread` workers.

### 2.4 Subprocess management — QProcess

Unchanged from v0.1.

### 2.5 File watching — QFileSystemWatcher

Unchanged from v0.1, including slice H's content-hash gating.

### 2.6 Test framework — pytest + pytest-qt

Unchanged from v0.1. pytest-qt's `qtbot` and `qapp` fixtures continue to be the testing pattern.

### 2.7 Logging — Python's standard `logging` module

Unchanged from v0.1. RotatingFileHandler at `~/.crmbuilder-v2/ui.log`.

### 2.8 Threading model

Unchanged from v0.1. Worker/object pattern; `run_in_thread` helper.

### 2.9 Error handling

Unchanged from v0.1. Typed exceptions in the storage client; inline-on-field for validation errors with `field`; modal `ErrorDialog` for everything else.

### 2.10 New for v0.2 — schema-driven dialog framework

`EntityCrudDialog` is parameterized by a per-entity field schema. The schema is a list of field descriptors:

```python
@dataclass
class FieldSchema:
    key: str                             # API field name
    label: str                           # UI label
    widget: Literal["line", "text",      # widget shape
                    "combo", "date",
                    "tree_picker"]
    required: bool = False
    placeholder: str | None = None
    vocab: frozenset[str] | None = None  # for combo widgets
    regex: re.Pattern | None = None      # client-side format check
    read_only: bool = False              # for Edit dialogs (Identifier)
```

Each entity's create dialog and edit dialog are subclasses (or thin wrappers) that supply the field schema. The base class handles widget construction, layout, inline error label management, the Save/Cancel buttons, the worker submission, the validation-error envelope routing, and the partial-PATCH diff (Edit only).

`VersionedReplaceDialog` is similarly parameterized by entity type (`"charter"` or `"status"`) and the storage client method to call (`replace_charter`, `replace_status`). The dialog itself is schema-blind — it presents JSON, validates JSON, submits JSON.

### 2.11 New for v0.2 — `ui/widgets/` package

A new top-level subpackage `crmbuilder_v2.ui.widgets` houses reusable widgets that are not dialogs and not entity-specific panels. v0.2 adds three widgets:

- `widgets/date_field.py` — `DateField` wrapping `QDateEdit` with calendar popup, configured for `MM-DD-YY` round-tripping.
- `widgets/references_section.py` — `ReferencesSection` for inbound/outbound reference rendering on detail panes.
- `widgets/hierarchical_picker.py` — `HierarchicalEntityPicker` for tree-shaped entity selection (parent_topic; future methodology entities).

Future widget additions (e.g., a multi-entity picker, a rich-text editor) land here as well.

---

## 3. Directory and File Layout

The UI lives entirely under `crmbuilder-v2/src/crmbuilder_v2/ui/`. v0.2 adds the `widgets/` subpackage and extends `base/` and `dialogs/`:

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    └── ui/
        ├── widgets/                              # NEW
        │   ├── __init__.py
        │   ├── date_field.py                     # NEW
        │   ├── references_section.py             # NEW
        │   └── hierarchical_picker.py            # NEW
        ├── base/
        │   ├── list_detail_panel.py              # unchanged
        │   ├── versioned_panel.py                # unchanged
        │   ├── crud_dialog.py                    # NEW (EntityCrudDialog + EntityCrudDeleteDialog)
        │   └── versioned_replace_dialog.py       # NEW
        ├── dialogs/
        │   ├── decision_create.py                # MODIFIED — uses EntityCrudDialog
        │   ├── decision_edit.py                  # MODIFIED — uses EntityCrudDialog
        │   ├── decision_delete.py                # MODIFIED — uses EntityCrudDeleteDialog
        │   ├── error.py                          # unchanged
        │   ├── risk_create.py                    # NEW
        │   ├── risk_edit.py                      # NEW
        │   ├── risk_delete.py                    # NEW
        │   ├── planning_item_create.py           # NEW
        │   ├── planning_item_edit.py             # NEW
        │   ├── planning_item_delete.py           # NEW
        │   ├── topic_create.py                   # NEW
        │   ├── topic_edit.py                     # NEW
        │   ├── topic_delete.py                   # NEW
        │   ├── charter_replace.py                # NEW
        │   └── status_replace.py                 # NEW
        └── panels/
            ├── decisions.py                      # MODIFIED — show-deleted toggle, ReferencesSection
            ├── sessions.py                       # MODIFIED — ReferencesSection
            ├── risks.py                          # MODIFIED — toolbar + detail buttons + ReferencesSection
            ├── planning_items.py                 # MODIFIED — toolbar + detail buttons + ReferencesSection
            ├── topics.py                         # MODIFIED — QTreeView, toolbar + detail buttons + ReferencesSection
            ├── charter.py                        # MODIFIED — New Version button, Make Current, ReferencesSection
            └── status.py                         # MODIFIED — same as charter

tests/
└── crmbuilder_v2/
    └── ui/
        ├── widgets/                              # NEW test directory
        │   ├── test_date_field.py                # NEW
        │   ├── test_references_section.py        # NEW
        │   └── test_hierarchical_picker.py       # NEW
        ├── test_decision_create_dialog.py        # MODIFIED — refactor against new base
        ├── test_decision_edit_dialog.py          # MODIFIED — refactor against new base
        ├── test_decision_delete_dialog.py        # MODIFIED — refactor against new base
        ├── test_decisions_panel_writes.py        # MODIFIED — show-deleted toggle
        ├── test_crud_dialog_base.py              # NEW — base class behavior
        ├── test_versioned_replace_dialog_base.py # NEW
        ├── test_risk_dialogs.py                  # NEW
        ├── test_risks_panel_writes.py            # NEW
        ├── test_planning_item_dialogs.py         # NEW
        ├── test_planning_items_panel_writes.py   # NEW
        ├── test_topic_dialogs.py                 # NEW
        ├── test_topics_panel_writes.py           # NEW (QTreeView + writes)
        ├── test_charter_replace.py               # NEW
        ├── test_status_replace.py                # NEW
        └── test_show_deleted_toggle.py           # NEW
```

Storage-system additions, made in the slice that needs them:

- `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py` — `?include_deleted=true` query parameter on `GET /decisions` (slice F if not already present).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/charter.py`, `status.py` — make-current endpoint (slice E if not already present).

---

## 4. Build Sequence

Each slice lands as one commit (or a small handful) prefixed `v2:` per the v2 convention and corresponds to one execution prompt. PRD acceptance criteria from section 6 are cross-referenced as `AC#N`.

### Step A — Foundation refactor

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-A-foundation-refactor.md`

**Deliverables:**

- New `widgets/` subpackage with `DateField`, `ReferencesSection`, `HierarchicalEntityPicker`.
- New `base/crud_dialog.py` housing `EntityCrudDialog` and `EntityCrudDeleteDialog`. Field schema dataclass. Inline error label management. Save-via-worker pattern factored from v0.1's decisions dialogs.
- Migration of `dialogs/decision_create.py`, `decision_edit.py`, `decision_delete.py` to use the new base. Decisions field schema (11 fields per v0.1 PRD §4.7) defined as a constant. The `DateField` widget replaces the plain-text `QLineEdit` for Decision Date. The `ReferencesSection` widget replaces v0.1's bespoke inbound-reference rendering on the Decisions detail pane.
- Planning records: SES-006, DEC-026 through DEC-031, six `decided_in` references from SES-006, status update bumping to `"v0.2 in build, slice A in progress"`.
- Tests: `test_crud_dialog_base.py`, `test_widgets/test_date_field.py`, `test_widgets/test_references_section.py`, `test_widgets/test_hierarchical_picker.py`. Existing `test_decision_*_dialog.py` files updated to assert behavior against the new base; v0.1's coverage stays equivalent or grows.

**Acceptance gates:**

- The full v2 test suite passes (264 v0.1 tests + new framework and widget tests). Estimated 290+ passing.
- Visible Decisions UI behavior is unchanged: Create dialog has the same 11 fields, the same status dropdown, the same error envelope handling. Edit dialog has read-only identifier and partial PATCH. Delete dialog has the same confirmation. Calendar widget on Decision Date is the only visible change.
- Decisions detail pane renders inbound and outbound references via the new `ReferencesSection` widget (the supersedes outbound is suppressed via `exclude_relationships` to avoid redundancy with the existing top-level field).
- Planning records are present in the database: SES-006, DEC-026 through DEC-031, six references, status v0.7.

**Out of slice:** any new entity write surface, charter/status replace, show-deleted toggle, QTreeView for topics.

---

### Step B — Risks CRUD

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-B-risks-crud.md`

**Deliverables:**

- `dialogs/risk_create.py`, `risk_edit.py`, `risk_delete.py` as instances of `EntityCrudDialog` / `EntityCrudDeleteDialog`. Field schema imports `RISK_PROBABILITIES`, `RISK_IMPACTS`, `RISK_STATUSES` from `crmbuilder_v2.access.vocab`.
- `panels/risks.py` extended: New Risk button in toolbar; Edit/Delete buttons in detail-pane button strip; `ReferencesSection` on detail pane.
- `client.py` extended with `create_risk`, `update_risk`, `delete_risk`, plus any missing get-for-edit method.
- The slice prompt reads the risk SQLAlchemy model and Pydantic schema to discover the exact field set; the field schema in the dialog matches.
- Tests: `test_risk_dialogs.py`, `test_risks_panel_writes.py`. ~15 new tests.

**Acceptance gates:**

- New Risk button opens the create dialog. Filling required fields and clicking Save creates the record, refreshes the panel, selects the new row. (AC#2)
- Edit dialog loads with values pre-populated; partial PATCH on save; panel reflects the change. (AC#3)
- Delete dialog confirms; deletion succeeds; row disappears (or status changes to Deleted if soft-delete is the access-layer pattern for risks). (AC#4)
- Inline validation works: empty required fields, invalid combo selections (impossible via dropdown), API-side validation errors with `field` populated.
- `ReferencesSection` renders on the Risks detail pane. (Partial AC#10.)
- Live refresh: a `curl POST /risks` while the panel is open causes the new row to appear without manual refresh. (Continues v0.1 file-watch behavior.)
- Test suite passes.

**Out of slice:** any other entity's write surface; references on other panels.

---

### Step C — Planning Items CRUD

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-C-planning-items-crud.md`

**Deliverables:**

- `dialogs/planning_item_create.py`, `planning_item_edit.py`, `planning_item_delete.py`.
- `panels/planning_items.py` extended: toolbar buttons, detail-pane buttons, `ReferencesSection`.
- `client.py` extended with `create_planning_item`, `update_planning_item`, `delete_planning_item`.
- Vocab imports: `PLANNING_ITEM_TYPES`, `PLANNING_ITEM_STATUSES`.
- Tests: `test_planning_item_dialogs.py`, `test_planning_items_panel_writes.py`.

**Acceptance gates:**

- Mirror of slice B for planning items. (AC#5.)
- `ReferencesSection` renders on the Planning Items detail pane. (Partial AC#10.)

**Out of slice:** topics, charter, status, show-deleted.

---

### Step D — Topics CRUD + QTreeView + HierarchicalEntityPicker

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-D-topics-and-tree-picker.md`

**Deliverables:**

- `panels/topics.py` swaps from indented `QTableView` to `QTreeView` backed by a `QStandardItemModel`. Tree population logic builds parent → children mapping from `parent_topic_id`. Single-row selection emits the existing `selection_changed` signal so the detail-pane behavior is unchanged. Detail pane unchanged in shape; gains `ReferencesSection`.
- `dialogs/topic_create.py`, `topic_edit.py`, `topic_delete.py` using `EntityCrudDialog` and `EntityCrudDeleteDialog`. The parent_topic field declares widget type `"tree_picker"` in its FieldSchema; the base class instantiates `HierarchicalEntityPicker` for that widget type. On Edit, the picker's selectable predicate filters out the topic itself and its descendants (cycle prevention).
- `client.py` extended with `create_topic`, `update_topic`, `delete_topic`. (List/get already exist from v0.1.)
- Tests: `test_topic_dialogs.py`, `test_topics_panel_writes.py` (covers QTreeView selection, expand/collapse, cell-click navigation from slice H carrying forward).

**Acceptance gates:**

- Topics master panel renders as a tree with parent-child nesting. Clicking a parent expands or collapses children. Selecting a node updates the detail pane. (Per AC#6.)
- New Topic, Edit Topic, Delete Topic flows work end-to-end through the new dialogs.
- Parent picker opens as a modal tree; selecting a node populates the parent_topic field; selecting "No parent" clears it.
- Cycle prevention: on Edit, the topic itself and its descendants are non-selectable in the picker.
- Re-parenting works: editing a topic's parent_topic and saving moves it under the new parent.
- `ReferencesSection` renders on Topics detail pane.
- Existing slice H test for Parent Topic cell click navigation continues to pass (the cell click navigation is on the QTreeView's tree column or wherever appropriate; the test may need updating to match the new shape).

**Out of slice:** charter, status, show-deleted.

---

### Step E — Charter and Status replace flows + Sessions detail upgrade

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-E-charter-status-replace.md`

**Deliverables:**

- `base/versioned_replace_dialog.py` housing `VersionedReplaceDialog`. Constructor takes (current_payload, save_callback). Renders a JSON `QPlainTextEdit` (monospace font, ~600px tall, optionally with a `QSyntaxHighlighter` for JSON tokens), a Validate button, Save button, Cancel button. Validate parses the editor text as JSON; on invalid, shows "Invalid: ..." in a status label below the editor; Save is disabled until Validate passes (or Save runs Validate first and refuses to send if invalid). On Save, calls `save_callback(parsed_payload)` through a worker; on success, accepts the dialog.
- `dialogs/charter_replace.py` and `dialogs/status_replace.py` are thin wrappers that instantiate `VersionedReplaceDialog` with the appropriate save callback.
- `panels/charter.py` and `panels/status.py` extended: New Version button in toolbar; Make Current button on each non-current version row in the version-history list pane (or via a context menu — the slice picks the cleanest implementation). Make Current opens a confirmation modal; confirming sends the make-current request through a worker.
- `client.py` extended with `replace_charter(payload)`, `replace_status(payload)`, `make_charter_version_current(version_number)`, `make_status_version_current(version_number)`. If the API doesn't expose a make-current endpoint, the slice adds one (small, additive — `PATCH /charter/versions/{n}/make-current` or equivalent).
- `panels/charter.py` and `panels/status.py` detail panes gain `ReferencesSection`.
- `panels/sessions.py` detail pane gains `ReferencesSection` (closes the v0.2 read-only-panel parity).
- Tests: `test_charter_replace.py`, `test_status_replace.py`, `test_versioned_replace_dialog_base.py`. Sessions tests gain a smoke check that `ReferencesSection` is present on its detail pane.

**Acceptance gates:**

- New Version button on Charter opens `VersionedReplaceDialog` pre-populated with the current charter's JSON. Validate button correctly identifies valid and invalid JSON. Save creates a new version; the version-history list updates. (AC#7.)
- Same flow on Status. (AC#8.)
- Make Current button on a non-current version flips `is_current` after confirmation. (AC#9.)
- `ReferencesSection` renders on Charter, Status, and Sessions detail panes. (AC#10 complete after this slice plus B/C/D.)
- Live refresh: a `curl PUT /charter` while the Charter panel is open causes the new version to appear in the version-history list without manual refresh. (Continues v0.1 file-watch.)
- Test suite passes.

**Out of slice:** show-deleted toggle, About dialog version bump, closeout.

---

### Step F — Show-deleted toggle + polish + closeout

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.2-F-show-deleted-and-closeout.md`

**Deliverables:**

- `panels/decisions.py` extended: Show-deleted checkbox in toolbar. Off by default. State does not persist across launches. Toggling on calls `client.list_decisions(include_deleted=True)`; toggling off goes back to the default. Deleted rows render with strikethrough on Identifier and Title.
- Detail pane button strip: when the selected decision has `status="Deleted"`, the Delete button is replaced with a Restore button. Restore calls `client.restore_decision(identifier)` (which under the hood is `PATCH /decisions/{id}` with `{"status": "Active"}`). Confirmation modal before flipping.
- `client.py` extension: `list_decisions` accepts `include_deleted` parameter (if not already present); `restore_decision` method added.
- API-side additions if needed: `?include_deleted=true` query param on `GET /decisions`; existing `PATCH /decisions/{id}` should already accept status updates per v0.1's contract — the slice confirms.
- About dialog: update the version display path to read `0.2.x` from `pyproject.toml` (the package version is bumped as part of this slice). No code change to `about_dialog.py` if it reads `importlib.metadata` correctly; just the version bump.
- `pyproject.toml`: bump `version = "0.2.0"` (or whatever the v0.1 version was → next patch/minor per the project's existing convention).
- Friction polish from any rough edges noticed during B/C/D/E. The slice is the catch-all for "noticed during build" items, mirroring v0.1 slice H.
- README addition: update `crmbuilder-v2/README.md` "User interface" section to mention v0.2's new write surfaces and link to `ui-PRD-v0.2.md`.
- Closeout governance records:
  - `SES-007` — UI v0.2 build session record. `topics_covered` summarizes the six-prompt build. `summary` enumerates what shipped. `artifacts_produced` lists the prompts and source/test additions. `in_flight_at_end` lists v0.3 candidates (Sessions write surface, References write surface, full styling design pass, search across entities, keyboard shortcuts, export to CSV/JSON, bulk operations, methodology entities post-schema-design).
  - Status update bumped to `"v0.2 complete"` (status v0.8 or whatever's next).
- Tests: `test_show_deleted_toggle.py`, plus any tests for friction-polish items that have a verifiable behavior change. Existing tests continue to pass.

**Acceptance gates:**

- Show-deleted toggle: off, deleted rows hidden; on, deleted rows visible with strikethrough; toggle off again, deleted rows hidden. (AC#11.)
- Restore button on a deleted decision flips status back to Active; the row reappears in the default (Show-deleted-off) view.
- About dialog shows `0.2.x` as the version.
- README "User interface" section reflects v0.2.
- SES-007 and the status update are present in `db-export/sessions.json` and `db-export/status.json`.
- Full test suite passes. Estimated 350+ tests passing.
- All 15 PRD acceptance criteria verified in a final manual pass.

**Out of slice:** anything labelled "deferred to v0.3" in PRD section 2.

---

## 5. Testing Strategy

### What we test in v0.2

- **`EntityCrudDialog` base behavior (high coverage):** field schema → widget construction; required-field check; partial PATCH diff (Edit); inline error label population from API validation envelope; vocab dropdown sourcing.
- **`VersionedReplaceDialog` base behavior (high coverage):** valid JSON → save; invalid JSON → Validate-button feedback; Save-after-Validate flow.
- **`HierarchicalEntityPicker` (medium coverage):** tree population from flat parent-id list; cycle filter via selectable predicate; selection emission.
- **`ReferencesSection` (medium coverage):** fetch on construction; inbound/outbound split; group-by-relationship rendering; click-to-navigate emission.
- **`DateField` (low coverage):** round-trip of `MM-DD-YY` strings; calendar popup integration.
- **Per-entity dialogs (medium coverage each):** smoke construction; field schema correctness; vocab binding; one happy-path Save.
- **Per-entity panel write integration (medium coverage each):** New button opens dialog; Edit/Delete buttons appear on detail pane; successful create triggers select-by-identifier; successful edit/delete refreshes panel.
- **Topics QTreeView (medium coverage):** tree-from-flat-list construction; expand/collapse; selection.
- **Charter/Status replace flows (medium coverage):** New Version dialog round-trip; Make Current confirmation and request.
- **Show-deleted toggle (medium coverage):** state changes, list refetch with parameter, strikethrough rendering, Restore-button behavior.

### What we defer to v0.3

- Click-through interaction tests for the broader workflows (filling a multi-field create dialog, clicking Save, verifying the row in the table is present and contents match).
- Visual regression testing.
- Cross-platform automated runs.
- Stress testing (panels with hundreds of records).

### Target

- Full UI test suite still runs in under 60 seconds (v0.2's additions roughly double the count).
- Every new test imports its fixtures from `conftest.py` rather than re-declaring fixtures inline.

---

## 6. Dependencies and Configuration

### New Python dependencies

None. v0.2 uses only `PySide6`, `httpx`, and `pytest-qt`, all already present from v0.1.

### Configuration

Unchanged from v0.1. `crmbuilder_v2.config.get_settings()` is the source.

### File system locations

Unchanged from v0.1. Logs at `~/.crmbuilder-v2/ui.log`; database at `crmbuilder-v2/data/v2.db`; snapshots at `PRDs/product/crmbuilder-v2/db-export/`.

---

## 7. Commit Strategy

Each prompt produces one or more commits, all prefixed `v2:`. Suggested per-prompt commit shapes:

| Prompt | Suggested commits |
|---|---|
| A | `v2: ui v0.2 planning records — SES-006, DEC-026 through DEC-031` <br> `v2: ui v0.2 widgets and CRUD dialog base` <br> `v2: ui v0.2 — migrate decisions dialogs to shared base` |
| B | `v2: ui risks CRUD — create, edit, delete + references section` |
| C | `v2: ui planning items CRUD — create, edit, delete + references section` |
| D | `v2: ui topics CRUD — QTreeView, hierarchical picker, dialogs` |
| E | `v2: ui charter and status replace flows + sessions references section` |
| F | `v2: ui show-deleted toggle + polish + v0.2 closeout` |

After each prompt's commits land, the v2 status record gets a one-line update reflecting progress. At end of F, status is updated to `"v0.2 complete"` and SES-007 is appended.

---

## 8. Risk Register

Prompt-level risks (cross-cutting risks live in PRD section 9):

| Risk | Slice | Mitigation |
|---|---|---|
| The slice A refactor of the existing decisions dialogs causes a regression that v0.1's existing tests don't catch (e.g., a UX detail like focus order) | A | The v0.1 test suite is the formal gate. The slice's reporting includes a manual visual verification of the Decisions surface (create, edit, delete, supersedes clear, error inline rendering). If a UX-only regression slips through, the F polish slice catches it. |
| Field-schema mismatch between dialog and access-layer Pydantic model on a per-entity basis (e.g., dialog has 6 fields, access layer expects 7) | B, C, D | The slice prompt explicitly reads the SQLAlchemy model and Pydantic schema before declaring the field schema. If the access layer evolves between slice planning and slice execution, the slice prompt resolves the mismatch by following the access layer (single source of truth). |
| Tree-from-flat-list construction in `HierarchicalEntityPicker` becomes O(N²) on large topic counts | D | v2's topic count is small (under 30 today, growing slowly). If the test fixture sets up 1000 topics and the test takes >1s, the slice optimizes; otherwise, it ships as-is. |
| The JSON editor in `VersionedReplaceDialog` doesn't catch a payload-shape error that the access layer rejects (e.g., the user types valid JSON but with the wrong top-level keys) | E | This is by design — the dialog is schema-blind. API validation errors return through the worker error handler and surface in the generic `ErrorDialog`. The user fixes and resaves. If the friction is significant in practice, v0.3 introduces a structured form per Q4 of the planning conversation. |
| `client.list_decisions(include_deleted=True)` requires a REST API change that turns out to be more invasive than expected | F | The change is mechanical (one query parameter, one branch in the repository's `list_all`). If unexpectedly invasive, the slice surfaces it as a deferral and the toggle ships in a follow-up rather than blocking the rest of slice F. |
| Make-current endpoint design conflicts with the existing access-layer pattern for `is_current` flipping | E | The slice reads the existing access-layer code first. If the access layer already exposes a `make_current` repository method, the API endpoint is a thin wrapper. If not, the slice adds the repository method and the endpoint together. |

---

## 9. Order of Operations Across the Series

The six prompts are sequential — each builds on the previous. A is the prerequisite for all subsequent slices (the framework lands in A). B/C/D could be parallelized in principle (each is a self-contained per-entity slice that depends only on A); in practice, single-developer execution does them in order.

After approval of this plan:

1. v2-ui-v0.2-A is drafted, reviewed, and executed.
2. Results reviewed; any prompt-level fixes applied before proceeding.
3. Repeat through v2-ui-v0.2-F.
4. After F, the closeout records (SES-007, status v0.8 or next) are written. v0.2 ships.

If review of any prompt's results surfaces a missed requirement that affects subsequent prompts, the affected later prompts are re-drafted before execution. The plan is a living document for the duration of the build; any material change is committed as a plan version bump (`0.2`, `0.3`, etc.) with an entry in the change log.

---

## 10. Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-08-26 | Initial draft. Decomposes the UI v0.2 build into six sequential prompts (v2-ui-v0.2-A through v2-ui-v0.2-F). Captures the new `widgets/` subpackage layout, the schema-driven `EntityCrudDialog` and `VersionedReplaceDialog` patterns, and the per-slice deliverables, acceptance gates, and out-of-slice notes. |
