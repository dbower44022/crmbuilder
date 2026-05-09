# CLAUDE-CODE-PROMPT-v2-ui-v0.3-B-right-click-menus

**Last Updated:** 05-09-26 17:30
**Series:** v2-ui-v0.3
**Slice:** B (2 of 5)
**Status:** Ready to execute (after slice A is reported complete)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.3-A (planning records + ListDetailPanel factory refactor + Topics migration)

## Purpose

This is the second of five slices that build the CRMBuilder v2 desktop UI v0.3. This prompt builds slice **B — Right-click context menus across existing panels**.

Slice B sweeps right-click context-menu adoption across every existing entity panel using the `_build_context_menu` factory introduced in slice A. Each panel overrides the factory to surface entity-specific actions paralleling its existing toolbar and detail-pane buttons. Action handlers reuse existing button slots — right-click introduces no new business logic, only a new entry point.

After this slice, every panel responds to right-click on row context with the appropriate actions for that entity. References and Sessions panels get only their existing read-only actions in this slice; their write actions land in slices C and D respectively, which extend the context-menu overrides established here.

This slice does NOT add any References write actions (those land in slice C), any Sessions create action (slice D), or any new dialogs. It is a focused mechanical sweep.

## Project context

Slice A landed `_build_context_menu(self, index: QModelIndex) -> QMenu` on `ListDetailPanel` with a default-empty implementation. The base wires `customContextMenuRequested` to a slot that calls the factory and pops the menu, silently ignoring an empty menu. Slice A also wrote SES-008, DEC-032 through DEC-037, six references, PI-NNN, and bumped status to `0.9`.

Per DEC-036, right-click is a global UX principle: every entity row across every panel surfaces a context menu paralleling its existing button affordances. Half-coverage is incoherent, so this slice is a complete sweep across all eight existing panels (Decisions, Sessions, Risks, Planning Items, Topics, References, Charter, Status).

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `git config user.name` returns `Doug`; `git config user.email` returns `doug@dougbower.com`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice A landed:
   - `db-export/sessions.json` contains SES-008.
   - `db-export/decisions.json` contains DEC-032 through DEC-037.
   - `db-export/status.json` shows version_label `"0.9"` and phase `"v0.3 in build"`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` defines `_create_master_widget` and `_build_context_menu`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py` no longer contains `self._table = self._tree`.
6. Confirm the storage system is operational: `uv run crmbuilder-v2-api &`; `curl http://127.0.0.1:8765/health` returns 200.
7. Confirm the v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Expected ~474 tests passing (458 v0.2 + ~16 slice-A parity tests).

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` §4.2 (right-click context menus uniform across every entity row) — the contract for this slice.
3. `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` §4 Step B.
4. The slice-A landed code: `base/list_detail_panel.py` — confirm the `_build_context_menu` factory signature and the `_on_context_menu_requested` slot.
5. Each existing panel's source — to identify the existing toolbar / detail-pane button slots that the right-click menu should reuse:
   - `panels/decisions.py`
   - `panels/sessions.py`
   - `panels/risks.py`
   - `panels/planning_items.py`
   - `panels/topics.py`
   - `panels/references.py`
   - `panels/charter.py`
   - `panels/status.py`
6. v0.2 test patterns: `tests/crmbuilder_v2/ui/test_decisions_panel_writes.py`, `test_risks_panel_writes.py`, `test_topics_panel_writes.py` — for the `qtbot` panel-construction idiom and any context-menu testing helpers already present.

## Action map (per panel)

The action set surfaced by `_build_context_menu` per panel follows. Each menu's actions wire to the same handler slots that the panel's existing toolbar / detail-pane buttons already use — this slice introduces no new business logic.

### Decisions

When `index.isValid()` (right-click on a row):

- **Edit** — connects to the existing edit handler (the one that opens `DecisionEditDialog`).
- **Delete** — connects to the existing delete handler (the one that opens `DecisionDeleteDialog`). For deleted rows, the menu shows **Restore** instead, connecting to the existing restore handler from v0.2 slice F.
- **Show references** — selects the row and scrolls the detail pane to the `ReferencesSection`. If no scroll is needed (the section is already visible), the action just selects the row. Implementation note: this can be a single `select_record_by_identifier(...)` call combined with a `references_section.setFocus()` or `ensureVisible(...)` call on the section's widget.

When `index.isValid()` is False (right-click on whitespace):

- **New decision** — connects to the existing `New Decision` toolbar button handler.

### Sessions

When `index.isValid()`:

- **Go to references** — same shape as Decisions' "Show references": select the row and focus/scroll the detail pane's `ReferencesSection`.
- **Copy identifier** — copies the session's `identifier` (e.g., `SES-008`) to the clipboard via `QApplication.clipboard().setText(...)`.

When `index.isValid()` is False:

- (Empty — slice D adds `New session` to this branch.)

### Risks

When `index.isValid()`:

- **Edit**
- **Delete**

When `index.isValid()` is False:

- **New risk** — connects to existing `New Risk` toolbar button handler.

### Planning Items

When `index.isValid()`:

- **Edit**
- **Delete**

When `index.isValid()` is False:

- **New planning item** — connects to existing `New Planning Item` toolbar button handler.

### Topics

When `index.isValid()`:

- **Edit**
- **Delete**

When `index.isValid()` is False:

- **New topic** — connects to existing `New Topic` toolbar button handler.

### References

When `index.isValid()`:

- **Go to source** — uses the existing v0.1/v0.2 click-to-navigate path on the source side of the reference. Reads the reference's `source_type` and `source_id`, then triggers the same navigation that detail-pane reference clicks already trigger.
- **Go to target** — same, but for the target side.

When `index.isValid()` is False:

- (Empty — slice C adds `New reference` to this branch.)

(Slice C also adds `Delete reference` to the row-context branch above. Do not include `Delete reference` here in slice B.)

### Charter

When `index.isValid()` and the row is a non-current version:

- **Make Current** — connects to the existing v0.2 Make Current handler.
- **View payload** — opens a read-only modal showing the version's payload. If a `view_payload` handler doesn't already exist (it may not — v0.2's Make Current dialog and the version-history list are the existing surfaces), add a thin handler that opens a small modal with the JSON payload. The modal can be a `QDialog` containing a `QPlainTextEdit` with the formatted JSON, read-only, with a Close button. If implementation cost is non-trivial (more than ~30 lines), defer the action to slice E with a TODO comment in the menu code.

When `index.isValid()` and the row IS the current version:

- **View payload** only (no Make Current — already current).

When `index.isValid()` is False:

- **New version** — connects to the existing v0.2 `New Version` toolbar button handler.

### Status

Same as Charter, but for status versions.

## Step 1 — Per-panel `_build_context_menu` overrides

For each panel in the action map above, override `_build_context_menu` in the panel's class. The implementation pattern:

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)

    if not index.isValid():
        # Whitespace right-click
        new_action = menu.addAction("New decision")  # adapt label per panel
        new_action.triggered.connect(self._on_new_clicked)
        return menu

    # Row context
    edit_action = menu.addAction("Edit")
    edit_action.triggered.connect(self._on_edit_clicked)

    # Adapt per panel — see action map above
    delete_action = menu.addAction("Delete")
    delete_action.triggered.connect(self._on_delete_clicked)

    return menu
```

The handler slot names (`_on_edit_clicked`, `_on_delete_clicked`, etc.) may differ per panel — read the existing panel code to find the correct names. The principle is: action handlers are existing slots, not new ones.

### Special handling per panel

**Decisions — Restore vs. Delete branching:**

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        new_action = menu.addAction("New decision")
        new_action.triggered.connect(self._on_new_clicked)
        return menu

    edit_action = menu.addAction("Edit")
    edit_action.triggered.connect(self._on_edit_clicked)

    record = self._record_at_index(index)  # use the existing helper if present, or implement inline
    if record and record.get("status") == "Deleted":
        restore_action = menu.addAction("Restore")
        restore_action.triggered.connect(self._on_restore_clicked)
    else:
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self._on_delete_clicked)

    show_refs_action = menu.addAction("Show references")
    show_refs_action.triggered.connect(lambda: self._show_references_for(index))

    return menu
```

**References — Go to source / Go to target:**

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        return menu  # slice C adds the New action

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
    return menu
```

If `_navigate_to` doesn't exist on the panel, use the existing v0.2 navigation path (the same one the `ReferencesSection` widget triggers on click).

**Sessions — Copy identifier:**

```python
copy_id_action = menu.addAction("Copy identifier")
copy_id_action.triggered.connect(
    lambda: QApplication.clipboard().setText(record["identifier"])
)
```

**Charter / Status — Make Current branching by current state:**

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        new_version_action = menu.addAction("New version")
        new_version_action.triggered.connect(self._on_new_version_clicked)
        return menu

    record = self._record_at_index(index)
    if record and not record.get("is_current"):
        make_current_action = menu.addAction("Make Current")
        make_current_action.triggered.connect(
            lambda: self._on_make_current_clicked(record)
        )
    view_payload_action = menu.addAction("View payload")
    view_payload_action.triggered.connect(
        lambda: self._on_view_payload_clicked(record)
    )
    return menu
```

If `_on_view_payload_clicked` doesn't exist and implementing it would exceed ~30 lines (most likely it's a small modal with a `QPlainTextEdit`), implement it inline. If it's larger than expected, leave a `TODO(v2-ui-v0.3-E)` comment and skip the View payload action for this slice.

## Step 2 — Sweep test in `tests/crmbuilder_v2/ui/test_context_menus.py`

Create a new test file. For each panel, write a test that:

1. Instantiates the panel.
2. Constructs a known `QModelIndex` for a known row (or invalid index for the whitespace case).
3. Calls `panel._build_context_menu(index)`.
4. Asserts the returned `QMenu`'s action `text()` list matches the expected list.

Sample test shape:

```python
def test_decisions_context_menu_row_actions(qtbot, mock_client_with_decisions):
    panel = DecisionsPanel(client=mock_client_with_decisions)
    qtbot.addWidget(panel)
    # Refresh panel data so a row exists
    panel._on_refresh_clicked()
    qtbot.wait(100)

    index = panel._master_view.model().index(0, 0)
    menu = panel._build_context_menu(index)
    actions = [a.text() for a in menu.actions()]
    assert actions == ["Edit", "Delete", "Show references"]


def test_decisions_context_menu_whitespace_actions(qtbot, mock_client):
    panel = DecisionsPanel(client=mock_client)
    qtbot.addWidget(panel)
    invalid_index = QModelIndex()
    menu = panel._build_context_menu(invalid_index)
    actions = [a.text() for a in menu.actions()]
    assert actions == ["New decision"]
```

Cover all eight panels with both row-context and whitespace-context tests. For panels where the deleted-row branch matters (Decisions), include a separate test asserting `Restore` appears instead of `Delete` for a row whose `status == "Deleted"`.

For Charter and Status, include separate tests for current-version vs. non-current-version rows.

For References, the row-context test asserts only `["Go to source", "Go to target"]` in this slice (slice C extends the menu with `Delete reference`, and a new test in slice C will assert the extended set).

## Step 3 — Per-panel test additions

In each existing `test_*_panel_writes.py` test file, add a smoke test that right-click is wired to the factory:

```python
def test_decisions_panel_right_click_invokes_context_menu_factory(qtbot, mock_client):
    panel = DecisionsPanel(client=mock_client)
    qtbot.addWidget(panel)
    # Mock or spy on _build_context_menu to confirm it's called
    with patch.object(panel, "_build_context_menu", wraps=panel._build_context_menu) as spy:
        # Programmatically trigger the customContextMenuRequested signal
        view = panel._master_view
        view.customContextMenuRequested.emit(QPoint(10, 10))
        qtbot.wait(50)
        assert spy.called
```

(The exact mechanics of triggering `customContextMenuRequested` programmatically may need adjustment depending on Qt's event behavior in pytest-qt — see the v0.2 test patterns for the convention. If the cleanest test is to call `_on_context_menu_requested` directly with a `QPoint`, that's acceptable.)

This is a single smoke test per panel; the action-set assertions live in `test_context_menus.py`.

## Step 4 — Run tests

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: ~474 tests from slice A + ~30 new context-menu tests (8 panels × ~3 tests each on average). Total ~504 passing.

If any v0.2 test breaks: debug. The right-click overrides should not affect any non-right-click behavior.

## Step 5 — Commit, push, report

One commit:

```
v2: ui v0.3 — right-click context menus across existing panels
```

Push:

```
git pull --rebase origin main
git push origin main
```

## Acceptance gates

- [ ] Each existing panel (Decisions, Sessions, Risks, Planning Items, Topics, References, Charter, Status) overrides `_build_context_menu` with the action set documented in the action map.
- [ ] Right-click on a row produces the correct menu actions per panel.
- [ ] Right-click on whitespace produces creation actions where applicable, an empty menu otherwise.
- [ ] Right-click on a deleted Decision row surfaces `Restore` instead of `Delete`.
- [ ] Right-click on a current Charter/Status version row surfaces only `View payload` (no `Make Current`); non-current rows surface both.
- [ ] Each menu action reuses an existing handler slot — no new business logic introduced.
- [ ] `tests/crmbuilder_v2/ui/test_context_menus.py` exists and asserts action-set parity per panel.
- [ ] Each `test_*_panel_writes.py` file has a smoke test confirming right-click invokes the context-menu factory.
- [ ] Full v2 test suite passes (~504 tests).
- [ ] One commit pushed: `v2: ui v0.3 — right-click context menus across existing panels`.

## Out of slice

- Any references write actions (`New reference`, `Delete reference`). Those land in slice C.
- Any Sessions create action (`New session`). Lands in slice D.
- Any micro-visual styling of the menus. Slice E if at all.
- The `View payload` modal for Charter/Status, if implementation cost exceeds ~30 lines. Defer to slice E with a TODO.
- Right-click extensions on `ReferencesSection` rows on detail panes. Those land in slice C.

## Constraints

- Do not introduce new business logic in any context-menu action. Each action calls an existing slot or is a trivial inline operation (clipboard, navigation).
- Do not break any existing toolbar or detail-pane button behavior. The menu is additive.
- Do not modify any dialog. Slice C and slice D handle dialog work.
- Do not change the storage layer. UI-only slice.

## Reporting

After all five steps complete, report:

- Confirmation that all acceptance gates above are checked.
- The final test count (`uv run pytest tests/crmbuilder_v2/ -v` summary line).
- Any deviations or surprises with rationale.
- Any open items for slice C.

Slice C (References write surface) is the next slice. Its prompt is `CLAUDE-CODE-PROMPT-v2-ui-v0.3-C-references-write-surface.md`.
