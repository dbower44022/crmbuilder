# CRMBuilder v2 — UI v0.3 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-09-26 17:30
**Status:** Draft — pending approval
**Companion PRD:** `ui-PRD-v0.3.md`
**Predecessor plan:** `ui-v0.2-implementation-plan.md` (shipped per SES-007)
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-{A..E}-*.md`

---

## 1. Overview

This plan implements the v0.3 desktop UI specified in `ui-PRD-v0.3.md`. v0.3 is decomposed into five independently testable slices, each delivered as its own Claude Code prompt. Each prompt produces a working state of the application that exercises a coherent subset of the PRD's acceptance criteria.

Slice boundaries follow dependency and natural review checkpoints. Slice A delivers the foundation (planning records and the `ListDetailPanel` factory refactor) before any per-feature work. Slice B sweeps right-click context menus across every existing panel in one focused pass. Slice C delivers the References write surface — the largest single piece of v0.3. Slice D delivers the Sessions create dialog. Slice E is mechanical closeout. v0.2 needed six slices because three CRUD entities each took their own slice; v0.3 has only two new write surfaces, both of which are individually rich enough to deserve their own slice but don't need duplication of the v0.2 pattern.

After all five prompts execute cleanly, every acceptance criterion in PRD section 6 is satisfied. The application is functionally usable from prompt C onward (References writes available); prompt D adds Sessions writes; prompt E is polish and governance closeout.

---

## 2. Implementation Choices

### 2.1 Language and runtime

Unchanged from v0.1 and v0.2. Python 3.12+, matching `pyproject.toml`'s `requires-python` pin.

### 2.2 Desktop framework — PySide6

Unchanged.

### 2.3 HTTP client — httpx (sync mode)

Unchanged.

### 2.4 Subprocess management — QProcess

Unchanged.

### 2.5 File watching — QFileSystemWatcher

Unchanged, including v0.1 slice H's content-hash gating. Slice C and slice D verify the refresh map covers `references` and `sessions` and extend it if needed.

### 2.6 Test framework — pytest + pytest-qt

Unchanged. `qtbot` and `qapp` fixtures continue.

### 2.7 Logging — Python's standard `logging` module

Unchanged. RotatingFileHandler at `~/.crmbuilder-v2/ui.log`.

### 2.8 Threading model

Unchanged. Worker/object pattern; `run_in_thread` helper.

### 2.9 Error handling

Unchanged. Typed exceptions in the storage client; inline-on-field for validation errors with `field`; modal `ErrorDialog` for everything else.

### 2.10 Existing dialog framework — `EntityCrudDialog`

v0.2's `EntityCrudDialog` is the schema-driven base. v0.3 reuses it for `SessionCreateDialog` directly. For `ReferenceCreateDialog`, the cascading-filter dependency between fields exceeds what the v0.2 field-schema dataclass expresses cleanly. Slice C resolves on first contact between two paths:

1. **Extend `FieldSchema` with an optional `depends_on` and `compute_options` callback.** A combo field can declare it depends on another field's value; when the other field changes, `compute_options` is invoked to repopulate. This is the cleaner long-term answer; it generalizes to any future cascading form.
2. **Make `ReferenceCreateDialog` extend a thin parallel base** that handles cascading without changing `EntityCrudDialog`.

Slice C's prompt enumerates the criterion: if extending `FieldSchema` is mechanical and doesn't ripple into the existing dialog implementations, do that. Otherwise, build the parallel base. Either choice keeps the change bounded.

### 2.11 New for v0.3 — `ListDetailPanel` factory methods

`base/list_detail_panel.py` gains two factory methods, both with sensible defaults so existing subclasses continue to work without edits:

```python
class ListDetailPanel(QWidget):
    def _create_master_widget(self) -> QAbstractItemView:
        """Factory for the master pane's view widget. Override to use a
        non-default widget type (e.g., QTreeView for hierarchical entities)."""
        view = QTableView(self)
        # Apply the same default configuration the previous _build_ui used
        # (selection mode, alternating row colors, etc.)
        return view

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        """Factory for the right-click context menu. Override to add
        entity-specific actions. Default is empty (no menu shown)."""
        return QMenu(self)
```

`_build_ui` is rewritten to call `self._create_master_widget()` instead of constructing `QTableView` inline. Connection of `customContextMenuRequested` to a slot that calls `_build_context_menu` and pops the menu also lands in `_build_ui`.

### 2.12 New for v0.3 — `EntityIdentifierPicker` widget

A new widget under `crmbuilder_v2.ui.widgets.entity_identifier_picker` houses `EntityIdentifierPicker`. Lightweight `QComboBox` + `QCompleter` wrapper used by `ReferenceCreateDialog` for source and target identifier fields.

```python
class EntityIdentifierPicker(QComboBox):
    selection_changed = Signal(str)  # emits the selected identifier

    def __init__(self, parent: QWidget | None = None) -> None: ...
    def set_entries(self, entries: list[tuple[str, str]]) -> None:
        """entries is a list of (identifier, title); the widget renders
        them as 'IDENTIFIER — title' and indexes by identifier."""
    def selected_identifier(self) -> str | None: ...
    def clear_selection(self) -> None: ...
```

`QCompleter` is configured with `Qt.MatchContains` so typing matches against both identifier and title substrings.

---

## 3. Directory and File Layout

The UI lives under `crmbuilder-v2/src/crmbuilder_v2/ui/`. v0.3 adds three dialog files, one widget file, and modifies `base/list_detail_panel.py` plus every entity panel for context-menu support.

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    └── ui/
        ├── widgets/
        │   ├── __init__.py
        │   ├── date_field.py                    # unchanged
        │   ├── references_section.py            # MODIFIED — Add reference button + per-row right-click
        │   ├── hierarchical_picker.py           # unchanged
        │   └── entity_identifier_picker.py      # NEW
        ├── base/
        │   ├── list_detail_panel.py             # MODIFIED — _create_master_widget, _build_context_menu
        │   ├── versioned_panel.py               # unchanged (or MODIFIED if context-menu wiring lives here too)
        │   ├── crud_dialog.py                   # MODIFIED if FieldSchema gains depends_on/compute_options
        │   └── versioned_replace_dialog.py      # unchanged
        ├── dialogs/
        │   ├── decision_create.py               # unchanged
        │   ├── decision_edit.py                 # unchanged
        │   ├── decision_delete.py               # unchanged
        │   ├── error.py                         # unchanged
        │   ├── risk_create.py                   # unchanged
        │   ├── risk_edit.py                     # unchanged
        │   ├── risk_delete.py                   # unchanged
        │   ├── planning_item_create.py          # unchanged
        │   ├── planning_item_edit.py            # unchanged
        │   ├── planning_item_delete.py          # unchanged
        │   ├── topic_create.py                  # unchanged
        │   ├── topic_edit.py                    # unchanged
        │   ├── topic_delete.py                  # unchanged
        │   ├── charter_replace.py               # unchanged
        │   ├── status_replace.py                # unchanged
        │   ├── reference_create.py              # NEW
        │   ├── reference_delete.py              # NEW
        │   └── session_create.py                # NEW
        └── panels/
            ├── decisions.py                     # MODIFIED — _build_context_menu override
            ├── sessions.py                      # MODIFIED — toolbar New Session, _build_context_menu
            ├── risks.py                         # MODIFIED — _build_context_menu
            ├── planning_items.py                # MODIFIED — _build_context_menu
            ├── topics.py                        # MODIFIED — migrate to _create_master_widget, _build_context_menu
            ├── references.py                    # MODIFIED — toolbar New Reference, _build_context_menu, write integration
            ├── charter.py                       # MODIFIED — _build_context_menu (for version-list rows)
            └── status.py                        # MODIFIED — _build_context_menu (for version-list rows)

tests/
└── crmbuilder_v2/
    └── ui/
        ├── widgets/
        │   ├── test_date_field.py               # unchanged
        │   ├── test_references_section.py       # MODIFIED — Add reference + delete row tests
        │   ├── test_hierarchical_picker.py      # unchanged
        │   └── test_entity_identifier_picker.py # NEW
        ├── test_decision_create_dialog.py       # unchanged
        ├── test_decision_edit_dialog.py         # unchanged
        ├── test_decision_delete_dialog.py       # unchanged
        ├── test_decisions_panel_writes.py       # MODIFIED — context-menu smoke test
        ├── test_crud_dialog_base.py             # MODIFIED if FieldSchema extended
        ├── test_versioned_replace_dialog_base.py # unchanged
        ├── test_risk_dialogs.py                 # unchanged
        ├── test_risks_panel_writes.py           # MODIFIED — context-menu smoke test
        ├── test_planning_item_dialogs.py        # unchanged
        ├── test_planning_items_panel_writes.py  # MODIFIED — context-menu smoke test
        ├── test_topic_dialogs.py                # unchanged
        ├── test_topics_panel_writes.py          # MODIFIED — factory migration test, context-menu smoke test
        ├── test_charter_replace.py              # MODIFIED — context-menu smoke test
        ├── test_status_replace.py               # MODIFIED — context-menu smoke test
        ├── test_show_deleted_toggle.py          # unchanged
        ├── test_list_detail_panel_factories.py  # NEW — per-panel parity tests
        ├── test_reference_create_dialog.py      # NEW
        ├── test_reference_delete_dialog.py      # NEW
        ├── test_references_panel_writes.py      # NEW — toolbar, right-click, write integration
        ├── test_session_create_dialog.py        # NEW
        ├── test_sessions_panel_writes.py        # NEW — toolbar, right-click, write integration
        └── test_context_menus.py                # NEW — sweep test asserting menu action set per panel
```

Storage-system additions, made in the slice that needs them:

- `crmbuilder-v2/src/crmbuilder_v2/api/routers/references.py` — `DELETE /references/{id}` if not already present (slice C). `POST /references` confirmed present.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/references.py` — `delete_reference(id)` method if not already present (slice C).
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py` — `POST /sessions` if not currently exposed via HTTP (slice D).
- `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — entity-type → panel signal map extended for `references` and `sessions` if not already wired (slices C and D).

---

## 4. Build Sequence

Each slice lands as one commit (or a small handful) prefixed `v2:` per the v2 convention and corresponds to one execution prompt. PRD acceptance criteria from section 6 are cross-referenced as `AC#N`.

### Step A — Foundation and factory refactor

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.3-A-foundation-and-factory-refactor.md`

**Deliverables:**

- Planning records written to the v2 database via the running REST API (or MCP):
  - SES-008 — UI v0.3 planning session per DEC-025 conventions (`conversation_reference` is descriptive text; `topics_covered` opens with the verbatim seed prompt).
  - DEC-032 through DEC-037 — six architectural decision records (full body text in the slice prompt's appendix).
  - Six `decided_in` references from SES-008 to each of DEC-032 through DEC-037.
  - PI-NNN — planning item tracking the deferred full styling pass per DEC-024 / DEC-037. Target release: dedicated styling release after v0.4.
  - Status update bumping to version `0.9` and phase `"v0.3 in build, slice A in progress"`.
- `base/list_detail_panel.py` refactor:
  - `_create_master_widget(self) -> QAbstractItemView` factory method (default `QTableView`).
  - `_build_context_menu(self, index: QModelIndex) -> QMenu` factory method (default empty `QMenu`).
  - `_build_ui` rewritten to call the factories; `customContextMenuRequested` wired to a slot that calls the factory and pops the menu.
- `panels/topics.py` migrated to `_create_master_widget` returning `QTreeView`. The v0.2 `self._table = self._tree` workaround is removed.
- Per-panel parity tests: for each panel with a `ListDetailPanel`-derived class, assert `isinstance(panel._master_view, expected_type)` and assert `_build_context_menu(some_index)` returns a `QMenu`. New file `tests/crmbuilder_v2/ui/test_list_detail_panel_factories.py`.

**Acceptance gates:**

- The full v2 test suite passes (458 v0.2 tests + new factory tests). Estimated 470+ passing.
- `panels/topics.py` no longer contains `self._table = self._tree`.
- Topics master panel still renders as `QTreeView` with parent-child nesting (existing v0.2 test continues to pass).
- Every other panel still renders its `QTableView` master view (existing v0.2 tests continue to pass).
- Right-clicking any panel produces no UI error (the default empty-menu factory is silently ignored).
- Planning records present in `db-export/`: SES-008, DEC-032 through DEC-037, six references, PI-NNN, status `0.9`.

**Out of slice:** any context-menu population (slice B), any references write surface (slice C), any sessions write surface (slice D).

---

### Step B — Right-click context menus across existing panels

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.3-B-right-click-menus.md`

**Deliverables:**

- Each existing entity panel overrides `_build_context_menu` to surface actions paralleling its toolbar and detail-pane buttons:
  - `panels/decisions.py`: Edit / Delete / Restore (when row is deleted) / Show references
  - `panels/sessions.py`: Go to references / Copy identifier (no Edit, no Delete — append-only)
  - `panels/risks.py`: Edit / Delete
  - `panels/planning_items.py`: Edit / Delete
  - `panels/topics.py`: Edit / Delete
  - `panels/references.py`: Go to source / Go to target (Delete and New land in slice C)
  - `panels/charter.py` and `panels/status.py` (version-list rows): Make Current (on non-current versions) / View payload
- All action handlers reuse existing toolbar / detail-pane button slots — right-click introduces no new business logic.
- Right-click on whitespace (no row selected): if the panel has a `New` action, surface it; otherwise return an empty menu (no menu shown).
- Tests:
  - `test_context_menus.py` — sweep test: for each panel, instantiate, programmatically request the context menu at a known row, assert the action set matches the expected list.
  - Per-panel test additions to `test_*_panel_writes.py` files: smoke test that right-click is wired and produces the expected menu shape.

**Acceptance gates:**

- Right-click on any entity panel row produces the expected action set per panel. (AC#3.)
- Clicking a context-menu action triggers the same handler as the corresponding toolbar / detail-pane button.
- Right-click on whitespace surfaces creation actions where applicable (panels with a `New` toolbar button).
- Right-click on a deleted Decision row surfaces `Restore` instead of `Delete`.
- Test suite passes. Estimated 480+ passing.

**Out of slice:** any reference-section row right-click (slice C extends `ReferencesSection` separately); any new write actions on References or Sessions panels (slices C and D).

---

### Step C — References write surface

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.3-C-references-write-surface.md`

**Deliverables:**

- New widget `widgets/entity_identifier_picker.py` housing `EntityIdentifierPicker` (autocomplete combo).
- New `dialogs/reference_create.py` housing `ReferenceCreateDialog`. The dialog's cascading-filter strategy resolves on first contact per §2.10:
  - If extending `FieldSchema` with `depends_on` and `compute_options` is mechanical, do that and base the dialog on the extended `EntityCrudDialog`.
  - Otherwise, build a thin parallel base for cascading dialogs and document the divergence.
- New `dialogs/reference_delete.py` housing `ReferenceDeleteDialog` (hard-delete confirmation modal).
- `client.py` extended with `create_reference(...)` and `delete_reference(id)` methods.
- Storage-layer additions if needed:
  - `DELETE /references/{id}` REST endpoint and access-layer `delete_reference` method.
  - `RELATIONSHIP_TYPES` vocab in `access/vocab.py` reshaped if it doesn't already key kinds by `(source_type, target_type)` constraints.
  - Refresh map extension for `references` if not already wired.
- `panels/references.py` extended:
  - `New Reference` button in the toolbar.
  - `_build_context_menu` extended (from slice B) to include `Delete reference` and `New reference` actions.
- `widgets/references_section.py` extended:
  - `Add reference` button at the bottom of the rendered section (or `+` icon in the section header — the slice picks the more natural placement on first contact).
  - Per-row right-click menu: `Delete reference`, `Go to [other side]`.
  - Existing click-to-navigate behavior preserved.
- Detail-pane integration: every entity panel's detail pane already hosts `ReferencesSection` from v0.2; the slice verifies the `Add reference` affordance and right-click menu are reachable from each.
- Tests:
  - `test_entity_identifier_picker.py` — autocomplete behavior, selection emission.
  - `test_reference_create_dialog.py` — cascade behavior, vocab compliance, source pre-population, save flow.
  - `test_reference_delete_dialog.py` — confirmation modal, delete flow.
  - `test_references_panel_writes.py` — toolbar `New Reference`, right-click `New` and `Delete`, write integration.
  - Updates to `test_references_section.py` — `Add reference` button, right-click delete on rendered rows.

**Acceptance gates:**

- `New Reference` button on the References panel opens the dialog with all fields empty. (AC#4.)
- Detail-pane `Add reference` affordance opens the dialog with source pre-filled and disabled. (AC#5.)
- Cascading filters constrain choices to valid `RELATIONSHIP_TYPES` combinations — invalid combinations are unrepresentable in the dialog. (AC#11.)
- Save creates the reference; the panel and any open detail-pane `ReferencesSection` widgets refresh via file-watch. (AC#4, AC#5.)
- Right-click delete on References panel rows opens the confirmation modal; confirming hard-deletes the reference. (AC#6.)
- Right-click delete on `ReferencesSection` rows opens the same modal; confirming hard-deletes the reference and the detail pane refreshes. (AC#7.)
- No Edit affordance exists. (AC#8.)
- File-watch refresh works for references writes via MCP / curl. (Continues AC#12.)
- Test suite passes. Estimated 500+ passing.

**Out of slice:** any sessions write surface (slice D); reference filtering by relationship type (deferred); soft-delete on references (deferred).

---

### Step D — Sessions create dialog

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.3-D-sessions-create-dialog.md`

**Deliverables:**

- New `dialogs/session_create.py` housing `SessionCreateDialog`, an instance of `EntityCrudDialog` parameterized by the field schema in PRD §2.4.
- Identifier auto-assignment helper. The dialog calls `client.list_sessions()` (or a new `client.next_session_identifier()` method) at dialog-open time to compute the next `SES-NNN`. The identifier appears as a read-only label at the top of the dialog.
- Placeholder text on `topics_covered` (`Seed prompt: "..."  followed by structured discussion summary`) and `conversation_reference` (`Descriptive text identifying the conversation by its outputs (PRDs, prompts, decisions). No transcript URL.`) per DEC-025.
- `client.py` extended with `create_session(...)` method.
- Storage-layer additions if needed:
  - `POST /sessions` HTTP endpoint, if the access-layer write path isn't already exposed via REST.
  - Refresh map extension for `sessions` if not already wired.
- `panels/sessions.py` extended:
  - `New Session` button in the toolbar (between Refresh and any existing buttons).
  - `_build_context_menu` extended (from slice B) to include `New session` on whitespace right-click.
  - No Edit, no Delete, no Restore — append-only stays strict per DEC-013 / DEC-034.
- Tests:
  - `test_session_create_dialog.py` — field set, auto-assignment, required-field validation, status defaulting to Complete, placeholder text, save flow.
  - `test_sessions_panel_writes.py` — toolbar `New Session`, right-click `New session`, write integration, no Edit/Delete buttons present on detail pane.

**Acceptance gates:**

- `New Session` button opens the dialog with the auto-assigned identifier shown read-only at the top, `session_date` defaulted to today, `status` defaulted to `Complete`. (AC#9.)
- All required fields validate inline; `in_flight_at_end` empty is allowed. (AC#9, AC#13.)
- Save creates the session; the panel refreshes and selects the new row. (AC#9.)
- The Sessions detail pane shows no Edit, no Delete, no Restore button. Right-click on a session row surfaces only `Go to references` / `Copy identifier`. (AC#10.)
- File-watch refresh works for session writes via MCP / curl. (Continues AC#12.)
- Test suite passes. Estimated 510+ passing.

**Out of slice:** any session edit, delete, or draft-mode affordance (governance-level boundary per DEC-013 / DEC-034); broadening sessions beyond Claude.ai conversations (out of v0.3 scope).

---

### Step E — Closeout

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.3-E-closeout.md`

**Deliverables:**

- Micro-visual adjustments observed during slices A–D: the slice prompt enumerates the polish items at draft time. Plausible candidates:
  - Small colored pill on the relationship-kind label inside `ReferencesSection` if read-pane friction surfaced.
  - Refinement of the `Add reference` button placement if the slice C choice felt awkward in use.
  - Any cosmetic regression observed during build.
- `pyproject.toml`: bump `version = "0.3.0"`.
- About dialog: verify it shows `0.3.0` (the version is read via `importlib.metadata` from `pyproject.toml`).
- README: update `crmbuilder-v2/README.md` "User interface" section to mention v0.3's new write surfaces (References full CRUD, Sessions create-only, right-click context menus) and link to `ui-PRD-v0.3.md`.
- Friction polish: any rough edges noticed during slices A–D that didn't fit cleanly into their owning slice.
- Closeout governance records:
  - SES-009 — UI v0.3 build session record. `topics_covered` summarizes the five-prompt build. `summary` enumerates what shipped. `artifacts_produced` lists the prompts and source/test additions. `in_flight_at_end` lists v0.4 candidates (full styling design pass, reference filtering by relationship type, JSON diff view, methodology entity panels post-schema-design, global search, keyboard shortcuts, export to CSV/JSON, bulk operations).
  - Status update bumped to version `1.0` and phase `"v0.3 complete"`.
- Tests: any tests for friction-polish items that have a verifiable behavior change. Existing tests continue to pass.

**Acceptance gates:**

- About dialog shows `0.3.0`.
- README "User interface" section reflects v0.3.
- SES-009 and the status update to `1.0` are present in `db-export/sessions.json` and `db-export/status.json`.
- Full test suite passes. Estimated 510+ tests passing (slice C and D contribute most of the new tests; slice E's additions are minimal).
- All 16 PRD acceptance criteria verified in a final manual pass (the PRD has 16 numbered AC items; AC#15 specifically covers the closeout artifacts produced in this slice).

**Out of slice:** anything labelled "deferred to v0.4 or later" in PRD section 2.

---

## 5. Testing Strategy

### What we test in v0.3

- **`ListDetailPanel` factory methods (high coverage):** default `QTableView` returned by base; override returns custom widget; context-menu factory invocation on right-click; empty menu silently ignored.
- **Per-panel parity (medium coverage):** for each panel class, assert master-widget type and context-menu factory return type. New file `test_list_detail_panel_factories.py`.
- **Per-panel context-menu sweep (medium coverage):** for each panel, assert the action set surfaced by right-click matches the expected list. New file `test_context_menus.py`.
- **`EntityIdentifierPicker` (medium coverage):** entry list rendering, autocomplete filter against identifier and title substrings, selection emission, clear-selection behavior.
- **`ReferenceCreateDialog` (high coverage):** cascade behavior (changing source type filters kind options; changing kind filters target-type options), strict vocab compliance (invalid combinations unreachable), pre-population from detail-pane caller, save flow with success and validation-error paths.
- **`ReferenceDeleteDialog` (low coverage):** confirmation modal renders edge text; confirm sends `DELETE /references/{id}`; cancel does nothing.
- **`SessionCreateDialog` (high coverage):** field set per PRD §2.4, identifier auto-assignment, required-field validation, status default to Complete, placeholder text correct, save flow.
- **References panel write integration (medium coverage):** toolbar `New Reference` opens dialog; right-click `New reference` opens dialog; right-click `Delete reference` opens confirmation; successful create / delete refreshes the panel.
- **`ReferencesSection` widget extensions (medium coverage):** `Add reference` button opens dialog with source pre-populated; right-click delete on rendered row opens confirmation; click-to-navigate preserved.
- **Sessions panel write integration (medium coverage):** toolbar `New Session` opens dialog; right-click `New session` on whitespace opens dialog; successful create refreshes the panel; no Edit/Delete buttons exist on detail pane.

### What we defer to v0.4

- Click-through interaction tests for the broader workflows (filling a multi-field create dialog, clicking Save, verifying the row in the table is present and contents match).
- Visual regression testing.
- Cross-platform automated runs.
- Stress testing (panels with hundreds of records).
- Reference filtering by relationship type.

### Target

- Full UI test suite still runs in under 90 seconds (v0.3's additions are roughly 50 tests).
- Every new test imports its fixtures from `conftest.py` rather than re-declaring fixtures inline.

---

## 6. Dependencies and Configuration

### New Python dependencies

None. v0.3 uses only `PySide6`, `httpx`, and `pytest-qt`, all already present from v0.1.

### Configuration

Unchanged. `crmbuilder_v2.config.get_settings()` is the source.

### File system locations

Unchanged. Logs at `~/.crmbuilder-v2/ui.log`; database at `crmbuilder-v2/data/v2.db`; snapshots at `PRDs/product/crmbuilder-v2/db-export/`.

---

## 7. Commit Strategy

Each prompt produces one or more commits, all prefixed `v2:`. Suggested per-prompt commit shapes:

| Prompt | Suggested commits |
|---|---|
| A | `v2: ui v0.3 planning records — SES-008, DEC-032 through DEC-037, PI-NNN` <br> `v2: ui v0.3 ListDetailPanel factory refactor + Topics migration` |
| B | `v2: ui v0.3 — right-click context menus across existing panels` |
| C | `v2: ui v0.3 — EntityIdentifierPicker widget` <br> `v2: ui v0.3 — references create + delete dialogs` <br> `v2: ui v0.3 — references panel + ReferencesSection write integration` |
| D | `v2: ui v0.3 — session create dialog + Sessions panel write integration` |
| E | `v2: ui v0.3 — closeout, About 0.3.0, README, SES-009, status v1.0` |

After each prompt's commits land, the v2 status record gets a one-line update reflecting progress. At end of E, status is updated to `"v0.3 complete"` (version label `1.0`) and SES-009 is appended.

---

## 8. Risk Register

Prompt-level risks (cross-cutting risks live in PRD section 9):

| Risk | Slice | Mitigation |
|---|---|---|
| Slice A's `_build_ui` rewrite to call `_create_master_widget()` introduces a subtle regression in a panel that v0.2's tests don't catch (e.g., a configuration step that was applied inline to `QTableView` is omitted from the factory's default) | A | Slice A's prompt enumerates every configuration step the previous `_build_ui` applied to the master view and asserts they're all reproduced inside the default factory. The new parity tests assert master-widget type per panel, which catches the gross failure case. The v0.2 tests catch behavior regressions. If a UX-only regression slips through (e.g., row spacing changes), slice E's polish phase catches it. |
| Right-click sweep in slice B introduces an inconsistency where one panel's menu actions don't match its toolbar (e.g., a Delete that's a soft-delete in one place and a hard-delete in the menu) | B | Each panel's context-menu actions are wired to the same handler slots as the toolbar / detail-pane buttons — the menu is a second entry point, not a parallel implementation. The sweep test in `test_context_menus.py` asserts the expected action set per panel; a divergence shows up as a test failure. |
| `RELATIONSHIP_TYPES` vocab in `access/vocab.py` does not have the structure needed to drive the cascade (e.g., kinds aren't keyed by `(source_type, target_type)` constraints) | C | Slice C's prompt reads `vocab.py` and the references repository before declaring the dialog's filter logic. If the vocab needs reshaping, the change is part of slice C and is mechanical (a refactor of the vocab dict, no consumer-side changes). |
| `EntityCrudDialog`'s `FieldSchema` cannot cleanly express the cascading-filter dependency between fields | C | Slice C's prompt enumerates the fork: extend `FieldSchema` with `depends_on` and `compute_options` if mechanical (preferred), otherwise build a thin parallel base for cascading dialogs. Both paths are bounded; the slice resolves on first contact and documents the choice in the slice's reporting. |
| Identifier auto-assignment in `SessionCreateDialog` races with another writer | D | The access layer enforces unique identifiers; on collision the API returns a validation error. The dialog re-fetches the latest session list and retries once; a second collision (extremely unlikely outside test scaffolding) surfaces in the generic `ErrorDialog`. |
| `POST /sessions` HTTP endpoint is missing — the existing `apply_dec_025.py` script writes through the access layer directly | D | Slice D's prompt verifies the API surface as its first investigation step. If `POST /sessions` is missing, the slice adds it as a thin wrapper around the existing access-layer method. |
| File-watch refresh map doesn't include `references` or `sessions` and panel updates require manual Refresh | C, D | Slices C and D each verify the refresh map and extend it if needed. The fix is a one-line addition. |
| Hard-delete on a reference creates a footgun if the user mis-clicks the right-click menu | C | The confirmation modal explicitly states "This cannot be undone through the UI." The confirm button is `Delete` (red), Cancel is the default focus. If real-use surfaces accidental deletions, v0.4 reconsiders soft-delete; v0.3 trusts the modal. |

---

## 9. Order of Operations Across the Series

The five prompts are sequential — each builds on the previous. A is the prerequisite for all subsequent slices (the factory refactor lands in A; B uses the context-menu factory; C and D wire write actions through the right-click menus established in B). C and D could be parallelized in principle (each is a self-contained per-feature slice that depends only on A and B); in practice, single-developer execution does them in order, with C first because the right-click-delete pattern on `ReferencesSection` is exercised across every detail pane and surfaces any cross-panel issues earlier than D's narrower Sessions surface would.

After approval of this plan:

1. v2-ui-v0.3-A is drafted, reviewed, and executed.
2. Results reviewed; any prompt-level fixes applied before proceeding.
3. Repeat through v2-ui-v0.3-E.
4. After E, the closeout records (SES-009, status `1.0`) are written. v0.3 ships.

If review of any prompt's results surfaces a missed requirement that affects subsequent prompts, the affected later prompts are re-drafted before execution. The plan is a living document for the duration of the build; any material change is committed as a plan version bump (`0.2`, `0.3`, etc.) with an entry in the change log.

---

## 10. Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-09-26 17:30 | Initial draft. Decomposes the UI v0.3 build into five sequential prompts (v2-ui-v0.3-A through v2-ui-v0.3-E). Captures the new `EntityIdentifierPicker` widget, the `ListDetailPanel` factory refactor, the cascading-filter dialog pattern for `ReferenceCreateDialog`, the per-slice deliverables, acceptance gates, and out-of-slice notes. |
