# CRMBuilder v2 — User Interface PRD

**Version:** 0.3 (draft)
**Last Updated:** 05-09-26 17:30
**Status:** Draft — pending approval
**Predecessor:** `ui-PRD-v0.2.md` (shipped 05-09-26 per SES-007)

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.3 | 05-09-26 | Third iteration of the v2 desktop UI. Frames v0.3 as "close the testability gap" — adds full create/delete for References (the graph edges between entities), append-only create for Sessions, refactors `ListDetailPanel` to expose master-widget and context-menu factory methods, and adopts right-click context menus uniformly across every entity row as a global UX principle. Captures six architectural decisions (DEC-032 through DEC-037) for recording in the v2 database after PRD approval. |

---

## 1. Overview

### Purpose

This document specifies the requirements for CRMBuilder v2 user interface (UI) v0.3. v0.2 shipped full create/edit/delete for Risks, Planning Items, and Topics, plus versioned-replace for Charter and Status, plus generalized reference rendering on every detail pane. v0.3 closes the remaining gap that prevents v2 from being used as a real governance tool without leaving the UI: References cannot be created or deleted through the UI, and Sessions cannot be created through the UI. After v0.3 ships, every governance write the project produces — including the records of v0.3's own planning conversation as the first dogfood — can be authored entirely through the desktop application. v0.3 is the build specification handed to Claude Code, which executes it through a five-prompt slice series.

### Background

UI v0.2 shipped on 05-09-26 (SES-007, status v0.8, phase `"v0.2 complete"`). With v0.2 in hand, four of the eight v2 entity types (Decisions, Risks, Planning Items, Topics) have full CRUD; two (Charter, Status) have versioned-replace + history; two (Sessions, References) remain read-only.

The two read-only entities are exactly what makes v2 untestable end-to-end as a real governance tool. Every Claude.ai conversation that produces governance content currently ends with a Python script — `apply_dec_025.py`, `apply_session_007.py`, and so on — writing the SES-NNN record and its `decided_in` references on Doug's behalf. The script-based path works, but it means the UI is not the operational tool; it is a viewer over an operational tool that lives in scripts.

The v0.3 planning conversation (SES-008) confirmed this framing — testability-first — and selected a coherent v0.3 thesis: **complete the testability gap so v2 can drive real governance work without leaving the UI.** Two write surfaces (References full CRUD, Sessions create-only), one architectural cleanup (the `ListDetailPanel` factory refactor deferred from v0.2 slice F), and one global UX principle (right-click context menus uniform across every entity row) constitute v0.3's scope. The full styling pass per DEC-024 is deferred again, with a tracking planning item created so the third deferral does not drift into a fourth.

### Source decisions

This PRD does not re-derive architectural decisions; it specifies requirements grounded in the following decision records.

Existing decisions still in force from v0.1 and v0.2:

- **DEC-013** — One Claude.ai conversation equals one session record; sessions are append-only.
- **DEC-014** — Every v2 conversation produces a session record.
- **DEC-018** — UI is a standalone application, not embedded in the v1 PySide6 app.
- **DEC-019** — UI consumes the REST API over HTTP, not the access layer directly.
- **DEC-021** — Sidebar navigation with master/detail panes.
- **DEC-022** — File-watch on `db-export/` for live refresh, manual Refresh button as fallback.
- **DEC-023** — Detect-then-launch API subprocess management.
- **DEC-024** — Native Qt look; styling pass deferred. (v0.3 honors this; deferred again with PI-NNN tracking — see DEC-037.)
- **DEC-025** — Per-conversation transcript capture deferred; `conversation_reference` is descriptive text, seed prompt verbatim in `topics_covered`.
- **DEC-027** — v0.2 entity scope statement noted Sessions and References as v0.3 candidates. v0.3 picks them up.
- **DEC-028** — `EntityCrudDialog` / `EntityCrudDeleteDialog` base classes; v0.3's new dialogs extend the same foundation where the field-schema model fits.
- **DEC-031** — `ReferencesSection` widget on every detail pane; v0.3 extends it with an `Add reference` affordance and right-click delete.

Forthcoming decisions (to be recorded after this PRD is approved, see Section 11):

- **DEC-032** — v0.3 frame: complete the testability gap so v2 can drive real governance work without leaving the UI.
- **DEC-033** — References write surface: panel + detail-pane entry points, source-first cascading dialog with strict `RELATIONSHIP_TYPES` vocab compliance, autocomplete combo identifier picker, no edit affordance, hard-delete with confirmation.
- **DEC-034** — Sessions create-only via UI: user-authored sessions permitted; append-only stays strict; sessions remain narrow-scoped to Claude.ai conversations.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor with targeted parity-test discipline.
- **DEC-036** — Right-click context menus uniform across all entity rows as a global UX principle.
- **DEC-037** — Full styling pass deferred again with PI-NNN tracking; v0.3 micro-visual adjustments allowed within scope.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.3.

1. **`ListDetailPanel` factory refactor.** Two factory methods added to the base class:
   - `_create_master_widget(self) -> QAbstractItemView` — default returns `QTableView`. Subclasses needing a different master widget (e.g., the Topics panel's `QTreeView`) override the factory rather than overriding `_build_ui` and aliasing `self._table = self._tree`. The Topics panel migrates to the factory in this slice; the v0.2 workaround is removed.
   - `_build_context_menu(self, index) -> QMenu` — default returns an empty `QMenu`. Subclasses populate with entity-specific actions. The base wires `customContextMenuRequested` and the `QAbstractItemView.contextMenuPolicy = Qt.CustomContextMenu` path so subclasses only supply the menu content.

2. **Right-click context menus uniform across every entity row.** Every panel implements `_build_context_menu` to surface actions paralleling its toolbar and detail-pane buttons. Per panel:
   - Decisions: Edit / Delete / Restore (when row is deleted) / Show references
   - Sessions: Go to references / Copy identifier (no Edit, no Delete)
   - Risks: Edit / Delete
   - Planning Items: Edit / Delete
   - Topics: Edit / Delete
   - References: Go to source / Go to target / Delete reference / New reference
   - Charter and Status (version-list rows): Make Current / View payload
   - References-section rows on every detail pane: Delete reference / Go to [other side]

3. **References full write surface.** The References panel becomes a write surface with both creation and deletion paths. Detail panes' `ReferencesSection` widget gains an `Add reference` affordance and per-row right-click `Delete reference`. Both entry points open the same dialog with optional pre-populated source.

   Dialog UX (per DEC-033):
   - Source-first picker order. Source type and identifier come first (or are pre-populated from the detail pane). The relationship-kind dropdown is filtered to kinds valid for that source type. The target-type dropdown is filtered by `(source_type, kind)`. The target-identifier picker comes last.
   - Strict `RELATIONSHIP_TYPES` vocab compliance. Dropdowns only show valid choices for the partially-filled state. Invalid combinations are unrepresentable in the dialog. The vocab is read from `access/vocab.py` at dialog-open time so new kinds appear automatically as the access layer evolves.
   - Identifier picker is an editable `QComboBox` + `QCompleter` populated with `IDENTIFIER — title` items, matching the existing v0.1/v0.2 entity-selection pattern (no need to reuse `HierarchicalEntityPicker` since references aren't a tree).
   - No edit affordance. References are immutable identity-wise; "edit" is delete + create.
   - Hard-delete with confirmation modal showing the edge text — "Delete the reference [SES-006 → DEC-026: decided_in]? This cannot be undone through the UI." — Cancel / Delete. No tombstone, no Show-deleted toggle, no Restore. Audit trail goes through the git-tracked `db-export/references.json` snapshot and (where present) the storage-layer `change_log` table.

4. **Sessions create-only surface.** The Sessions panel toolbar gets a `New Session` button; right-click on the panel surfaces `New session`. Append-only stays strict — no Edit button, no Delete button, no Restore, no draft mode. The dialog is fill-everything-once-and-save; the user records a session after the corresponding Claude.ai conversation closes, with all fields complete.

   Dialog field set (per DEC-034 and Q6 of the planning conversation):

   | Field | Widget | Required | Notes |
   |-------|--------|----------|-------|
   | `identifier` | Read-only label | (auto) | Auto-assigned at create time by querying the latest session and incrementing (`SES-NNN`). |
   | `session_date` | `DateField` | yes | Defaults to today. |
   | `status` | Combo | yes | Items from `SESSION_STATUSES`. Default `Complete`. |
   | `title` | `QLineEdit` | yes | Single-line. |
   | `summary` | `QPlainTextEdit` | yes | Multi-line, ~200px tall. |
   | `topics_covered` | `QPlainTextEdit` | yes | Multi-line, ~300px tall. Placeholder hints at DEC-025: `Seed prompt: "..."  followed by structured discussion summary`. |
   | `artifacts_produced` | `QPlainTextEdit` | yes | Multi-line, ~200px tall. |
   | `in_flight_at_end` | `QPlainTextEdit` | no | Multi-line, ~200px tall. Empty allowed. |
   | `conversation_reference` | `QPlainTextEdit` | yes | Multi-line, ~80px tall. Placeholder hints at DEC-025: `Descriptive text identifying the conversation by its outputs (PRDs, prompts, decisions). No transcript URL.` |

   No content-pattern enforcement on `topics_covered` or `conversation_reference` — placeholders carry the convention. Required-field checks block Save with inline errors via the existing `EntityCrudDialog` validation pattern.

5. **Storage-layer additions where required.** v0.3 is primarily UI work, but two storage paths must be reachable:
   - `POST /references` and `DELETE /references/{id}` — confirm both exist; if `DELETE` is missing, the slice that needs it adds the endpoint and access-layer method (mechanical; matches the existing references repository shape).
   - `POST /sessions` — confirm it exists; the `apply_dec_025.py` script proves the access layer supports session writes, so the surface is reachable. The slice confirms the API surface and adds the endpoint if missing.

### Out of Scope

The following are explicitly deferred to v0.4 or later.

- **References edit affordance.** Edges are immutable identity-wise. Per DEC-033 the dialog is create-only, paired with hard-delete. If you want a different edge, delete and create.
- **Sessions edit affordance.** Per DEC-013 sessions are append-only, and DEC-034 confirms append-only stays strict in v0.3. No edit, no delete, no draft mode.
- **Soft-delete on references.** Edges aren't first-class governance content; the entities they connect carry the substance. Tombstones would bloat the References panel monotonically. Audit goes through git history and `change_log`. (Per DEC-033.)
- **Full styling design pass per DEC-024.** Deferred again. PI-NNN tracks the deferral so it does not drift further. (Per DEC-037.) v0.3 may introduce small visual decisions demanded by its scope (e.g., a small colored pill on the relationship-kind label inside `ReferencesSection`) without those constituting a styling pass.
- **Reference filtering by relationship type.** v0.2 deferred this; v0.3 defers it again. Reference volume isn't pressuring readability yet.
- **Diff-with-current view for the JSON payload editor.** v0.2 noted this as a possible v0.3 addition if friction surfaces. None has surfaced; deferred to v0.4 if it does.
- **Methodology entity panels.** Personas, processes, fields, requirements, manual-config items, test specs. Gated on the methodology-entity schema being designed.
- **Global search across entities.**
- **Keyboard shortcuts beyond Qt defaults** (Ctrl-N for new record, etc.).
- **Export visible panel to CSV/JSON.**
- **Bulk operations** (multi-row select + delete, multi-row update).
- **Optimistic concurrency control on edits.** v0.1's last-write-wins posture continues.
- **Drag-to-reparent on the Topics tree view.** v0.2 noted this as a possible v0.3 candidate; not pressuring, deferred.
- **Reimplementation of the v1 saved-views / duplicate-checks / workflows managers (no public REST API write path).** Out of v0.3 scope; this is v1 application work, not v2 UI work.

---

## 3. Architecture

### Process model

Unchanged from v0.1 and v0.2. The UI process spawns or attaches to the API subprocess (DEC-023), watches `db-export/` (DEC-022), and reaches the storage system exclusively through the REST API (DEC-019).

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

v0.3 keeps every v0.2 layer and adds nothing structural. The two factory-method additions live inside the existing `base/list_detail_panel.py`; new dialogs live in `dialogs/`; one new widget lives in `widgets/`.

| Layer | Module | Status | Responsibility |
|---|---|---|---|
| Application shell | `crmbuilder_v2.ui.app` | unchanged | Qt application initialization, main window, sidebar, content area, lifecycle wiring |
| Storage client | `crmbuilder_v2.ui.client` | extended | Adds `create_reference`, `delete_reference`, `create_session` methods. `list_references` already present from v0.2. |
| Workers | `crmbuilder_v2.ui.workers` | unchanged | `QThread` wrappers around storage client calls |
| Server lifecycle | `crmbuilder_v2.ui.server_lifecycle` | unchanged | Probe, spawn, track, terminate the API subprocess |
| Refresh service | `crmbuilder_v2.ui.refresh` | unchanged | `QFileSystemWatcher` on the snapshot directory; per-entity-type "data changed" signals (extended by the slice that needs it if `references` and `sessions` aren't yet wired into the refresh map) |
| Entity panels | `crmbuilder_v2.ui.panels.*` | extended | Every panel implements `_build_context_menu`. References panel adds `New Reference` toolbar button + right-click. Sessions panel adds `New Session` toolbar button + right-click. Topics panel migrates to `_create_master_widget` factory. |
| Dialogs | `crmbuilder_v2.ui.dialogs.*` | extended | New `reference_create.py`, `reference_delete.py`, `session_create.py` |
| Base widgets | `crmbuilder_v2.ui.base` | extended | `list_detail_panel.py` adds `_create_master_widget` and `_build_context_menu` factory methods. `EntityCrudDialog` and `VersionedReplaceDialog` unchanged from v0.2. |
| Reusable widgets | `crmbuilder_v2.ui.widgets` | extended | New `EntityIdentifierPicker` (autocomplete combo). `DateField`, `ReferencesSection`, `HierarchicalEntityPicker` unchanged from v0.2. `ReferencesSection` extended with an `Add reference` affordance and per-row right-click. |

### Configuration

Unchanged from v0.1 and v0.2. The UI reads `crmbuilder_v2.config.get_settings()` directly. No new environment variables, no config file additions.

---

## 4. Functional Requirements

### 4.1 `ListDetailPanel` factory refactor

`base/list_detail_panel.py` gains two factory methods.

`_create_master_widget(self) -> QAbstractItemView` — default implementation returns a configured `QTableView`. The current `_build_ui` is rewritten to call this factory instead of constructing the table directly. Subclasses that need a different master widget override the factory; the base remains agnostic. Slice A migrates `panels/topics.py` to override the factory and return a configured `QTreeView`, eliminating the v0.2 `self._table = self._tree` workaround.

`_build_context_menu(self, index: QModelIndex) -> QMenu` — default implementation returns an empty `QMenu`. The base wires `setContextMenuPolicy(Qt.CustomContextMenu)` on the master widget and connects `customContextMenuRequested` to a slot that calls the factory and pops the resulting menu at the requested position. If the factory returns an empty menu, the request is silently ignored.

`select_record_by_identifier` (promoted to base in v0.2 slice F) is the canonical way subclass right-click handlers select rows by identifier when an action navigates to another row.

### 4.2 Right-click context menus uniform across every entity row

Every panel overrides `_build_context_menu` to surface actions paralleling its toolbar and detail-pane buttons. Empty selections (right-click on whitespace) surface a creation action where applicable; selections on a row surface row-scoped actions.

The full action map appears in Section 2.2 (In Scope). Implementation pattern per panel:

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        # Right-click on whitespace
        new_action = menu.addAction("New …")
        new_action.triggered.connect(self._on_new_clicked)
        return menu
    # Row context — populate from the panel's existing button handlers
    edit = menu.addAction("Edit")
    edit.triggered.connect(self._on_edit_clicked)
    # ...
    return menu
```

Action handlers reuse the existing toolbar / detail-pane button slots; right-click introduces no new business logic, only a new entry point.

### 4.3 References write surface

#### 4.3.1 Dialog architecture

`dialogs/reference_create.py` houses `ReferenceCreateDialog`. The dialog extends `EntityCrudDialog` if the schema-driven framework can be parameterized to support cascading filters between fields; if friction surfaces during slice C, the dialog instead extends a thin parallel base or the framework gains a small filter-callback hook. The slice resolves this implementation choice once the framework is exercised.

Construction signature:

```python
ReferenceCreateDialog(
    parent: QWidget,
    client: StorageClient,
    *,
    pre_populated_source: tuple[str, str] | None = None,
    # tuple is (source_type, source_id); when supplied (from a detail
    # pane Add-reference affordance), the source fields are filled and
    # disabled
)
```

Field cascade:

| Step | Field | Behavior |
|------|-------|----------|
| 1 | Source type | Combo populated with the entity types valid as source for any kind in `RELATIONSHIP_TYPES`. Disabled and pre-filled if `pre_populated_source` is supplied. |
| 2 | Source identifier | `EntityIdentifierPicker` for the chosen source type. Disabled and pre-filled if `pre_populated_source` is supplied. |
| 3 | Relationship kind | Combo populated with the kinds that have the chosen source type as a valid source. Recomputed when source type changes. |
| 4 | Target type | Combo populated with the target types valid for `(source_type, kind)`. Auto-selected and disabled if only one valid type exists. Recomputed when source type or kind changes. |
| 5 | Target identifier | `EntityIdentifierPicker` for the chosen target type. Recomputed when target type changes. |

Save sends `POST /references` with `{source_type, source_id, target_type, target_id, relationship_kind}`. Success closes the dialog; the panel and any open `ReferencesSection` widgets refresh via the existing file-watch path.

`dialogs/reference_delete.py` houses `ReferenceDeleteDialog`. Construction takes the reference's `id` (the integer primary key) and the human-readable edge text. Modal renders confirmation: "Delete the reference [SES-006 → DEC-026: decided_in]? This cannot be undone through the UI." with Cancel and Delete buttons. Confirm sends `DELETE /references/{id}`.

#### 4.3.2 Entry points

References panel toolbar gets a `New Reference` button that opens `ReferenceCreateDialog` with `pre_populated_source=None`.

Every detail pane's `ReferencesSection` widget gets:
- An `Add reference` button at the bottom of the section (or a `+` icon in the section header — the slice picks the more natural placement). Opens `ReferenceCreateDialog` with `pre_populated_source=(entity_type, identifier)` matching the detail pane's current entity.
- Per-row right-click menu: `Delete reference` (opens `ReferenceDeleteDialog` for that reference), `Go to [other side]` (navigates to the entity at the other end of the edge using the existing v0.2 click-to-navigate path).

References panel rows also get the right-click menu defined in §4.2.

#### 4.3.3 New widget

`widgets/entity_identifier_picker.py` houses `EntityIdentifierPicker`. Lightweight wrapper around `QComboBox` configured with:
- `setEditable(True)`
- `QCompleter` set to `Qt.MatchContains` filter mode so typing matches both `IDENTIFIER` and `title` substring
- Items populated from a list provided at construction or via a `set_entity_type(entity_type)` slot (the dialog calls this when the type combo changes, fetching the entity's records via the storage client)
- Emits a `selection_changed(identifier: str)` signal for downstream cascade triggers

The widget is generic over entity type — it doesn't know what a Decision or Session is, just renders `IDENTIFIER — title` strings the dialog feeds it.

### 4.4 Sessions create-only surface

`dialogs/session_create.py` houses `SessionCreateDialog`, an instance of `EntityCrudDialog` parameterized by the field schema in §2.4. Identifier auto-assignment runs at dialog-open time:
- The dialog calls `client.list_sessions()` (or a new `client.next_session_identifier()` helper if the slice prefers a server-side endpoint) to determine the next `SES-NNN`.
- The identifier appears in the dialog as a read-only label at the top.

Save sends `POST /sessions` with the full payload. The Sessions panel and any cross-references refresh via file-watch.

`panels/sessions.py` extended:
- `New Session` button in the toolbar, between Refresh and any existing buttons.
- Right-click on the panel master widget surfaces `New session` (whitespace) or `Go to references` / `Copy identifier` (selected row), per §4.2.
- No Edit, no Delete, no Restore — append-only stays strict per DEC-013 / DEC-034.

### 4.5 Detail-pane `ReferencesSection` extensions

`widgets/references_section.py` extended with:
- `Add reference` button at the bottom of the rendered section. Click opens `ReferenceCreateDialog` with the host detail pane's `(entity_type, identifier)` as pre-populated source.
- Per-row right-click menu on each rendered reference: `Delete reference` (opens `ReferenceDeleteDialog`), `Go to [other side]` (the side that isn't the host).
- Existing click-to-navigate behavior is preserved.

The `exclude_relationships` parameter from v0.2 (used to suppress the redundant outbound `supersedes` rendering on the Decisions detail pane) continues to work.

### 4.6 Storage-layer additions where required

Two paths must be reachable through the REST API:

- **`DELETE /references/{id}`.** If absent, the slice that needs it (slice C) adds the endpoint and the access-layer `delete_reference(id)` method. The deletion is a hard delete; no soft-delete column is added.
- **`POST /sessions`.** Confirmed reachable today via the `apply_dec_025.py` script path. The slice that needs it (slice D) verifies via the API surface; if the script bypasses HTTP and writes directly through the access layer, the slice adds the HTTP endpoint as a thin wrapper.

These are mechanical additions and are made in the slice that needs them, with a one-paragraph note in that slice's prompt explaining the addition. They do not require their own architectural conversation.

### 4.7 Application shutdown, startup, refresh, error handling, and connection management

All unchanged from v0.1 and v0.2. v0.3's new dialogs and panels integrate with the existing patterns:

- All HTTP calls go through `QThread` workers.
- Validation errors with a `field` key surface inline; missing-field errors surface in the generic `ErrorDialog`.
- `StorageConnectionError` during a write closes the dialog via `reject()` and lets the lifecycle's existing crash-banner handle the connection-lost surface.
- The `RefreshService` catches every successful write and refreshes the affected panel within ~500ms via the file-watch path.

---

## 5. Non-Functional Requirements

### 5.1 Threading

Unchanged from v0.1 and v0.2. Every HTTP call runs in a `QThread` worker.

### 5.2 Responsiveness

- Dialog open completes in under 100ms (data already in memory from the list).
- The cascading filter recomputation in `ReferenceCreateDialog` (when source type changes) completes in under 50ms — the vocab filter is in-memory and the entity-identifier list is cached.
- The `EntityIdentifierPicker`'s autocomplete responds to typing within one frame on lists up to ~1000 entries.

### 5.3 Resource use

Unchanged from v0.1 and v0.2.

### 5.4 Logging

Unchanged from v0.1 and v0.2.

### 5.5 Platform support

Linux primary. macOS verified. Windows not a v0.3 target.

### 5.6 Dependencies

No new external dependencies for v0.3. All needed libraries are already present:
- `PySide6` for Qt (existing).
- `httpx` for HTTP (existing).
- `pytest-qt` for tests (existing).

---

## 6. Acceptance Criteria

The UI v0.3 is considered functionally complete when all of the following are true.

1. The full v0.2 surface continues to work end-to-end after the slice A factory refactor: every existing CRUD, replace, refresh, and reference-rendering path continues to function. v0.2's 458 tests still pass.

2. **Factory refactor.** `panels/topics.py` no longer contains the `self._table = self._tree` workaround; its `_create_master_widget` returns the `QTreeView`. Every other panel uses the default `QTableView` factory. Per-panel parity tests assert master-widget type and confirm `_build_context_menu` returns a `QMenu`.

3. **Right-click context menus.** Right-clicking a row on every entity panel surfaces a context menu with the actions enumerated in §2.2. Right-clicking whitespace surfaces creation actions where applicable. Right-clicking a reference row inside a `ReferencesSection` on any detail pane surfaces `Delete reference` and `Go to [other side]`.

4. **References create from References panel.** Clicking `New Reference` on the References panel opens `ReferenceCreateDialog` with all fields empty. The user picks source type, source identifier, kind, target type, target identifier; cascading filters constrain choices to valid `RELATIONSHIP_TYPES` combinations. Save creates the reference, refreshes the panel, selects the new row.

5. **References create from a detail pane.** The `Add reference` affordance on a detail pane's `ReferencesSection` opens `ReferenceCreateDialog` with source type and identifier pre-filled and disabled. The user picks kind, target type, target identifier. Save creates the reference; the detail pane's `ReferencesSection` refreshes with the new edge visible.

6. **References delete from References panel.** Right-clicking a reference row and choosing `Delete reference` opens `ReferenceDeleteDialog` with the edge text rendered. Confirming hard-deletes the reference; the panel refreshes.

7. **References delete from a detail pane.** Right-clicking a rendered reference inside a `ReferencesSection` and choosing `Delete reference` opens the same delete dialog. Confirming hard-deletes the reference; the detail pane's `ReferencesSection` refreshes.

8. **No edit affordance on references.** No Edit button or right-click `Edit reference` action exists.

9. **Sessions create.** Clicking `New Session` on the Sessions panel toolbar (or the right-click `New session` action) opens `SessionCreateDialog` with the auto-assigned identifier shown read-only at the top, `session_date` defaulted to today, `status` defaulted to `Complete`. All required fields validate inline; empty `in_flight_at_end` is allowed. Save creates the session; the panel refreshes and selects the new row.

10. **No edit or delete on sessions.** The Sessions panel detail pane shows no Edit, no Delete, no Restore button. Right-click on a session row surfaces only `Go to references` / `Copy identifier`.

11. **Vocab compliance is strict.** Constructing an invalid `(source_type, kind, target_type)` combination is impossible in the dialog — the cascading filters never offer it. New kinds added to `RELATIONSHIP_TYPES` at the access layer surface in the dialog without UI changes.

12. **File-watch refresh continues.** Writing a new reference or session via MCP / curl while the UI is open causes the affected panel to update without manual refresh. (Continues v0.1/v0.2 file-watch behavior; verifies the refresh map covers `references` and `sessions`.)

13. **Inline validation works for all new dialogs.** Empty required fields, invalid combo selections (impossible via cascade but guarded server-side), and API-side validation errors keyed to a field surface inline. Field-less API errors surface in the generic `ErrorDialog`.

14. **Planning records present in the database after slice A.** SES-008 record, DEC-032 through DEC-037 records, six `decided_in` references from SES-008 to each, PI-NNN tracking the deferred styling pass, status update bumping to v0.9 phase `"v0.3 in build"`.

15. **Closeout artifacts after slice E.** SES-009 build session record, status update to v1.0 phase `"v0.3 complete"`, About dialog showing `0.3.0`, README updated.

16. **The full v2 test suite passes.** v0.2's 458 tests + new tests across slices A through E. Estimated 510+ passing.

---

## 7. Implementation Approach

The implementation plan (`ui-v0.3-implementation-plan.md`) breaks this PRD into five prompts (`v2-ui-v0.3-A` through `v2-ui-v0.3-E`), each producing an independently testable slice. The plan is the operational counterpart to this PRD and is approved separately.

In summary:

- **A — Foundation and factory refactor.** Planning records (SES-008, DEC-032 through DEC-037, references, PI-NNN, status update). `ListDetailPanel` factory methods. Topics migration. Per-panel parity tests.
- **B — Right-click context menus uniform across existing panels.** Each existing panel overrides `_build_context_menu` with its action set. References and Sessions panels get only their existing read-only actions in this slice; write actions are added in C and D.
- **C — References write surface.** `ReferenceCreateDialog`, `ReferenceDeleteDialog`, `EntityIdentifierPicker`. Panel `New Reference` button. Detail-pane `Add reference` affordance and per-row right-click delete. Storage additions if needed.
- **D — Sessions create dialog.** `SessionCreateDialog`, identifier auto-assignment, panel `New Session` button, panel right-click extension.
- **E — Closeout.** Micro-adjustments observed during build, About 0.3.0, README, SES-009, status update to v1.0, final test pass.

---

## 8. Dependencies and Constraints

### Dependencies on the storage system

v0.3 may require small additive storage-layer changes:

- `DELETE /references/{id}` endpoint and access-layer method (slice C) if not already present.
- `POST /sessions` HTTP endpoint (slice D) if the existing path is access-layer-only.
- Refresh-service entity-type map extension (slice C and slice D) if `references` and `sessions` aren't yet wired into the file-watch refresh signal map.

These are mechanical additions and are made in the slice that needs them, with a one-paragraph note in that slice's prompt explaining the addition. They do not require their own architectural conversation.

### No changes to the v1 application

Unchanged from v0.1 and v0.2. v2 work is strictly additive to v1.

### Constraint: process model still assumes localhost

Unchanged from v0.1 and v0.2.

### Constraint: factory refactor must not regress v0.2 panel behavior

The slice A refactor changes how master widgets and context menus are constructed in `ListDetailPanel`. v0.2's 458 tests are the regression net; the refactor is acceptance-gated on those tests continuing to pass plus per-panel parity tests for the new factory shape.

### Constraint: append-only on Sessions stays strict

DEC-013 and DEC-034 jointly require that no UI path edits or deletes a session record. Slice D must not introduce an Edit button, Delete button, or "Save draft" mode. The detail pane stays read-only for existing sessions.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Slice A's factory refactor regresses v0.2 panel behavior on a panel other than Topics (e.g., a subtle change to context-menu wiring breaks an existing keyboard shortcut path) | Low | High | v0.2's 458 tests are the regression net. Slice A is acceptance-gated on every prior test passing plus per-panel parity tests. The refactor is bounded to `_build_ui` and the new factory methods; subclasses other than Topics are not touched in slice A. |
| `EntityCrudDialog` schema-driven framework cannot cleanly express the cascading-filter dependency between fields in `ReferenceCreateDialog` | Medium | Medium | Slice C resolves on first contact: either the framework is extended with a small filter-callback hook (preferred), or `ReferenceCreateDialog` extends a thin parallel base. Both paths are bounded; the slice prompt enumerates the decision criterion. |
| `RELATIONSHIP_TYPES` vocab in `access/vocab.py` does not have the structure needed to drive the cascade (e.g., kinds aren't keyed by `(source_type, target_type)` constraints) | Low | Medium | Slice A's reading-order section reads `vocab.py` and the `references` repository; if the vocab needs reshaping, the change is part of slice C and is mechanical. |
| `EntityIdentifierPicker`'s autocomplete becomes sluggish at high entity counts | Low | Low | The widget caches the entity list at construction; recomputing the filter is in-memory. Real-world counts in v0.3 are well under 1000 entries per type. If volume becomes a real problem, slice E or v0.4 introduces a server-side search. |
| The right-click context menu sweep in slice B introduces an inconsistency where one panel's menu is subtly out of step with its toolbar | Low | Low | Each panel's menu actions are wired to the same handler slots as its toolbar buttons — the menu is a second entry point, not a parallel implementation. Smoke tests assert menu has the expected action set per panel. |
| Sessions identifier auto-assignment races with another session being written simultaneously (two writers both compute `SES-008`) | Low | Low | The access layer enforces unique identifiers; on collision the API returns a validation error and the dialog re-fetches the latest and retries once. |
| File-watch refresh map doesn't include `references` or `sessions` and panel updates require manual Refresh | Medium | Low | Slice C and slice D each verify the refresh map and extend it if needed. The fix is a one-line addition. |
| Hard-delete on a reference that is later realized to be wrong cannot be undone through the UI | Low | Low | The confirmation modal explicitly states this. Audit through `db-export/references.json` git history. If un-delete becomes a real need, v0.4 reconsiders soft-delete; v0.3 keeps hard-delete simple. |

---

## 10. Open Questions

1. **Should the `Add reference` affordance be a button at the bottom of the `ReferencesSection` or a `+` icon in the section header?** Both work. Button at the bottom is more discoverable; `+` icon is less visually heavy. Slice C picks the more natural placement on first contact.

2. **Should the relationship-kind label in `ReferencesSection` get a small colored pill?** A micro-visual adjustment allowed under DEC-037. Decision deferred to slice E (closeout) — if friction on the read surface during slice C/D suggests it, add it; otherwise defer.

3. **Should `EntityIdentifierPicker` support keyboard navigation through results without the dropdown opening?** Qt's default `QCompleter` behavior covers this; verify in slice C and tune if the default UX is awkward.

4. **What does the right-click menu show on a Charter or Status version-list row?** Per §2.2: `Make Current` (on non-current versions) and `View payload`. The slice that builds context menus confirms the action set against the existing v0.2 version-list panel structure.

5. **Should `SessionCreateDialog` offer a "Use as template" affordance that pre-fills fields from the most recent session?** Plausibly useful (the conventions for `topics_covered` and `conversation_reference` recur), but adds a UI mode. Deferred to v0.4 unless it surfaces friction during real-use testing.

---

## 11. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and DEC-025 (conversation_reference convention + seed-prompt-in-topics_covered), the planning conversation that produced this PRD is captured in the v2 database after PRD approval. The session and decision records are written through the REST API or MCP server as part of the v2-ui-v0.3-A prompt's setup steps.

Records to write:

- **SES-008** — UI v0.3 planning. Status: Complete. `conversation_reference`: descriptive text per DEC-025 (`"Claude.ai planning conversation that produced ui-PRD-v0.3.md, ui-v0.3-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.3 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`). `topics_covered`: opens with the verbatim seed prompt rendered as `Seed prompt: "<the task statement>"`, followed by a structured summary of the nine architectural questions discussed (release shape, references entry points + global right-click directive, references picker UX, references edit/delete semantics, sessions governance interpretation, sessions dialog content, factory refactor, styling deferral, slice breakdown).
- **DEC-032** — v0.3 frame: complete the testability gap.
- **DEC-033** — References write surface: panel + detail-pane entry points; source-first cascading dialog with strict `RELATIONSHIP_TYPES` vocab compliance; autocomplete combo identifier picker; no edit affordance; hard-delete with confirmation.
- **DEC-034** — Sessions create-only via UI: user-authored sessions permitted; append-only stays strict; sessions remain narrow-scoped to Claude.ai conversations.
- **DEC-035** — `ListDetailPanel` master-widget + context-menu factory refactor; per-panel parity-test discipline.
- **DEC-036** — Right-click context menus uniform across all entity rows as a global UX principle.
- **DEC-037** — Full styling pass deferred again with PI-NNN tracking; v0.3 micro-visual adjustments allowed within scope.
- **References** — `decided_in` from SES-008 to each of DEC-032 through DEC-037.
- **PI-NNN** — Planning item tracking the deferred full styling pass per DEC-024 / DEC-037. Target release: dedicated styling release after v0.4 unless other priorities reorder.

A status update reflecting that UI v0.3 is now in build (slice A in progress, phase `"v0.3 in build"`, version label `0.9`) is also appropriate at the same time.
