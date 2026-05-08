# CRMBuilder v2 — User Interface PRD

**Version:** 0.2 (draft)
**Last Updated:** 05-08-26
**Status:** Draft — pending approval
**Predecessor:** `ui-PRD-v0.1.md` (shipped 05-09-26 per SES-005)

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.2 | 05-08-26 | Second iteration of the v2 desktop UI. Frames v0.2 as "complete the write surface" — adds full create/read/update/delete for Risks, Planning Items, and Topics, plus versioned replace flows for Charter and Status, plus generalized reference rendering on every detail pane, plus calendar widget on date inputs and "Show deleted" toggle on Decisions. Captures six architectural decisions (DEC-026 through DEC-031) for recording in the v2 database after PRD approval. |

---

## 1. Overview

### Purpose

This document specifies the requirements for CRMBuilder v2 user interface (UI) v0.2. v0.1 shipped a standalone PySide6 desktop application that consumed the storage system REST API with read-only views for all seven governance entity types and full create/read/update/delete operations for decisions. v0.2 generalizes the write surface beyond decisions, completes the version-history UX for Charter and Status, and standardizes reference rendering across every detail pane. v0.2 is the build specification handed to Claude Code, which executes it through a six-prompt slice series.

### Background

UI v0.1 shipped on 05-09-26 (SES-005, status v0.6, phase `"v0.1 complete"`). Its scope was deliberately narrow: prove the architectural pieces — subprocess management, threading, error envelope handling, file-watch refresh, dialog patterns — on a single end-to-end CRUD path (decisions). Other entities received read-only treatment.

Daily use of v0.1 surfaces a clear gap: every governance write that isn't recording a decision still has to go through `curl` or MCP. Recording a risk, adding a planning item, defining a topic, creating a new charter version, updating status — all of these flow through tooling outside the UI. The v0.1 PRD anticipated this and captured the deferral pattern: "v0.2 is the intended workstream that closes those gaps, prioritized by the friction observed during v0.1 use."

The v0.2 planning conversation (SES-006) confirmed the deferred items and selected a coherent v0.2 thesis — "complete the write surface" — that closes the operational gap without expanding the architectural surface. The conversation produced this PRD, the companion implementation plan, and a six-prompt build series. The architectural pieces v0.1 proved (lifecycle, threading, error envelope, refresh, dialog mechanics) generalize cleanly; v0.2 is mostly additive.

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records.

Existing decisions still in force from v0.1:

- **DEC-018** — UI is a standalone application, not embedded in the v1 PySide6 app.
- **DEC-019** — UI consumes the REST API over HTTP, not the access layer directly.
- **DEC-020** — v0.1 scope: read-only across all entities, full CRUD for decisions only. (Superseded only in scope by DEC-026; the standalone-application + REST-only posture continues.)
- **DEC-021** — Sidebar navigation with master/detail panes.
- **DEC-022** — File-watch on `db-export/` for live refresh, manual Refresh button as fallback.
- **DEC-023** — Detect-then-launch API subprocess management.
- **DEC-024** — Native Qt look for v0.1; styling pass deferred. (v0.2 honors this — the styling design pass is deferred again, to v0.3.)

Forthcoming decisions (to be recorded after this PRD is approved, see Section 11):

- **DEC-026** — v0.2 frame is "complete the write surface," with calendar widget and Show-deleted toggle as carve-outs.
- **DEC-027** — v0.2 entity scope: full CRUD for Risks, Planning Items, Topics; versioned replace + history browsing for Charter and Status; Sessions and References deferred to v0.3.
- **DEC-028** — Extract `EntityCrudDialog` and `VersionedReplaceDialog` base classes; v0.1's decisions dialogs become the first user of the CRUD base.
- **DEC-029** — Charter/Status replace flow uses a raw JSON payload editor with Validate button; Make Current affordance is included in v0.2.
- **DEC-030** — Topics master panel switches to `QTreeView`; parent_topic field uses a reusable `HierarchicalEntityPicker` widget.
- **DEC-031** — Reference rendering generalized via a shared `ReferencesSection` widget on every detail pane, both directions, grouped by relationship type, no filtering in v0.2.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.2.

1. **Foundation refactor — extract shared dialog base classes.** A new `EntityCrudDialog` base class is extracted from v0.1's decisions create/edit/delete dialogs, parameterized by a per-entity field schema (label, widget type, required flag, validation regex, vocab source). The decisions dialogs become the first user of the base — visible behavior unchanged from v0.1. A separate `VersionedReplaceDialog` base class supports Charter and Status flows.

2. **Reusable widgets under `ui/widgets/`.** Three widgets land alongside the foundation refactor:
   - `DateField` — wraps `QDateEdit` with the calendar popup enabled, configured to accept and emit the `MM-DD-YY` string the access layer expects. Replaces the plain-text date input on the existing Decisions create/edit dialog and is used by all new dialogs that have date fields.
   - `ReferencesSection` — fetches and renders inbound and outbound references for a given (entity_type, identifier), grouped by relationship type, with click-to-navigate behavior. Replaces v0.1's bespoke decisions-pane inbound rendering and lands on every other entity's detail pane.
   - `HierarchicalEntityPicker` — modal tree picker for hierarchical entity fields with a "selectable predicate" callback for cycle filtering. Used by the Topics dialog's parent_topic field; available for future hierarchical fields in methodology entities.

3. **Risks CRUD.** New Risk button in the Risks panel toolbar opens a Create dialog. Edit and Delete buttons appear on the Risks detail pane. Vocabularies (`RISK_PROBABILITIES`, `RISK_IMPACTS`, `RISK_STATUSES`) imported from `vocab.py`. Inline validation surfaces field errors before the API roundtrip.

4. **Planning Items CRUD.** Same shape as Risks. Vocabularies (`PLANNING_ITEM_TYPES`, `PLANNING_ITEM_STATUSES`) imported from `vocab.py`.

5. **Topics CRUD with hierarchical UX.** Topics master panel switches from v0.1's indented `QTableView` to a `QTreeView` backed by a `QStandardItemModel`. New / Edit / Delete dialogs use `EntityCrudDialog`; the parent_topic field uses `HierarchicalEntityPicker` with cycle filtering (the topic itself and its descendants are non-selectable on Edit). Re-parenting is supported.

6. **Charter and Status replace flows.** New Version button on the Charter and Status panel toolbars opens a `VersionedReplaceDialog` with a raw JSON payload editor pre-populated with the current version's payload, a Validate button that runs a client-side JSON parse before allowing Save, and (on the panel's version list) a Make Current affordance on non-current versions with a confirmation modal. Optional `QSyntaxHighlighter` for JSON tokens if Qt makes it convenient.

7. **Reference rendering on every detail pane.** Shared `ReferencesSection` widget appears on Decisions (replacing v0.1's bespoke rendering), Sessions, Risks, Planning Items, Topics, Charter, and Status detail panes. The widget shows inbound and outbound references in two clearly-labeled blocks, each grouped by relationship type with a count header. Empty sections render a "(none)" placeholder so layout is consistent.

8. **"Show deleted" toggle on Decisions.** Checkbox in the Decisions panel toolbar; off by default. When on, the panel calls `list_decisions(include_deleted=True)` and renders deleted rows with strikethrough. Detail pane's Delete button changes to Restore on a deleted record if the access layer supports un-delete (a one-call status PATCH); otherwise viewing-only. State does not persist across launches.

9. **Calendar widget on Decision Date inputs.** `DateField` widget replaces the plain-text MM-DD-YY input on the v0.1 Decisions create/edit dialog and is used by any v0.2 dialog that has a date field. Slice G's existing client-side format regex for date inputs becomes redundant for the calendar-backed fields and is removed; identifier-format validation stays.

10. **Storage layer additions where required for the UI surface.** v0.2 is primarily UI work, but two small storage additions land alongside their consumers:
    - **List-with-include-deleted parameter.** v0.1's `list_decisions` already accepts `include_deleted`; the corresponding REST endpoint either accepts a `?include_deleted=true` query parameter or a UI-side join is acceptable. Scope of work depends on the existing API surface — the slice that needs it makes the addition.
    - **Restore endpoint or PATCH path for soft-deleted decisions.** If un-delete isn't already reachable through `PATCH /decisions/{id}` with `status="Active"`, a thin endpoint is added. If it already works, no addition.

### Out of Scope

The following are explicitly deferred to v0.3 or later.

- **Sessions write surface.** Sessions are append-only per DEC-013, written by Claude at conversation close per DEC-014. The UI does not author session records. This is a governance-level boundary, not a UI deferral; if it ever changes, the change starts with revising DEC-013.
- **References write surface.** The references graph is its own subsystem — relationship vocabulary discoverability, source/target picker UX, and edge-deletion semantics are a focused design conversation that v0.3 takes on as its own slice. v0.2 keeps References as a list-only read panel with no detail pane (unchanged from v0.1).
- **Filterable references on detail panes.** Per the v0.1 PRD §10 Open Question 4, references could be filtered by relationship type. Deferred again — v0.2's reference volume isn't pressuring readability, and the dropdown UI surface is best designed against a real "this is unreadable" moment rather than in the abstract.
- **Full styling design pass.** DEC-024 deferred this from v0.1 to "v0.2 or later." v0.2's frame is the write surface; piling a designed visual pass on top would make v0.2 a less coherent release. Deferred to v0.3.
- **Optimistic concurrency control for edits.** v0.1's last-write-wins posture continues. If two writers race on the same record, the second write replaces the first. v0.3 may introduce version-stamped PATCH if real friction surfaces.
- **Bulk operations.** Multi-row select + delete, multi-row update. Not in v0.2.
- **Global search across entities.** A search box that finds matching records across all entity types. Plausible v0.3 candidate.
- **Keyboard shortcuts beyond Qt defaults.** Tab navigation, Enter-to-Save, Escape-to-Cancel are inherited from Qt. Custom shortcuts (Ctrl-N for new record, etc.) are deferred.
- **Export visible panel to CSV/JSON.** Plausible v0.3 candidate.
- **Methodology-entity panels.** Personas, processes, fields, requirements, manual-config items, test specs — these are post-v0.2 work, gated on the methodology-entity schema being designed (status doc's "build after v0.1" list).

---

## 3. Architecture

### Process model

Unchanged from v0.1. The UI process spawns or attaches to the API subprocess (DEC-023), watches `db-export/` (DEC-022), and reaches the storage system exclusively through the REST API (DEC-019).

```
┌─────────────────────────────────────────────────────┐
│  PySide6 UI process (crmbuilder-v2-ui)              │
│                                                     │
│  ┌──────────────────┐    ┌──────────────────────┐   │
│  │  UI thread       │    │  QThread workers     │   │
│  │  (Qt event loop) │◄──►│  (HTTP calls)        │   │
│  └──────────────────┘    └──────────┬───────────┘   │
│                                     │               │
│  ┌──────────────────┐               │               │
│  │  QFileSystem-    │               │               │
│  │  Watcher         │               │               │
│  └──────────────────┘               │               │
└─────────────────────────────────────┼───────────────┘
                                      │ HTTP
┌─────────────────────────────────────▼───────────────┐
│  REST API subprocess (crmbuilder-v2-api)            │
└─────────────────────────────────────────────────────┘
```

### Layer responsibilities

v0.2 keeps every v0.1 layer and adds two:

| Layer | Module | Status | Responsibility |
|---|---|---|---|
| Application shell | `crmbuilder_v2.ui.app` | unchanged | Qt application initialization, main window, sidebar, content area, lifecycle wiring |
| Storage client | `crmbuilder_v2.ui.client` | extended | Adds CRUD methods for Risks, Planning Items, Topics; replace methods for Charter, Status; references-for-entity fetch method |
| Workers | `crmbuilder_v2.ui.workers` | unchanged | `QThread` wrappers around storage client calls |
| Server lifecycle | `crmbuilder_v2.ui.server_lifecycle` | unchanged | Probe, spawn, track, terminate the API subprocess |
| Refresh service | `crmbuilder_v2.ui.refresh` | unchanged | `QFileSystemWatcher` on the snapshot directory; per-entity-type "data changed" signals |
| Entity panels | `crmbuilder_v2.ui.panels.*` | extended | Each entity panel adds its write toolbar buttons and `ReferencesSection` on its detail pane. Topics swaps to `QTreeView` |
| Dialogs | `crmbuilder_v2.ui.dialogs.*` | extended | New per-entity create/edit/delete dialogs for Risks, Planning Items, Topics. New replace dialogs for Charter, Status |
| Base widgets | `crmbuilder_v2.ui.base` | extended | New `EntityCrudDialog` base. New `VersionedReplaceDialog` base. Existing `ListDetailPanel` and `VersionedPanel` unchanged |
| **Reusable widgets** | `crmbuilder_v2.ui.widgets` | **new** | `DateField`, `ReferencesSection`, `HierarchicalEntityPicker` |

### Configuration

Unchanged from v0.1. The UI reads `crmbuilder_v2.config.get_settings()` directly. No new environment variables, no config file additions.

---

## 4. Functional Requirements

### 4.1 Foundation refactor

`EntityCrudDialog` (under `ui/base/`) is the parameterized base class for create and edit dialogs. Its construction takes a `field_schema` describing each form field — label, widget type (`QLineEdit`, `QComboBox`, `QPlainTextEdit`, `DateField`, `HierarchicalEntityPicker`, etc.), required flag, optional vocab source for combo boxes, optional regex validator. The dialog renders the form, manages the inline-error labels, runs Save through a worker, parses validation errors from the API envelope, and routes errors to the correct field labels or the generic `ErrorDialog`.

`EntityCrudDeleteDialog` (also under `ui/base/`) is a parameterized confirmation dialog. Takes entity identifier and a display title; renders confirmation text; calls the appropriate client `delete_*` method on confirm.

`VersionedReplaceDialog` (under `ui/base/`) renders a JSON payload editor with a Validate button and a Save button. Takes the current payload (pre-populates the editor), validates JSON syntax client-side before allowing Save, sends the parsed payload through the appropriate client method (e.g., `replace_charter(payload)`).

V0.1's three decisions dialogs (`decision_create.py`, `decision_edit.py`, `decision_delete.py`) become subclasses or thin wrappers of the new bases. All v0.1 visible behavior is preserved — DEC-NNN format validation, Active/Superseded/Withdrawn status dropdown, supersedes/superseded_by handling, the existing inline error UX, the existing soft-delete confirmation flow.

### 4.2 Risks CRUD

Risks panel toolbar gets a New Risk button. Detail pane gets Edit and Delete buttons (rendered when a row is selected, mirrors v0.1's decisions detail-pane button strip).

Create dialog fields (per the access-layer schema):

- Identifier — text, required, regex validator (`RSK-NNN` or whatever the existing convention is; check against existing data on first slice run)
- Title — text, required
- Description — multi-line text
- Probability — combo box, required, items from `RISK_PROBABILITIES` (Low, Medium, High)
- Impact — combo box, required, items from `RISK_IMPACTS` (Low, Medium, High)
- Status — combo box, required, items from `RISK_STATUSES` (Open, Mitigated, Accepted, Closed)
- Mitigation — multi-line text
- (any other fields the storage schema defines for Risk; the slice prompt resolves the field set against the SQLAlchemy model at build time)

Edit dialog has the identifier read-only, partial PATCH semantics matching v0.1 decisions: only changed fields are submitted.

Delete dialog is a confirmation modal. v0.1's soft-delete pattern for decisions does not extend to risks unless the access layer supports it; if risks are physically deleted on `DELETE /risks/{id}`, the delete dialog's ConflictError branch (referenced records prevent deletion) is included.

### 4.3 Planning Items CRUD

Same shape as Risks. Vocabularies are `PLANNING_ITEM_TYPES` (planning_dimension, open_question, pending_work) and `PLANNING_ITEM_STATUSES` (Open, Resolved, Deferred).

### 4.4 Topics CRUD with hierarchical UX

Topics master panel switches from v0.1's indented `QTableView` (one column with name-prefix indentation) to a `QTreeView` backed by `QStandardItemModel`. Roots are top-level topics; children nest under parents via the `parent_topic_id` field. Single-row selection, alphabetical within each level, expand/collapse per-row. The tree column shows the topic's name; identifier and other fields appear in the detail pane.

Create dialog fields:

- Identifier — text, required
- Name — text, required
- Description — multi-line text
- Parent Topic — `HierarchicalEntityPicker` (modal), optional. The picker opens a tree view of all topics; the user selects a node or "No parent." On Edit, the topic itself and its descendants are filtered out via the picker's selectable-predicate callback to prevent cycles.

Edit dialog supports re-parenting (the parent_topic field is editable). Delete dialog matches the Risks/Planning Items pattern.

### 4.5 Charter and Status replace flows

Charter and Status panels each get a New Version button in the toolbar. Clicking opens a `VersionedReplaceDialog` pre-populated with the current version's payload as pretty-printed JSON. The dialog has:

- A `QPlainTextEdit` (or equivalent) editor showing the JSON payload, ~600px tall, monospace font. Optional `QSyntaxHighlighter` for basic JSON token coloring.
- A Validate button that parses the editor's text as JSON and shows the result inline ("Valid JSON" / "Invalid: line N column M, expected ...").
- A Save button that runs Validate first; if valid, sends `PUT /charter` (or `PUT /status`) with the parsed payload as the new version. On success, dismisses the dialog; the panel refreshes (file-watch path will catch it; explicit refresh is a fast-path safety net).
- A Cancel button.

The version-history list pane (already present from v0.1) is extended: each non-current version row gets a Make Current button (or context-menu action — implementer's call between row buttons and right-click menu). Clicking opens a confirmation modal; confirming sends a request that flips `is_current` to the selected version. The storage system supports this; if the existing API doesn't expose it directly, a thin `PATCH /charter/versions/{n}/make-current` (or equivalent) is added in the slice that needs it.

### 4.6 Reference rendering on detail panes

A new `ReferencesSection` widget under `ui/widgets/references_section.py`. Constructor takes `entity_type` (e.g., `"decision"`) and `identifier` (e.g., `"DEC-018"`), plus the storage client. On construction, fires a worker that fetches references where `source_type=entity_type AND source_id=identifier` (outbound) and `target_type=entity_type AND target_id=identifier` (inbound) — either as two API calls or one if the API exposes a combined endpoint.

Render shape:

```
References
──────────
Inbound (3)
  Decided in (2)
    SES-002 — Planning dimension #5 → 
    SES-004 — UI v0.1 planning      → 
  Is about (1)
    TOP-3 — Schema design            → 

Outbound (1)
  Supersedes (1)
    DEC-007 — Earlier topics design  → 
```

Click any item, navigate to it (mirrors v0.1's decisions inbound-reference click behavior). Section header is always rendered; if both inbound and outbound are empty, a single "(none)" placeholder appears so the layout is consistent.

`ReferencesSection` lands on every panel's detail pane: Decisions (replacing v0.1's bespoke rendering), Sessions, Risks, Planning Items, Topics, Charter, Status. References panel itself stays list-only with no detail pane (unchanged).

For Decisions specifically: the existing top-level Supersedes / Superseded By fields remain (they are direct columns on the decision record, not references-table edges). The outbound `supersedes` reference rendered through `ReferencesSection` is somewhat redundant with the existing field; suppress it via an optional `exclude_relationships` constructor parameter on `ReferencesSection` if the redundancy reads weirdly during build. Trivial conditional.

### 4.7 "Show deleted" toggle on Decisions

A `QCheckBox("Show deleted")` widget added to the Decisions panel toolbar, between the Refresh button and the New Decision button. Off by default. State does not persist across launches.

When toggled on:
- The panel's list refetches via `client.list_decisions(include_deleted=True)`. The slice that builds this confirms the client method's signature; if it doesn't currently accept the parameter, the slice extends it (and extends the underlying API endpoint if needed).
- Deleted rows render with strikethrough text on the Identifier and Title columns. The Status column already shows `Deleted`.
- The detail pane's Delete button is replaced with a Restore button on rows whose status is `Deleted`, IF the access layer exposes a path to flip status back to Active. v0.1's soft-delete is a status PATCH, so `PATCH /decisions/{id}` with `{"status": "Active"}` should work; the slice confirms.
- The Edit button stays available on deleted rows. (The access layer permits or denies; the API surfaces the result.)

When toggled off:
- The panel refetches with the default `include_deleted=False`. Deleted rows disappear from the list.

### 4.8 Calendar widget on Decision Date inputs

A new `DateField` widget under `ui/widgets/date_field.py` wraps `QDateEdit` with the calendar popup enabled (`setCalendarPopup(True)`). Configured to:
- Display dates as `MM-dd-yy` (Qt's `setDisplayFormat("MM-dd-yy")`).
- Emit dates as the same `MM-DD-YY` string the access layer expects.
- Default to today on a fresh dialog (Create); pre-populated with the record's existing date on Edit.

`DateField` replaces the plain-text `QLineEdit` for Decision Date in the v0.1 Decisions create and edit dialogs. The slice G client-side regex validation for date format becomes redundant for `DateField`-backed inputs and is removed; identifier format validation stays. Any v0.2 entity dialog that has a date field uses `DateField` from the start.

### 4.9 Application shutdown, startup, refresh, error handling, and connection management

All unchanged from v0.1. v0.2's new dialogs and panels integrate with v0.1's existing patterns:

- All HTTP calls go through `QThread` workers (v0.1 §5.1).
- Validation errors with a `field` key surface inline; missing-field errors surface in the generic `ErrorDialog` (v0.1 §4.11).
- `StorageConnectionError` during a write closes the dialog via `reject()` and lets the lifecycle's existing crash-banner handle the connection-lost surface (v0.1 §4.3).
- The `RefreshService` (v0.1 slice F + slice H content-hash gating) catches every successful write and refreshes the affected panel within ~500ms.

---

## 5. Non-Functional Requirements

### 5.1 Threading

Unchanged from v0.1. Every HTTP call runs in a `QThread` worker. The UI thread is reserved for Qt event handling, widget updates, and file-watcher signal slots.

### 5.2 Responsiveness

- Dialog open completes in under 100ms (data already in memory from the list, except for the explicit Edit refetch which inherits v0.1's pattern).
- List refetch on a panel switch completes in under 500ms on localhost (matches v0.1).
- Manual Refresh button feedback ("Loading…") appears within 50ms of click (matches v0.1).
- `ReferencesSection` initial fetch on detail-pane open completes in under 500ms; the section renders a "Loading…" state while fetching to avoid layout pop.

### 5.3 Resource use

Unchanged from v0.1. File watcher watches one directory; HTTP client uses connection pooling; worker threads short-lived.

### 5.4 Logging

Unchanged from v0.1. UI logs to `~/.crmbuilder-v2/ui.log` (rotated). Subprocess lifecycle, HTTP errors, file-watcher events. No request/response bodies.

### 5.5 Platform support

Linux primary. macOS verified. Windows not a v0.2 target.

### 5.6 Dependencies

No new external dependencies for v0.2. All needed libraries are already present from v0.1:
- `PySide6` for Qt (existing).
- `httpx` for HTTP (existing).
- `pytest-qt` for tests (existing).

---

## 6. Acceptance Criteria

The UI v0.2 is considered functionally complete when all of the following are true.

1. The existing v0.1 Decisions surface continues to work end-to-end after the foundation refactor: create, edit, delete, soft-delete + Show-deleted-toggle + restore, supersedes link clearing, validation error inline rendering, file-watch refresh, About dialog. v0.1's 264 tests still pass.

2. `New Risk` button in the Risks panel opens a Create dialog with all fields per the access-layer schema. Filling required fields and clicking Save creates the record, closes the dialog, refreshes the panel, and selects the new row.

3. Editing a selected risk via the Edit button opens a pre-populated dialog. Modifying a field and clicking Save updates the record. The panel reflects the change.

4. Deleting a selected risk via the Delete button opens a confirmation dialog. Confirming deletes the record. The panel reflects the deletion.

5. Creating, editing, and deleting Planning Items works the same way (criteria 2-4 mirrored).

6. Creating, editing, and deleting Topics works the same way. The Topics master panel renders as a `QTreeView` with parent-child nesting. The Topic create/edit dialog's parent_topic field is a tree picker that filters out the topic itself and its descendants on Edit (cycle prevention).

7. `New Version` button on the Charter panel opens a `VersionedReplaceDialog` pre-populated with the current charter's JSON payload. Validate button correctly identifies valid and invalid JSON. Save creates a new charter version and the version-history list updates.

8. Same flow works on the Status panel.

9. Make Current button on a non-current Charter or Status version flips `is_current` to that version after confirmation.

10. The shared `ReferencesSection` widget renders correctly on every detail pane: Decisions, Sessions, Risks, Planning Items, Topics, Charter, Status. Inbound and outbound references appear in their own grouped sections; click navigates to the referenced record.

11. "Show deleted" toggle on the Decisions panel: off by default; toggling on reveals deleted records with strikethrough; the detail pane's Delete button is replaced with Restore on deleted rows; Restore PATCHes the status back to Active.

12. Calendar widget appears on the Decision Date input across all date inputs in v0.2's dialogs. Selecting a date emits the correct `MM-DD-YY` string to the API.

13. Inline validation works for all new dialogs: empty required fields surface "This field is required."; format errors surface field-specific messages; API validation errors keyed to a field surface inline; field-less API errors surface in the generic `ErrorDialog`.

14. Writing a new risk / planning item / topic / charter version / status version via MCP while the UI is open causes the affected panel to update without manual refresh (v0.1 file-watch pattern continues to apply).

15. The full v2 test suite passes. v0.1's 264 tests + new tests across slices A through F. Estimated 350+ passing.

---

## 7. Implementation Approach

The implementation plan (`ui-v0.2-implementation-plan.md`) breaks this PRD into six prompts (`v2-ui-v0.2-A` through `v2-ui-v0.2-F`), each producing an independently testable slice. The plan is the operational counterpart to this PRD and is approved separately.

In summary:

- **A — Foundation refactor.** Extract `EntityCrudDialog` and (foundation for) `VersionedReplaceDialog`. Build `DateField` and `ReferencesSection` widgets. Migrate the Decisions surface to use them. v0.1 visible behavior unchanged.
- **B — Risks CRUD.** First user of the new framework. Risks dialogs + Risks references.
- **C — Planning Items CRUD.** Mirrors B. Planning Items dialogs + references.
- **D — Topics CRUD + QTreeView master + HierarchicalEntityPicker.** Topics dialogs + the new picker widget + the QTreeView swap + Topics references.
- **E — Charter and Status replace flows + Sessions detail upgrade.** `VersionedReplaceDialog`, JSON editor, Make Current. `ReferencesSection` lands on Charter, Status, and Sessions detail panes.
- **F — "Show deleted" toggle + polish + closeout.** Decisions Show-deleted, About dialog version bump, status update, SES-007 closing record.

---

## 8. Dependencies and Constraints

### Dependencies on the storage system

v0.2 may require small additive storage-layer changes:

- `list_decisions` extending to accept `include_deleted` at the REST layer (slice F).
- A `make_current` path for Charter/Status versions (slice E) if not already present.
- Restore-from-soft-delete path for decisions (slice F) if `PATCH /decisions/{id}` with `status="Active"` doesn't already work.

These are mechanical additions and are made in the slice that needs them, with a one-paragraph note in that slice's prompt explaining the addition. They do not require their own architectural conversation.

### No changes to the v1 application

Unchanged from v0.1. v2 work is strictly additive to v1.

### Constraint: process model still assumes localhost

Unchanged from v0.1. The detect-then-launch model and file-watch refresh strategy assume UI and API share a filesystem and host.

### Constraint: dialog base classes must not regress v0.1 Decisions behavior

The slice A refactor extracts shared bases from the existing decisions dialogs. v0.1's existing 264 tests are the regression net; the refactor is acceptance-gated on those tests continuing to pass plus new tests for the extracted framework.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Slice A's foundation refactor regresses v0.1 Decisions UI | Low | High | v0.1's 264 tests are the regression net. Slice A is acceptance-gated on every prior test passing plus framework tests. The refactor is bounded to the dialog code; the panel and lifecycle stay untouched. |
| `EntityCrudDialog` field-schema abstraction doesn't generalize cleanly to entities with novel field shapes (methodology entities post-v0.2 — rich text, attachments, multi-entity pickers) | Medium | Low | The base is designed for the four CRUD entities currently in scope (decisions, risks, planning items, topics). When methodology entities are designed, the base evolves with a clear forcing function. v0.2 doesn't try to anticipate every future shape. |
| Charter and Status payload schemas diverge enough that a single `VersionedReplaceDialog` can't serve both | Low | Low | The dialog is intentionally schema-blind — it presents JSON, validates JSON, submits JSON. The schemas live in the storage layer's Pydantic models, not the UI. |
| Topic re-parenting introduces cycles despite UI cycle filtering (e.g., race between two writers) | Low | Low | The UI filters the picker but does not enforce. The access layer enforces structural validity; if a race produces a cycle attempt, the API returns a validation error and the dialog surfaces it inline. |
| Reference fetching becomes the long-pole on detail-pane open if records accumulate many references | Low | Medium | The widget renders a "Loading…" state during fetch so the rest of the detail pane is usable. If volume becomes a real problem, slice F polish or v0.3 can introduce pagination or lazy loading. |
| Show-deleted toggle's strikethrough rendering is visually inconsistent across platforms | Medium | Low | Use Qt's standard text-decoration via stylesheet on the affected rows. macOS and Linux render the same; Windows is not a v0.2 target. |
| Slice F's storage additions (include_deleted query param, make_current endpoint, restore path) block on storage refactor | Low | Medium | Each addition is mechanical and backwards-compatible. If any addition turns out to be more invasive than expected, the slice surfaces it as a v0.3 deferral and ships without that affordance. |

---

## 10. Open Questions

1. **What's the right vocabulary for "Make Current" on a charter/status version?** "Make Current," "Promote," "Restore," "Activate" — pick one and use consistently. Recommend "Make Current" unless a v0.2 build session surfaces friction.

2. **Should the QTreeView for Topics support drag-to-reparent?** Out of scope for v0.2 per slice D; re-parenting is via the dialog only. If users find the dialog parent-picker awkward, drag support is a v0.3 candidate.

3. **Should Risks and Planning Items soft-delete like Decisions, or physical-delete?** Decisions are soft-delete to preserve referential integrity (v0.1 slice H). Risks and Planning Items may have inbound references too. Recommend soft-delete parity if the schema supports it; the slice that builds delete confirms with the access-layer maintainer (i.e., reads the existing repository code) and either follows the existing semantics or adds the same migration shape v0.1 slice H added for decisions.

4. **Should the JSON payload editor offer a "diff with current" view?** Useful when the user is doing surgical edits on a long payload. Recommend defer; a Validate button covers the immediate need. v0.3 if friction surfaces.

---

## 11. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and DEC-025 (conversation_reference convention + seed-prompt-in-topics_covered), the planning conversation that produced this PRD is captured in the v2 database after PRD approval. The session and decision records are written through the REST API or MCP server as part of the v2-ui-v0.2-A prompt's setup steps.

Records to write:

- **SES-006** — UI v0.2 planning. Status: Complete. `conversation_reference`: descriptive text per DEC-025 ("Claude.ai planning conversation that produced ui-PRD-v0.2.md, ui-v0.2-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.2 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."). `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement>"`, followed by a structured summary of the eight architectural questions discussed (release shape, entity scope, dialog architecture, payload editor, hierarchical UX, reference rendering, small batched items, slice breakdown).
- **DEC-026** — v0.2 frame is "complete the write surface."
- **DEC-027** — v0.2 entity scope: full CRUD for Risks/Planning Items/Topics; replace+history for Charter/Status; Sessions and References deferred.
- **DEC-028** — Extract `EntityCrudDialog` and `VersionedReplaceDialog` base classes; decisions becomes the first user.
- **DEC-029** — Charter/Status replace via raw JSON editor with Validate button + Make Current affordance.
- **DEC-030** — Topics master panel switches to QTreeView; parent_topic uses a reusable `HierarchicalEntityPicker` widget.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget on every detail pane, both directions, grouped, no v0.2 filtering.
- **References** — `decided_in` from SES-006 to each of DEC-026 through DEC-031.

A status update reflecting that UI v0.2 is now in build (slice A in progress, phase `"v0.2 in build"`) is also appropriate at the same time.
