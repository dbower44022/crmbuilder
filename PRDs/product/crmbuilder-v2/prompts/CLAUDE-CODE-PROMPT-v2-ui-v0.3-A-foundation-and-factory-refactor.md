# CLAUDE-CODE-PROMPT-v2-ui-v0.3-A-foundation-and-factory-refactor

**Last Updated:** 05-09-26 17:30
**Series:** v2-ui-v0.3
**Slice:** A (1 of 5)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-F (UI v0.2 closeout — 458 v2 tests passing as of SES-007)

## Purpose

This is the first of five slices that build the CRMBuilder v2 desktop UI v0.3 per the companion PRD and implementation plan. This prompt builds slice **A — Foundation and factory refactor**.

Slice A produces three deliverables, layered:

1. **Planning records.** The conversation that produced the v0.3 PRD and plan is captured in the v2 database — SES-008 (the planning session), DEC-032 through DEC-037 (the six architectural decisions made during that conversation), six `decided_in` references from SES-008 to those decisions, PI-NNN tracking the deferred styling pass, and a status update reflecting that v0.3 is now in build. Per DEC-025, SES-008's `conversation_reference` is descriptive text and `topics_covered` opens with the verbatim seed prompt.

2. **`ListDetailPanel` factory refactor.** Two factory methods added to the base class (`_create_master_widget` and `_build_context_menu`), with sensible defaults so existing subclasses continue to work without edits. The Topics panel is migrated to use `_create_master_widget` and the v0.2 `self._table = self._tree` workaround is removed.

3. **Per-panel parity tests.** New test file asserting master-widget type and context-menu factory return type for every panel.

After this slice, the foundation is in place. Slice B sweeps right-click context menus across every panel using the new `_build_context_menu` factory; slice C builds the References write surface; slice D adds Sessions create; slice E is closeout. This slice does NOT add any new dialog, any context-menu population, any References or Sessions write surface — those land in their own slices.

## Project context

UI v0.2 shipped 05-09-26 (SES-007, status v0.8, phase `"v0.2 complete"`). The v2 stack is end-to-end: SQLite + Alembic + access layer + REST API + MCP server + PySide6 UI. 458 v2 tests pass.

The v0.3 planning conversation (SES-008, this slice's planning record) confirmed v0.3's frame as "complete the testability gap" — close the gap that prevents v2 from being used as a real governance tool without leaving the UI. Two write surfaces (References full CRUD, Sessions create-only), one architectural cleanup (the `ListDetailPanel` factory refactor deferred from v0.2 slice F), and one global UX principle (right-click context menus uniform across every entity row) constitute v0.3's scope. The full styling pass per DEC-024 is deferred again with PI-NNN tracking so the third deferral does not drift into a fourth.

The v0.3 architecture introduces no new layer or transport. The factory refactor is a refinement of `ListDetailPanel`'s existing `_build_ui` to replace inline widget construction with two factory method calls — both with defaults that preserve the current behavior of every existing panel. Topics is the only panel that overrides the master-widget factory in slice A; every other panel's right-click factory is overridden in slice B.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug`
   - `git config user.email` should return `doug@dougbower.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational. Verify-first, only start if not already running:
   - First check: `curl -sf http://127.0.0.1:8765/health` — if it returns 200, the API is already running; proceed to step 6.
   - If the health check fails (connection refused or no response), start the API in the background: `uv run crmbuilder-v2-api &`. Wait ~3 seconds, then re-run the health check. If the second check still fails, stop and report to Doug before proceeding.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 458 tests passing.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay particular attention to the "CRMBuilder v2 — Methodology Rearchitecture" section.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` — the requirements you are implementing. All slices.
3. `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` — the slice breakdown. Pay particular attention to **Step A** in section 4.
4. **Tier 2 orientation** (per DEC-011), via either MCP or the JSON snapshots:
   - Current charter
   - Current status (v0.8, `"v0.2 complete"`)
   - SES-007 (most recent prior session, the v0.2 build closeout)
   - DEC-026 through DEC-031 (v0.2's architectural decisions, still in force where applicable; DEC-027 is partially superseded by DEC-032 in scope but its v0.2 record is preserved)
   - DEC-013, DEC-014, DEC-024, DEC-025 (load-bearing for v0.3's session, sessions, styling, and conversation-reference conventions)
5. v0.2's existing `ListDetailPanel` and `TopicsPanel` code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py`
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py` — currently uses the `self._table = self._tree` workaround
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py`, `sessions.py`, `risks.py`, `planning_items.py`, `references.py`, `charter.py`, `status.py` — to confirm none of them override `_build_ui` in a way that would conflict with the factory refactor
6. v2 storage surfaces (read-only — do not modify in this slice):
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py` — `POST /decisions`
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py` — `POST /sessions`
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/references.py` — `POST /references`
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/planning_items.py` — `POST /planning_items` for PI-NNN
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/status.py` — `PUT /status`
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `RELATIONSHIP_TYPES`, `SESSION_STATUSES`, `PLANNING_ITEM_TYPES`, `PLANNING_ITEM_STATUSES`

## Step 1 — Write planning records to the database

Capture the planning conversation that produced the companion PRD and plan. Write these records via the running REST API (or via MCP if your client is connected — both reach the same database).

### Decisions (six new records, DEC-032 through DEC-037)

Each decision below should be written as a `POST /decisions` call. All have `decision_date: "05-09-26"` and `status: "Active"`. Use the verbatim body text in **Appendix A** below for `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences`. Do not paraphrase or summarize.

- **DEC-032** — v0.3 frame: complete the testability gap so v2 can drive real governance work without leaving the UI
- **DEC-033** — References write surface: panel + detail-pane entry points; source-first cascading dialog with strict RELATIONSHIP_TYPES vocab compliance; autocomplete combo identifier picker; no edit affordance; hard-delete with confirmation
- **DEC-034** — Sessions create-only via UI: user-authored sessions permitted; append-only stays strict; sessions remain narrow-scoped to Claude.ai conversations
- **DEC-035** — ListDetailPanel master-widget + context-menu factory refactor with targeted parity-test discipline
- **DEC-036** — Right-click context menus uniform across all entity rows as a global UX principle
- **DEC-037** — Full styling pass deferred again with PI-NNN tracking; v0.3 micro-visual adjustments allowed within scope

### Session (one new record, SES-008)

Per DEC-025, the `conversation_reference` is descriptive text identifying the conversation by its outputs (no transcript), and `topics_covered` opens with the verbatim seed prompt.

Write a `POST /sessions` call with:

- `identifier: "SES-008"`
- `title: "UI v0.3 planning"`
- `session_date: "05-09-26"`
- `status: "Complete"`
- `conversation_reference`: `"Claude.ai planning conversation that produced ui-PRD-v0.3.md, ui-v0.3-implementation-plan.md, and the CLAUDE-CODE-PROMPT-v2-ui-v0.3 series under PRDs/product/crmbuilder-v2/. No transcript preserved per DEC-025."`
- `topics_covered`: the text in **Appendix B** below verbatim. Opens with the seed prompt rendered as `Seed prompt: "<the task statement>"` per DEC-025, followed by a structured summary of the nine architectural questions discussed.
- `summary`: the text in **Appendix C** below.
- `artifacts_produced`: the text in **Appendix D** below.
- `in_flight_at_end`: `""`.

### Planning item (one new record, PI-NNN)

The styling pass deferred per DEC-037 is tracked as a planning item. Write a `POST /planning_items` call with:

- `identifier`: the next available `PI-NNN` (query the planning-items list to find the next sequence number).
- `title`: `"Full styling design pass per DEC-024"`
- `type`: an appropriate value from `PLANNING_ITEM_TYPES` — likely `"pending_work"` (read `vocab.py` to confirm the exact vocabulary value).
- `status`: `"Open"` (or whatever the equivalent value is in `PLANNING_ITEM_STATUSES`; read `vocab.py` to confirm).
- `description`: the text in **Appendix E** below.
- `target_release`: `"v0.5 (dedicated styling release after v0.4 unless other priorities reorder)"` (or omit if `target_release` is not a field on the planning_item schema; read the schema to confirm).

If the planning_item schema does not have all the fields listed (e.g., `target_release`), include only those that are present. The intent is a tracked record that the next planning conversation will engage when the deferred work is taken up.

### References (six new records)

For each of DEC-032 through DEC-037, write a `POST /references` call:

- `source_type: "session"`
- `source_id: "SES-008"`
- `target_type: "decision"`
- `target_id: "DEC-NNN"` (one per decision)
- `relationship_kind: "decided_in"` (confirm the exact field name against the schema; v0.2 used `relationship_kind`)

### Status update

Append a new status version via `PUT /status`. The new payload should:

- Set `phase` to `"v0.3 in build"`.
- Set `sub_step` to `"Slice A foundation and factory refactor in progress: writing planning records (SES-008, DEC-032 through DEC-037, PI-NNN, six references), refactoring ListDetailPanel with _create_master_widget and _build_context_menu factory methods, migrating Topics panel to use the new master-widget factory, and adding per-panel parity tests."`.
- Set `active_work` to `"Slice A — foundation and factory refactor (this conversation's execution work)."`.
- Update `live_inventory.in_database` counts to reflect: 37 decisions (DEC-001 through DEC-037), 8 sessions (SES-001 through SES-008), charter unchanged, status versions +1, references +6 (36 total), planning_items +1.
- Add a new field `pending.ui_v0_3_remaining_slices` listing slices B through E per the implementation plan.
- Preserve everything else from status v0.8 that remains accurate. The previous `pending.ui_v0_3_backlog` field should be removed (its content is now reflected in the v0.3 PRD itself).
- Set `version_label` to `"0.9"`.
- Update `metadata.Last Updated` to today's date in `MM-DD-YY` format.

### Verify

After the writes:

- The `db-export/` directory should have updated `decisions.json`, `sessions.json`, `references.json`, `planning_items.json`, `status.json`, and `change_log.json` files. Inspect them and confirm the expected records are present.
- Commit all changes under `db-export/` in a single commit:

```
v2: ui v0.3 planning records — SES-008, DEC-032 through DEC-037, PI-NNN
```

## Step 2 — Refactor `ListDetailPanel` to use factory methods

Open `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py`.

### Add `_create_master_widget` factory method

Add a new method (placement before `_build_ui` is conventional):

```python
def _create_master_widget(self) -> QAbstractItemView:
    """Factory for the master pane's view widget.

    Override to use a non-default widget type (e.g., QTreeView for
    hierarchical entities). The default returns a QTableView configured
    with the same default policies the v0.2 implementation applied
    inline in _build_ui.
    """
    view = QTableView(self)
    # The exact configuration below mirrors the v0.2 inline construction.
    # Read the existing _build_ui first and reproduce every configuration
    # call on the table here. Common settings include:
    #   view.setSelectionBehavior(QAbstractItemView.SelectRows)
    #   view.setSelectionMode(QAbstractItemView.SingleSelection)
    #   view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    #   view.setAlternatingRowColors(True)
    #   view.verticalHeader().setVisible(False)
    #   etc.
    return view
```

Required reading: read the existing `_build_ui` body in this file and the corresponding `setSelection*`, `setEdit*`, `setHorizontalHeader*`, etc. calls applied to the master view. Reproduce every one inside the factory's default implementation. The factory must produce a widget identical in configuration to what the previous inline construction produced — otherwise downstream panels will subtly regress.

### Add `_build_context_menu` factory method

Add a second factory method:

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    """Factory for the right-click context menu.

    Override to add entity-specific actions. The default returns an
    empty QMenu, which the base treats as "no menu shown" — the
    customContextMenuRequested handler silently returns when the menu
    has no actions.
    """
    return QMenu(self)
```

### Rewrite `_build_ui` to call the factories

Replace the inline `QTableView()` construction with `self._master_view = self._create_master_widget()`. Wire the context-menu factory:

```python
self._master_view.setContextMenuPolicy(Qt.CustomContextMenu)
self._master_view.customContextMenuRequested.connect(self._on_context_menu_requested)
```

Add the slot:

```python
def _on_context_menu_requested(self, position: QPoint) -> None:
    index = self._master_view.indexAt(position)
    menu = self._build_context_menu(index)
    if menu.actions():
        menu.exec(self._master_view.viewport().mapToGlobal(position))
```

The slot is intentionally tolerant of an empty menu — when no actions are present (the base class default), nothing is shown.

### Aliasing concern

The existing v0.2 pattern likely stores the master view as `self._table` in `_build_ui`. If subclasses reference `self._table` directly (which they do — slice planning identified the `self._table = self._tree` workaround in `TopicsPanel`), preserve that attribute name. The simplest approach: store the factory result in `self._master_view` AND assign `self._table = self._master_view` so existing subclass references continue to resolve. (The Topics migration in Step 3 will drop the `self._tree` alias entirely; other panels continue to work via `self._table`.)

If you find that v0.2 stored the master view under a different attribute name (e.g., `self._view`), use that name instead. Read the existing code to confirm.

### Tests at this step

Run `uv run pytest tests/crmbuilder_v2/ui/ -v`. Every existing test should still pass after this refactor. The factory's default implementation must produce a widget identical to what the previous inline construction produced.

If any test fails:
- A widget configuration step in the previous `_build_ui` is missing from the factory's default. Add it.
- A subclass reference to a specific attribute is broken. Add the alias as described above.

Do not commit until all 458 v0.2 tests pass.

## Step 3 — Migrate `TopicsPanel` to use the master-widget factory

Open `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py`.

The v0.2 implementation overrides `_build_ui` (or some part of construction) and includes the workaround `self._table = self._tree`. Replace this pattern with a clean factory override:

```python
def _create_master_widget(self) -> QAbstractItemView:
    tree = QTreeView(self)
    # Reproduce every configuration call the v0.2 panel applied to
    # the QTreeView (header config, expand/collapse defaults, selection
    # mode, etc.).
    return tree
```

Remove:
- Any override of `_build_ui` that was added in v0.2 slice D.
- The `self._table = self._tree` aliasing line.
- Any other workaround that was specifically introduced because `_build_ui` couldn't be parameterized.

The model-construction code (the `QStandardItemModel` build-from-flat-list loop) stays. The selection-changed signal hookup stays. Everything that touches the model or the panel's behavior stays. Only the widget-instantiation indirection changes.

### Tests at this step

Run `uv run pytest tests/crmbuilder_v2/ui/test_topics_panel_writes.py -v` (or whatever the v0.2 Topics tests are named). All existing Topics tests should continue to pass — the panel renders as `QTreeView`, click-to-select updates the detail pane, parent-child nesting works.

## Step 4 — Per-panel parity tests

Create a new test file `tests/crmbuilder_v2/ui/test_list_detail_panel_factories.py`.

For each panel class under `crmbuilder_v2.ui.panels`, write two tests:

1. **Master-widget type assertion.** Instantiate the panel, then assert `isinstance(panel._master_view, ExpectedType)`. `ExpectedType` is `QTableView` for every panel except `TopicsPanel`, which gets `QTreeView`.
2. **Context-menu factory smoke test.** Instantiate the panel, call `panel._build_context_menu(QModelIndex())`, and assert the returned object is a `QMenu` instance. (The action set is asserted in slice B's tests.)

Use the existing `qtbot` and `qapp` pytest-qt fixtures. Reference the v0.2 panel-test patterns under `tests/crmbuilder_v2/ui/` for the panel construction idiom.

Sample test shape:

```python
def test_decisions_panel_uses_qtableview(qtbot, mock_client):
    panel = DecisionsPanel(client=mock_client)
    qtbot.addWidget(panel)
    assert isinstance(panel._master_view, QTableView)

def test_decisions_panel_context_menu_factory_returns_qmenu(qtbot, mock_client):
    panel = DecisionsPanel(client=mock_client)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert isinstance(menu, QMenu)
```

Cover every panel class (Decisions, Sessions, Risks, Planning Items, Topics, References, Charter, Status). For Charter and Status, if their master view is part of `VersionedPanel` rather than `ListDetailPanel`, adapt the test accordingly — the parity assertion is on the master view's type, regardless of which base class housed it.

### Run tests

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 458 v0.2 tests + ~16 new factory tests (8 panels × 2 tests). Total ~474 passing.

## Step 5 — Commit, push, report

Two commits in this slice:

1. The planning-records commit from Step 1.
2. A factory-refactor commit covering Steps 2–4:

```
v2: ui v0.3 ListDetailPanel factory refactor + Topics migration
```

Push:

```
git pull --rebase origin main
git push origin main
```

## Acceptance gates

Before marking the slice complete, verify:

- [ ] `db-export/decisions.json` has new records DEC-032 through DEC-037 with verbatim body text per Appendix A.
- [ ] `db-export/sessions.json` has SES-008 with `topics_covered` opening with the verbatim seed prompt per DEC-025.
- [ ] `db-export/references.json` has six new `decided_in` references from SES-008.
- [ ] `db-export/planning_items.json` has the new PI-NNN tracking the deferred styling pass.
- [ ] `db-export/status.json` shows version_label `"0.9"` and phase `"v0.3 in build"`.
- [ ] `panels/topics.py` no longer contains `self._table = self._tree`.
- [ ] `_create_master_widget` and `_build_context_menu` exist in `base/list_detail_panel.py` with the documented signatures.
- [ ] `_build_ui` calls `self._create_master_widget()` and wires `customContextMenuRequested` to a slot that calls `self._build_context_menu()`.
- [ ] All 458 v0.2 tests still pass.
- [ ] New parity tests in `test_list_detail_panel_factories.py` pass — at least 16 new tests (master-widget + context-menu factory across 8 panels).
- [ ] Two commits pushed: one for planning records, one for the factory refactor.

## Out of slice

The following are NOT part of slice A and must not be added:

- Any context-menu actions (Edit / Delete / Restore / etc.). The factory's default returns an empty menu; per-panel overrides land in slice B.
- Any References write surface. The dialog, the `New Reference` button, the `Add reference` affordance on `ReferencesSection`, the right-click delete on reference rows — all land in slice C.
- Any Sessions create surface. The dialog, the `New Session` button — both land in slice D.
- Any micro-visual adjustments (relationship-kind colored pill, `Add reference` button styling) — those land in slice E if they land at all.
- Any styling pass work — deferred to a future release per DEC-037 / PI-NNN.

## Constraints

- Do not change `_build_ui` in a way that breaks any v0.2 panel's rendering. The factory's default must be a drop-in replacement for the v0.2 inline `QTableView` construction.
- Do not break v0.2's existing behavior on any panel. The 458 v0.2 tests are the regression net.
- Do not modify the storage system schema. The factory refactor is UI-side only.
- Do not skip the planning records. SES-008 must be written before any code change is committed; the slice's first commit is the planning records, the second commit is the factory refactor.
- Do not paraphrase the decision body text in Appendix A. Use the verbatim text.

## Reporting

After all five steps complete, report back to Doug with:

- Confirmation that all five acceptance gates above are checked.
- The final test count (`uv run pytest tests/crmbuilder_v2/ -v` summary line).
- Any deviations from the plan or surprises encountered, with rationale for the deviation.
- Any questions or open items for slice B.

Slice B (right-click context menus across existing panels) is the next slice. Its prompt is `CLAUDE-CODE-PROMPT-v2-ui-v0.3-B-right-click-menus.md` and is ready to execute as soon as slice A is reported complete.

---

## Appendix A — Decision body text (verbatim)

The text below is to be written verbatim into the `context`, `decision`, `rationale`, `alternatives_considered`, and `consequences` fields of each decision record. Multi-line fields are written as-is into the database.

### DEC-032 — v0.3 frame: complete the testability gap so v2 can drive real governance work without leaving the UI

**context**

UI v0.2 shipped on 05-09-26 with full create/edit/delete for Risks, Planning Items, and Topics, plus versioned-replace for Charter and Status, plus generalized reference rendering on every detail pane. With v0.2 in hand, four of the eight v2 entity types (Decisions, Risks, Planning Items, Topics) have full CRUD; two (Charter, Status) have versioned-replace + history; two (Sessions, References) remain read-only.

The two read-only entities are exactly what makes v2 untestable end-to-end as a real governance tool. Every Claude.ai conversation that produces governance content currently ends with a Python script — `apply_dec_025.py`, `apply_session_007.py`, and so on — writing the SES-NNN record and its `decided_in` references on Doug's behalf. The script-based path works, but it means the UI is not the operational tool; it is a viewer over an operational tool that lives in scripts.

**decision**

v0.3 is framed as "complete the testability gap so v2 can drive real governance work without leaving the UI." The primary work is two write surfaces: References full CRUD (create + delete; no edit because edges are immutable identity-wise) and Sessions create-only (no edit, no delete because DEC-013 establishes append-only). One architectural cleanup lands alongside: the `ListDetailPanel` master-widget factory refactor deferred from v0.2 slice F, plus a global UX principle (right-click context menus uniform across every entity row) that lifts the project's overall affordance density. The full styling pass per DEC-024 is deferred again with PI-NNN tracking so the third deferral does not drift into a fourth.

**rationale**

After v0.3 ships, every governance write the project produces — including the records of v0.3's own planning conversation as the first dogfood — can be authored entirely through the desktop application. That is the user-facing acceptance test for v0.3: the next planning conversation after v0.3, call it v0.4's planning session, can be captured by Doug, in the app, with no script runs.

The factory refactor and right-click sweep are not testability-blocking individually but are the right scope for v0.3 because (a) the factory cleanup is overdue from v0.2 slice F, (b) the right-click sweep is a cohesive UX principle that is incoherent at half-coverage, and (c) introducing both write surfaces into a base class with the factory cleanup creates leverage that v0.4 onwards inherits cleanly.

**alternatives_considered**

- Defer the factory refactor again. Rejected — v0.2 slice F already deferred it once on regression-risk grounds. v0.3 has a smaller slice count overall, leaving room for a focused refactor with proper test discipline. Pushing the cleanup further accumulates working-around-it cost in every subsequent v2 panel addition.
- Include the full styling pass per DEC-024. Rejected — testability is the v0.3 frame, and styling is a different category of design work (visual identity, accessibility, theme coherence). Tucking it into a release that's adding two new write surfaces and a refactor would produce a half-pass. PI-NNN tracking commits to a future dedicated styling release.
- Add Priority-4 nice-to-haves (reference filtering, JSON diff view, global search, exports, bulk operations, methodology entity panels, keyboard shortcuts). Rejected — none move the testability needle, and a 4–5 slice release with focused intent ships better than a 6–8 slice grab-bag.
- Broaden the Sessions concept to include non-Claude.ai conversations (phone calls, in-person meetings). Rejected — DEC-013 ties sessions to Claude.ai conversations specifically. Broadening is a separate decision to make later if the need surfaces.

**consequences**

v0.3 is decomposed into five prompts in the build series. Slice A delivers planning records + the `ListDetailPanel` factory refactor. Slice B sweeps right-click context menus uniformly across every existing entity panel. Slice C delivers the References write surface (create dialog with cascading filters, delete confirmation modal, `EntityIdentifierPicker` widget, panel button, detail-pane `Add reference` affordance, right-click delete on reference rows in both the panel and `ReferencesSection`). Slice D delivers the Sessions create-only dialog. Slice E is closeout: micro-adjustments observed during build, About 0.3.0, README, SES-009, status update to v1.0. After v0.3 ships, the next governance writeable target is the styling pass tracked under PI-NNN.

---

### DEC-033 — References write surface: panel + detail-pane entry points; source-first cascading dialog with strict RELATIONSHIP_TYPES vocab compliance; autocomplete combo identifier picker; no edit affordance; hard-delete with confirmation

**context**

References are the graph edges between entities — `(source_type, source_id, relationship_kind, target_type, target_id)` records that say "this decision was decided in this session," "this decision supersedes this earlier decision," "this risk affects this domain," etc. v0.2's `ReferencesSection` widget renders inbound and outbound edges on every detail pane, but the only path to create or delete a reference today is via API call or governance script (e.g., `apply_dec_025.py`). For v0.3's testability frame, references must be authorable through the UI.

The design space has four moving parts: (a) where the user enters the create flow, (b) the order in which they pick source/kind/target, (c) how strictly the `RELATIONSHIP_TYPES` vocab constrains valid combinations, (d) what happens on edit and delete.

**decision**

The References write surface combines panel-level and detail-pane entry points. The References panel toolbar gets a `New Reference` button. Every detail pane's `ReferencesSection` widget gains an `Add reference` affordance (button at the bottom or `+` icon in the section header — slice C picks the more natural placement). Both entry points open the same `ReferenceCreateDialog` with optional pre-populated source.

The dialog uses source-first picking order: source type and identifier come first (or are pre-populated from the detail pane), then relationship kind (filtered to valid kinds for the source type), then target type (filtered by source type and kind), then target identifier. Strict `RELATIONSHIP_TYPES` vocab compliance — dropdowns only ever show valid choices for the partially-filled state, so invalid combinations are unrepresentable in the dialog. The vocab is read from `access/vocab.py` at dialog-open time so new kinds appear automatically as the access layer evolves.

Identifier picker is an editable `QComboBox` with `QCompleter` configured for `Qt.MatchContains`, populated with `IDENTIFIER — title` items. The same widget is reused for source and target identifier fields (a new `EntityIdentifierPicker` under `ui/widgets/`).

No edit affordance. References are immutable identity-wise; "edit" is delete + create. Hard-delete with confirmation modal showing the edge text — "Delete the reference [SES-006 → DEC-026: decided_in]? This cannot be undone through the UI." — Cancel / Delete. No tombstone, no Show-deleted toggle, no Restore.

**rationale**

Source-first matches the dominant workflow ("I'm reviewing DEC-032, this is decided in SES-009 — let me link them"). From the detail pane the source is fixed, leaving three choices for the user; from the References panel the user picks source first naturally because "I'm linking X to Y" is how the mental model runs. Strict vocab compliance turns the dropdowns themselves into documentation — when you pick source=decision, the kind dropdown shows you exactly which relationships decisions can participate in. The cascading filters ensure no Save error path exists for invalid combinations.

No edit follows from references being graph edges, not entity records. Edge identity is `(source, kind, target)`; changing any of those is a different edge. Edit-as-replace is the same number of clicks as delete + create, and "editing" graph edges has no clean mental model. Skipping the edit path eliminates an entire dialog mode and a class of "edit corrupted my reference" failures.

Hard-delete reflects that references are derivative — the entities they connect carry the substance, not the edge itself. Removing a wrong edge should make it gone, not leave a tombstone in every list and detail pane forever. Audit goes through git-tracked `db-export/references.json` snapshots and (where present) the storage-layer `change_log` table.

**alternatives_considered**

- Panel-only entry point (References panel toolbar `New Reference` button, no detail-pane affordance). Rejected — too heavy for the dominant use case where the user is already viewing one of the entities being linked. Six clicks vs. two from the natural workflow path.
- Detail-pane only (no panel-level button). Rejected — purist but eliminates a useful escape hatch when the user wants to link two entities they have IDs for in their head without first navigating to either side.
- Kind-first picking (relationship kind first, then source and target types filtered). Rejected — awkward when source is pre-populated from a detail pane. Source-first generalizes cleanly to both entry points.
- Permissive vocab with validation on save. Rejected — invalid intermediate states allow the user to construct bad combinations and only learn about the error after Save. Strict cascading filters teach the vocab through the UI itself.
- Soft-delete on references with a `deleted_at` column and a Show-deleted toggle paralleling Decisions. Rejected — references aren't first-class governance content; tombstones bloat the panel monotonically and don't pay for the bloat. Audit through git history is sufficient for derivative content.
- Edit affordance for references. Rejected — graph edges have no edit semantic that isn't equivalent to delete + create.

**consequences**

Slice C of the v0.3 build delivers the full References write surface: `ReferenceCreateDialog`, `ReferenceDeleteDialog`, `EntityIdentifierPicker` widget, panel `New Reference` button, detail-pane `Add reference` affordance, right-click delete on reference rows in both the panel and the `ReferencesSection` widget on every detail pane. Storage-layer additions if needed are mechanical: `DELETE /references/{id}` if missing, `RELATIONSHIP_TYPES` vocab reshape if its current structure doesn't key kinds by `(source_type, target_type)` constraints. v0.4 reconsiders soft-delete only if real-use surfaces accidental deletions as a recurring problem.

---

### DEC-034 — Sessions create-only via UI: user-authored sessions permitted; append-only stays strict; sessions remain narrow-scoped to Claude.ai conversations

**context**

DEC-013 establishes that one Claude.ai conversation equals one session record, append-only — once written, sessions are not edited. DEC-014 establishes that every conversation engaging v2 work produces a session record. DEC-027 (in v0.2's scope statement) inferred that Claude is the writer of session records via post-conversation script. The inference was load-bearing for excluding Sessions from v0.2's write surface.

Re-reading DEC-013 and DEC-014 carefully: neither says Claude must be the only writer. They say what a session record is (one per Claude.ai conversation, append-only) and that every v2 conversation produces one. The "Claude-as-writer" inference was DEC-027's interpretation, made because v0.2 didn't have a UI write surface and the script path was the de-facto creation mechanism.

For v0.3's testability frame, the user must be able to record sessions through the UI — otherwise every governance conversation still ends with a Python script. The question is whether enabling user-authored sessions requires revising DEC-013 or DEC-014 or merely adds a new clarifying decision.

**decision**

Session records may be authored through the UI by the user as well as written by Claude via script. Both paths produce identical records. The constraints from DEC-013 and DEC-014 stay in force: one Claude.ai conversation per session, every v2 conversation produces a record, append-only.

Practical UI consequences:

- Sessions panel gets a `New Session` toolbar button and a right-click `New session` action.
- No Edit button. No Delete button. The detail pane stays read-only for existing sessions.
- The dialog is fill-everything-once-and-save. No "Save draft" mode. The user records a session after the corresponding Claude.ai conversation closes, with all fields complete.
- Soft-delete is not added. Hard-delete is not added. Mistakes in a session record are out-of-band recoverable through the script path or direct database editing — they are not a UI flow.

Sessions stay narrow-scoped to Claude.ai conversations. v0.3 does not broaden the concept to include phone calls, in-person meetings, or other governance events that aren't Claude.ai conversations. Those are recorded as decisions, planning items, or status updates directly. Broadening is a separate decision to make later if the need surfaces.

**rationale**

The append-only constraint is what makes session records audit-grade. Allowing edits would mean any session could be quietly rewritten after the fact, undermining the chronological integrity that DEC-013 was designed to preserve. The user-authored path doesn't relax the constraint; it adds a second writer (the user, through the UI) alongside Claude (through scripts), with both bound by the same rule.

The fill-once-and-save constraint follows directly from append-only. A "Save draft" mode would introduce an editable intermediate state, which is the same as relaxing append-only. Forcing the user to compose the record outside the dialog (e.g., in a notes file) and paste in the final form preserves the constraint cleanly.

Narrowness on Claude.ai conversations preserves DEC-013's clarity. Broadening would dilute the specific audit guarantee the session log provides — that the chronological record of Claude.ai work is complete. Other governance events have their own appropriate entity types.

**alternatives_considered**

- Revise DEC-013 to relax append-only and allow session edit. Rejected — the constraint is what makes the session log valuable. Allowing edit would be a regression in audit integrity.
- Add a "Save draft" mode for in-progress sessions. Rejected — equivalent to relaxing append-only. The user can compose the record outside the dialog; the UI write happens once at the end.
- Allow session delete (soft-delete with Restore). Rejected — same audit-integrity argument. If a session needs to be removed, the operation goes through script or direct database editing, with the actor accepting responsibility for the audit gap.
- Broaden sessions to include non-Claude.ai conversations. Rejected — DEC-013 is specifically about Claude.ai conversations. Broadening dilutes the constraint and the audit guarantee. Other entity types serve other governance events.
- Defer Sessions create to v0.4. Rejected — Sessions create is a Priority-1 testability blocker for v0.3. Without it, Doug still has to drop to scripts for every conversation.

**consequences**

Slice D of the v0.3 build delivers the Sessions create-only dialog. Identifier auto-assignment, default session_date to today, default status to Complete, placeholder text on `topics_covered` and `conversation_reference` per DEC-025 conventions. Sessions panel gets the `New Session` toolbar button and right-click. No Edit, no Delete affordance anywhere in the UI. Future broadening of sessions beyond Claude.ai conversations would require revising this decision and DEC-013 jointly.

---

### DEC-035 — ListDetailPanel master-widget + context-menu factory refactor with targeted parity-test discipline

**context**

`ListDetailPanel` is the base class for every entity panel. v0.1's implementation hardcoded the master pane as a `QTableView` constructed inline in `_build_ui`. v0.2 slice D needed a `QTreeView` for Topics' hierarchical structure, and the cleanest refactor was deferred under regression-risk concerns; the slice instead used an override-and-alias workaround (`self._table = self._tree`). The workaround works but is fragile — every future hierarchical or non-table master pane would need its own version of the workaround, and the alias creates a class of subtle bugs where subclass code references `self._table` thinking it's a `QTableView` but is actually a `QTreeView`.

v0.3 also introduces a global UX principle (DEC-036): right-click context menus uniform across every entity row. Every panel needs a way to populate its context menu without each subclass rolling its own `contextMenuEvent` override.

**decision**

`ListDetailPanel` gains two factory methods:

- `_create_master_widget(self) -> QAbstractItemView` — default returns a `QTableView` configured identically to v0.2's inline construction. Subclasses needing a different master widget override the factory.
- `_build_context_menu(self, index: QModelIndex) -> QMenu` — default returns an empty `QMenu`. Subclasses populate with entity-specific actions; the base wires `customContextMenuRequested` to a slot that calls the factory and pops the menu, silently ignoring empty menus.

`_build_ui` is rewritten to call `self._create_master_widget()` instead of constructing `QTableView` inline. The Topics panel migrates to the new factory in slice A; the v0.2 `self._table = self._tree` workaround is removed.

Test discipline is targeted parity tests: for each panel, assert master-widget type and confirm `_build_context_menu` returns a `QMenu`. These catch the dominant regression risk (silently using the wrong widget type) without ballooning the test surface. v0.2's existing 458 tests are the behavior regression net.

**rationale**

The factory pattern is the right shape for parameterizing widget construction at the base-class level: subclasses opt in by overriding, and the default preserves existing behavior. Both factories are added together because adding `_build_context_menu` independently would require a second `_build_ui` refactor — combining them makes the change cohesive and one-shot.

Parity tests address the specific class of regression most likely to happen here ("master widget became the wrong type after refactor"). Behavior tests catch most regressions but can pass even if the underlying widget is subtly wrong (e.g., a `QTreeView` rendering as a flat list because the model isn't tree-shaped). Type assertion is mechanical, fast, and high-leverage.

**alternatives_considered**

- Keep the v0.2 workaround pattern for v0.3 too. Rejected — the workaround compounds with each new non-`QTableView` master pane. The cleanup is overdue; v0.3 has the test budget for it.
- Refactor only the master-widget factory; defer `_build_context_menu` to its own slice. Rejected — they're cohesive concerns (both touch how `_build_ui` constructs and configures the master widget) and combining them avoids two `_build_ui` rewrites.
- Make `_build_context_menu` opt-in via a flag rather than always-present. Rejected — adds an unnecessary configuration knob. The empty-menu default is silent (no menu shown when there are no actions), so the factory is harmless for panels that haven't yet populated their menu.
- Rely solely on v0.2's behavior tests as the regression net. Rejected — behavior tests miss the "wrong widget type" regression class. Targeted parity tests are a small, focused addition.

**consequences**

Slice A of the v0.3 build implements the factory refactor and migrates Topics. Per-panel parity tests are added. Slice B uses `_build_context_menu` to add right-click action sets across every existing panel. Slice C and slice D extend the panels' menus with new write actions. Future panels (methodology entities, post-v0.3) override the factories cleanly without copying any workaround.

---

### DEC-036 — Right-click context menus uniform across all entity rows as a global UX principle

**context**

v0.1 and v0.2 panels rely exclusively on toolbar buttons, detail-pane button strips, and (in the case of References) inline-rendered click navigation. There is no right-click menu on any row across any panel. The v0.3 References write surface introduces edge-creation and edge-deletion, which are the natural fit for context menus on the rows being edited. Adding right-click for References alone would create UI inconsistency — half the panels with right-click affordances and half without.

**decision**

Right-click context menus are added uniformly across every entity row in every panel. The actions surfaced by the menu parallel the existing toolbar and detail-pane buttons; the menu is a second entry point for the same actions, not a parallel implementation. Empty right-click (whitespace, no row selected) surfaces creation actions where applicable.

Per-panel action sets:

- Decisions: Edit / Delete / Restore (when row is deleted) / Show references
- Sessions: Go to references / Copy identifier (no Edit, no Delete — append-only)
- Risks, Planning Items, Topics: Edit / Delete
- References: Go to source / Go to target / Delete reference / New reference
- Charter and Status (version-list rows): Make Current (on non-current versions) / View payload
- References-section rows on every detail pane: Delete reference / Go to [other side]

**rationale**

Uniform right-click is a standard UX affordance on desktop applications; users expect it. Half-coverage is incoherent — the user learns "I can right-click here" on one panel and is surprised when another doesn't respond. Building it as a global principle from v0.3 onward keeps every future panel addition (methodology entities, post-v0.3) consistent without retroactive sweeps.

The action handlers reuse existing toolbar / detail-pane button slots, so right-click introduces no new business logic. The only new code is the per-panel `_build_context_menu` override — mechanical, repeatable, and trivially testable via a sweep test asserting the action set per panel.

**alternatives_considered**

- Add right-click only on the new write surfaces (References create/delete, Sessions create). Rejected — produces UI inconsistency where some panels have the affordance and others don't. The user can't predict which panels respond to right-click.
- Defer right-click to a future styling/UX release. Rejected — the References write surface specifically benefits from row-context delete (the dominant use case is "I'm looking at this edge and want to remove it"). Without right-click, the only delete path is the panel toolbar, which forces the user to first select the row and then click a separate button.
- Add right-click only on row context, not on whitespace. Rejected — panels with a `New` toolbar button benefit from right-click-on-whitespace surfacing creation, especially as panels grow taller and the toolbar drifts off-screen.

**consequences**

Slice B of the v0.3 build adds `_build_context_menu` overrides to every existing panel using the factory introduced in slice A. Action handlers wire to the same slots as the existing toolbar and detail-pane buttons. Slice C extends the References panel and `ReferencesSection` widget menus with the new write actions. Slice D extends the Sessions panel menu with `New session`. The sweep test in `test_context_menus.py` asserts action set parity per panel.

---

### DEC-037 — Full styling pass deferred again with PI-NNN tracking; v0.3 micro-visual adjustments allowed within scope

**context**

DEC-024 deferred a full styling pass from v0.1 to "v0.2 or later." DEC-026 (in v0.2's frame) deferred it again to v0.3 or later. Three deferrals in a row would establish a "we will never style this thing" pattern. The v0.3 testability frame doesn't naturally include a styling pass — visual identity, typography, accessibility, theme coherence are a different category of design work that wants its own focused release.

**decision**

The full styling pass is deferred from v0.3 to a future dedicated styling release (target: v0.5 or whatever release follows v0.4 unless other priorities reorder). A planning item (PI-NNN) is created to track the deferral as a durable record, so the third deferral does not drift into a fourth without an explicit decision.

v0.3 is allowed to introduce small visual adjustments demanded by its scope — for example, the right-click menus rendering with Qt defaults, a small colored pill on the relationship-kind label inside `ReferencesSection` if it improves readability, and the deleted-row strikethrough rendering carrying forward unchanged. These adjustments do not constitute a styling pass; they are visual decisions specifically required by what v0.3 is building.

**rationale**

Two prior deferrals deserve a more concrete commitment than another informal punt. Creating PI-NNN turns the deferral into a tracked planning item that surfaces in the same panel where every other planning item lives — there's a visible record that says "this work is owed." Without the planning item, the deferral risks becoming permanent through inattention.

Allowing scope-driven micro-adjustments is the right balance. A blanket "no visual changes in v0.3" rule would be unworkable — the references write surface needs at least minimal visual decisions about button placement and pill rendering. A blanket "we'll style as we go" rule would slowly accumulate visual debt without coordination. The middle path — small adjustments allowed within scope, full pass deferred — keeps v0.3 cohesive while not forbidding obvious local improvements.

**alternatives_considered**

- Pull the full styling pass into v0.3. Rejected — testability is the v0.3 frame, and styling is a different category of work. Tucking both into one release produces a half-pass.
- Defer styling without creating a tracking planning item. Rejected — three deferrals in a row without an explicit tracker is the path to permanent deferral. PI-NNN forces the next planning conversation to acknowledge the deferred work.
- Forbid all visual changes in v0.3. Rejected — unworkable. The new write surfaces need at least some visual choices, and forbidding them would either block slice C and D or push them to ad-hoc fixes in slice E.

**consequences**

Slice A creates PI-NNN tracking the deferred styling pass alongside the other planning records. Slice E (closeout) is the natural home for any micro-visual adjustments observed during build — the slice is intentionally light on hard requirements and heavy on polish. The next planning conversation (likely v0.4) engages PI-NNN explicitly when scoping the next release; if other priorities reorder, the planning item carries forward visibly until it lands.

---

## Appendix B — SES-008 `topics_covered` (verbatim)

The text below is the verbatim content for the `topics_covered` field of SES-008. Per DEC-025, the field opens with the seed prompt rendered as `Seed prompt: "..."` and is followed by a structured summary of the architectural questions discussed.

```
Seed prompt: "Plan v0.3 of the v2 desktop UI for the CRM Builder project. Drive a structured architectural discussion that produces three deliverables: (1) PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md — intent, scope, acceptance criteria, error handling matrix, open questions; (2) PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md — slice breakdown with deliverables and acceptance gates per slice; (3) Execution prompts under PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-{A..*}-*.md — one per implementation slice. The conversation that produces these deliverables is the v0.3 planning session and will be captured as SES-008 at the conversation's close."

The planning conversation worked through nine architectural questions in order:

1. Release shape and scope envelope. The kickoff prompt framed v0.3 as testability-first: after this release, the user intends to begin actually using v2 to drive governance work. Priority tiers proposed: Priority 1 (testability-blocking — References write, Sessions create), Priority 2 (architecturally-overdue — ListDetailPanel factory refactor), Priority 3 (independent quality — full styling pass), Priority 4 (nice-to-haves — reference filtering, JSON diff, global search, exports, bulk ops, methodology entities, keyboard shortcuts). Resolved: Priority 1 + Priority 2 in scope; Priority 3 + 4 out, with possible micro-adjustments inside the references slice for any visual convention the picker UX itself demands.

2. References write surface — entry points. Three options considered: panel-only, detail-pane + panel, detail-pane only. Resolved: detail-pane + panel (option B). The user added a global directive: right-click context menus across all panels in addition to UI elements. Confirmed retroactive sweep across all existing panels is in scope, not just the new v0.3 surfaces.

3. References picker UX — order and vocab strictness. Source-first picking order with strict RELATIONSHIP_TYPES vocab compliance, identifier picker as editable QComboBox + QCompleter on IDENTIFIER — title items. Source-first matches the dominant "I'm linking X to Y" workflow; strict compliance turns the dropdowns into vocab documentation; the autocomplete combo handles up to thousands of entries gracefully. Vocab is read at dialog-open time so new kinds appear without UI changes.

4. References edit and delete semantics. Resolved: no edit affordance (graph edges have no clean edit semantic that isn't equivalent to delete + create); hard-delete with confirmation modal showing the edge text. Soft-delete on references rejected — references aren't first-class governance content, tombstones bloat the panel monotonically, audit through git history is sufficient for derivative content.

5. Sessions create-only — governance interpretation. The kickoff prompt noted that DEC-013 / DEC-014 / DEC-027 collectively imply "Claude-as-writer" through DEC-027's interpretation, but DEC-013 and DEC-014 themselves never restrict the writer. Resolved: a new clarifying decision (DEC-034) makes the writer-side interpretation explicit and reverses it — user-authored sessions via the UI are permitted, append-only stays strict (no edit, no delete, no drafts), sessions remain narrow-scoped to Claude.ai conversations. Broadening to non-Claude conversations is a separate decision to make later if the need surfaces.

6. Sessions create dialog — content and shape. Nine fields: identifier (auto-assigned), session_date (DateField, defaults today), status (combo from SESSION_STATUSES, defaults Complete), title (line edit), summary (multi-line), topics_covered (multi-line with placeholder hinting at DEC-025 seed-prompt convention), artifacts_produced (multi-line), in_flight_at_end (multi-line, optional), conversation_reference (multi-line with placeholder hinting at DEC-025 descriptive-text convention). Single-scroll layout consistent with EntityCrudDialog pattern. No content-pattern enforcement on freeform fields — placeholders carry the convention. Right-click on session rows: Go to references / Copy identifier; no Edit / Delete / Restore.

7. ListDetailPanel master-pane factory refactor — scope and test discipline. Adopt the v0.2 slice F deferred spec verbatim: _create_master_widget factory method with QTableView default; QTreeView panels override. Add _build_context_menu factory method as cohesive companion (right-click is the global UX principle from question 2). Test discipline: targeted parity tests per panel (master-widget type assertion + context-menu factory smoke test). Slice A landing alongside planning records.

8. Styling pass per DEC-024 — go in v0.3 or defer again. Three prior deferrals would establish a permanence pattern, but testability is the v0.3 frame and styling is a different category of work. Resolved: defer again with concrete commitment closing the deferral loop — new decision (DEC-037) defers; planning item PI-NNN tracks for a future dedicated styling release; v0.3 scope-driven micro-adjustments allowed (e.g., colored pill on relationship-kind label, deleted-row strikethrough carryforward). Without PI-NNN the third deferral would be the same as the first two.

9. Slice breakdown. Resolved: five slices. A — foundation (planning records + ListDetailPanel factory refactor + Topics migration + per-panel parity tests). B — right-click context menus uniform across all existing panels. C — references write surface (EntityIdentifierPicker widget + create dialog + delete dialog + panel button + detail-pane Add reference + right-click delete). D — sessions create dialog. E — closeout (micro-adjustments + About 0.3.0 + README + SES-009 + status update to v1.0). Six decisions captured: DEC-032 (frame), DEC-033 (references), DEC-034 (sessions), DEC-035 (factory refactor), DEC-036 (right-click global principle), DEC-037 (styling deferral). PI-NNN created for styling tracker.
```

## Appendix C — SES-008 `summary` (verbatim)

```
The planning conversation worked through nine architectural questions and produced three artifacts: ui-PRD-v0.3.md (intent, scope, acceptance criteria, error handling matrix, open questions, six forthcoming decisions DEC-032 through DEC-037), ui-v0.3-implementation-plan.md (five-slice breakdown with per-slice deliverables and acceptance gates), and the CLAUDE-CODE-PROMPT-v2-ui-v0.3-A through E prompt series. v0.3 is framed as "complete the testability gap so v2 can drive real governance work without leaving the UI" — after this release ships, the next planning conversation can be captured by Doug, in the app, with no script runs. References full CRUD (create + delete; no edit; hard-delete with confirmation; source-first cascading dialog with strict RELATIONSHIP_TYPES vocab compliance), Sessions create-only (user-authored permitted; append-only stays strict; narrow-scoped to Claude.ai conversations), ListDetailPanel master-widget + context-menu factory refactor (with Topics migration and per-panel parity tests), and right-click context menus uniform across every entity row as a global UX principle. Full styling pass deferred again per DEC-037 with PI-NNN tracking to close the deferral loop.
```

## Appendix D — SES-008 `artifacts_produced` (verbatim)

```
- PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md
- PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-A-foundation-and-factory-refactor.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-B-right-click-menus.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-C-references-write-surface.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-D-sessions-create-dialog.md
- PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.3-E-closeout.md
- DEC-032 through DEC-037 (six decision records, written via the v2-ui-v0.3-A foundation-and-factory-refactor prompt)
- This session record (SES-008)
- Six decided_in references from SES-008 to DEC-032 through DEC-037
- PI-NNN tracking the deferred full styling pass per DEC-037
- Status update bumping to v0.9 reflecting v0.3 in build, slice A in progress
```

## Appendix E — PI-NNN `description` (verbatim)

```
Full styling design pass per DEC-024 deferred from v0.1 (per DEC-024), v0.2 (per DEC-026), and v0.3 (per DEC-037). The pass establishes a coherent visual language for the v2 desktop application: typography hierarchy, accent colors beyond the navy stub (#1F3864), error/warning/info states, button hierarchy, dialog framing, table row spacing, and accessibility considerations. Target release: v0.5 or whatever release follows v0.4 unless other priorities reorder. The next planning conversation should engage this planning item explicitly when scoping the next release. If three deferrals were not enough, this planning item is the lever that prevents a fourth from being silent.
```
