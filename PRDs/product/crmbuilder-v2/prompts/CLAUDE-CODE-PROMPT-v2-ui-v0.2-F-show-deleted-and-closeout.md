# CLAUDE-CODE-PROMPT-v2-ui-v0.2-F-show-deleted-and-closeout

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2 (final slice)
**Slice:** F (6 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-E (charter and status replace flows)

## Purpose

Slice F closes v0.2. It packages three groups of changes:

1. **Show-deleted toggle on Decisions.** A checkbox in the Decisions panel toolbar that surfaces soft-deleted decisions (hidden by default per v0.1 slice H). When toggled on, deleted rows render with strikethrough text; the detail-pane Delete button becomes Restore on a deleted record (PATCHes status back to Active).

2. **Polish.** Friction items observed during slices B/C/D/E execution. About dialog version bump to reflect v0.2. README "User interface" section update.

3. **Closeout governance records.** SES-007 session record summarizing the v0.2 build, status update bumping to `"v0.2 complete"`.

After this slice, v0.2 is shipped: the v2 UI now offers full create/edit/delete for Decisions, Risks, Planning Items, Topics; versioned replace + Make Current for Charter and Status; reference rendering on every detail pane; Show-deleted on Decisions; calendar widget on date inputs; QTreeView master for Topics; HierarchicalEntityPicker reusable widget. Sessions write surface and References write surface remain deferred to v0.3.

## Project context

Slice E delivered the Charter/Status replace flows. Slices B/C/D delivered Risks, Planning Items, Topics CRUD. Slice A delivered the foundation. v0.2's design surface is now substantially complete; slice F's job is to add the small Show-deleted toggle, address any rough edges, and write closeout records.

The Show-deleted toggle requires:

- The UI client method `list_decisions` accepts an `include_deleted` parameter (probably already present from v0.1 slice H — verify).
- The `GET /decisions` endpoint accepts `?include_deleted=true` query parameter (probably already present via the access-layer parameter — verify).
- A `restore_decision(identifier)` client method that PATCHes status back to Active. v0.1 slice H established that `PATCH /decisions/{id}` with `{"status": "Active"}` is the soft-delete-restore path; verify and use it directly, or wrap as a convenience method on the client.

If any of these is missing at the storage level, the slice adds them. Mechanical work.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice E is on `main`.
6. Confirm the v2 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — re-read sections 4.7 (Show-deleted), 4.8 (calendar already done), 6 (acceptance criteria for final pass).
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — Step F in section 4.
4. v0.1 slice H code for the soft-delete pattern:
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` — `delete()` (soft-delete) and `list_all(include_deleted=...)`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py` — confirm `?include_deleted=true` is wired through.
5. Existing UI surface:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — `list_decisions`, error mapping, `update_decision`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py` — toolbar layout, button strip rendering.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py` — version display.
   - `crmbuilder-v2/README.md` — User interface section from v0.1 slice H.
6. **Tier 2 orientation**: current charter, current status, SES-006, DEC-026 (v0.2 frame including show-deleted carve-out), DEC-014 (every conversation produces a session record), DEC-025 (conversation_reference convention).

## Step 1 — Verify or add storage support for include_deleted and restore

### `list_decisions(include_deleted=True)` at the API

If `GET /decisions?include_deleted=true` is not already supported (it likely is from slice H), add the query parameter to the API's decisions list endpoint. The access-layer `list_all(include_deleted=...)` already exists from slice H; the API just needs to plumb the query parameter through.

Verify with:

```bash
curl 'http://127.0.0.1:8765/decisions?include_deleted=true' | jq '.data | length'
curl 'http://127.0.0.1:8765/decisions' | jq '.data | length'
```

The first should return all decisions including deleted; the second should return only Active/Superseded/Withdrawn (not Deleted).

### Restore path

`PATCH /decisions/{id}` with `{"status": "Active"}` is the established restore path from slice H. Verify with:

```bash
# Soft-delete:
curl -X DELETE http://127.0.0.1:8765/decisions/DEC-XXX
# Restore:
curl -X PATCH http://127.0.0.1:8765/decisions/DEC-XXX -d '{"status": "Active"}' -H 'Content-Type: application/json'
```

Confirm the second call flips the status back to Active and returns the updated record.

If either path doesn't work, add the missing piece. Mechanical work.

## Step 2 — Extend `StorageClient` for show-deleted and restore

```python
def list_decisions(self, *, include_deleted: bool = False) -> list[dict]:
    """GET /decisions. Returns the list of decisions.

    With include_deleted=True, soft-deleted decisions are also
    returned. Without it, the API filters Deleted out (default
    behavior from v0.1 slice H).
    """
    params = {}
    if include_deleted:
        params["include_deleted"] = "true"
    return self._request("GET", "/decisions", params=params)["data"]


def restore_decision(self, identifier: str) -> dict:
    """Restore a soft-deleted decision by PATCHing status to Active.

    Convenience method around update_decision(); the underlying API
    call is identical, but this name reflects the intent.
    """
    return self.update_decision(identifier, {"status": "Active"})
```

If `list_decisions` already accepts `include_deleted` from v0.1, the existing method is preserved; only the parameter behavior is verified.

### Tests

Extend `tests/crmbuilder_v2/ui/test_client.py`:

- `list_decisions(include_deleted=True)` includes the query parameter in the request.
- `list_decisions(include_deleted=False)` (and the default) does not include the parameter.
- `restore_decision("DEC-XXX")` calls `PATCH /decisions/DEC-XXX` with `{"status": "Active"}`.

## Step 3 — Show-deleted toggle on the Decisions panel

### Toolbar

Add a `QCheckBox("Show deleted")` to the decisions panel toolbar action layout, between the Refresh button and the New Decision button:

```python
self._show_deleted_check = QCheckBox("Show deleted")
self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
self._action_layout.addWidget(self._show_deleted_check)


def _on_show_deleted_toggled(self, checked: bool) -> None:
    self._include_deleted = checked
    self.refresh()
```

The panel's `refresh` method passes `include_deleted=self._include_deleted` to `client.list_decisions`. Default `self._include_deleted = False` set in `__init__`.

### Strikethrough rendering for deleted rows

The Decisions panel's table model (likely a QStandardItemModel populated in `_populate_model`) renders each row from a record dict. Apply strikethrough to deleted rows:

```python
def _populate_model(self, records: list[dict]) -> None:
    self._model.clear()
    self._model.setHorizontalHeaderLabels([...])
    for record in records:
        items = [QStandardItem(record.get(c, "")) for c in COLUMNS]
        if record.get("status") == "Deleted":
            font = items[0].font()
            font.setStrikeOut(True)
            for item in items:
                item.setFont(font)
        for item in items:
            item.setEditable(False)
        self._model.appendRow(items)
```

Strikethrough on Identifier and Title columns (or all columns — implementer's call between minimal-strikethrough and full-row-strikethrough). The Status column already shows `Deleted` in plain text; that's enough to make the deletion state explicit.

### Restore button on the detail pane for deleted records

In the detail-pane button strip rendered by `render_detail`, branch on the record's status:

```python
if record.get("status") == "Deleted":
    restore_btn = QPushButton("Restore")
    restore_btn.clicked.connect(lambda: self._on_restore_clicked(record))
    button_strip.addWidget(restore_btn)
    edit_btn = QPushButton("Edit")
    edit_btn.clicked.connect(lambda: self._on_edit_clicked(record))
    button_strip.addWidget(edit_btn)
    # No Delete button — already deleted.
else:
    edit_btn = QPushButton("Edit")
    edit_btn.clicked.connect(lambda: self._on_edit_clicked(record))
    button_strip.addWidget(edit_btn)
    delete_btn = QPushButton("Delete")
    delete_btn.clicked.connect(lambda: self._on_delete_clicked(record))
    button_strip.addWidget(delete_btn)


def _on_restore_clicked(self, record: dict) -> None:
    confirm = QMessageBox.question(
        self,
        "Restore decision",
        f"Restore {record['identifier']} — {record['title']}? "
        "Its status will return to Active.",
    )
    if confirm != QMessageBox.Yes:
        return
    try:
        self._client.restore_decision(record["identifier"])
    except StorageClientError as exc:
        ErrorDialog(
            "Could not restore",
            "An error occurred while restoring the decision.",
            detail=str(exc),
            parent=self,
        ).exec()
        return
    self.refresh()
```

(Run the restore call through a worker per v0.2 threading rules; sketch above is synchronous for clarity.)

### Test

`tests/crmbuilder_v2/ui/test_show_deleted_toggle.py` (new):

- Show-deleted checkbox is present in the toolbar.
- Default state: unchecked. `refresh` calls `list_decisions` without `include_deleted=True`.
- Toggling on: `refresh` calls `list_decisions(include_deleted=True)`.
- A row with `status="Deleted"` renders with strikethrough.
- A non-deleted row does not render with strikethrough.
- Detail pane on a deleted record shows Restore and Edit buttons (no Delete).
- Detail pane on an active record shows Edit and Delete buttons (no Restore).
- Clicking Restore opens the confirmation; confirming calls `restore_decision`.

## Step 4 — About dialog version bump

The `AboutDialog` from v0.1 slice H reads version from `importlib.metadata`. Bump `pyproject.toml`:

```toml
[project]
name = "crmbuilder-v2"
version = "0.2.0"  # was "0.1.x"
```

Verify by launching the UI and opening Help → About; the displayed version should be `0.2.0`.

If the AboutDialog needs any code changes (e.g., to display a v0.2-specific note), make them. Otherwise, the version bump is sufficient.

## Step 5 — README addition

Update `crmbuilder-v2/README.md` "User interface" section (added in v0.1 slice H). Add a paragraph describing v0.2's expanded write surface:

```markdown
### v0.2 (current)

In addition to the v0.1 surface, v0.2 adds full create/edit/delete
operations for Risks, Planning Items, and Topics; versioned-replace
flows with Make Current affordance for Charter and Status; reference
rendering on every detail pane; a calendar widget on date inputs; a
"Show deleted" toggle on the Decisions panel; and a QTreeView master
panel for Topics with a reusable hierarchical picker widget for
parent_topic.

Sessions and References write surfaces remain deferred to v0.3.
The full styling design pass per DEC-024 is also deferred to v0.3.
```

Or restructure the section as the maintainer judges best — the goal is to reflect v0.2's current capabilities.

## Step 6 — Friction polish

Items observed during slices B through E that haven't been called out yet, plus anything noticed during slice F execution. Non-exhaustive list; Claude Code uses judgment.

Suggested items:

1. **Tab order in new dialogs.** Verify Tab moves through fields in render order in Risks, Planning Items, Topics, Charter, Status dialogs. If not, set explicitly via `QWidget.setTabOrder()`.
2. **Close-on-Escape.** All new dialogs should close on Escape. QDialog default; verify.
3. **Window titles consistency.** "New Risk", "Edit RSK-001", "New Charter Version", etc.
4. **Status label on panel toolbars.** Verify the existing pattern from v0.1 ("Loading…" → "{n} records") works for the new write surfaces (a successful create should update the count).
5. **Log noise.** Verify `~/.crmbuilder-v2/ui.log` doesn't fill with WARNINGs or ERRORs for routine operations.
6. **References fetch failure handling.** If `ReferencesSection`'s fetch fails (network blip, API restart), the section should render an error placeholder rather than the loading state forever.
7. **Tree picker scroll-to-current.** When opening the Topics parent picker on Edit, the picker should scroll to the current parent (if any) so the user sees their starting point. The slice A widget supports this via the `current_id` parameter; verify it's passed through correctly from the EntityCrudDialog tree_picker handling.

Where a fix introduces a behavior change worth verifying, add a test. Where it's a cosmetic tweak, skip.

## Step 7 — Closeout governance records

After all functional changes are committed, write the closing session and status update.

### SES-007 — UI v0.2 build

Via `POST /sessions`. Per DEC-014 every v2 conversation produces a session record; per DEC-025 the conversation_reference is descriptive text and topics_covered captures the conversation's scope.

```json
{
  "identifier": "SES-007",
  "title": "UI v0.2 build",
  "session_date": "<today, MM-DD-YY format>",
  "status": "Complete",
  "conversation_reference": "Six Claude Code execution sessions per the CLAUDE-CODE-PROMPT-v2-ui-v0.2-A through F prompt series. No transcripts preserved per DEC-025.",
  "topics_covered": "Six-prompt execution of the UI v0.2 build per ui-v0.2-implementation-plan.md: foundation refactor (A), risks CRUD (B), planning items CRUD (C), topics CRUD with QTreeView and HierarchicalEntityPicker (D), charter and status replace flows + sessions references section (E), show-deleted toggle and closeout (F). Foundation refactor extracted EntityCrudDialog and EntityCrudDeleteDialog base classes plus a new widgets/ subpackage with DateField, ReferencesSection, and HierarchicalEntityPicker; v0.1's decisions dialogs migrated to use the base. Each subsequent slice instantiated the base for its entity, added the entity's panel-side write integration, and dropped ReferencesSection on the detail pane. Charter/Status got the parallel VersionedReplaceDialog with raw JSON editor and Make Current affordance. Slice F closed with the Show-deleted toggle plus polish plus this record.",
  "summary": "UI v0.2 shipped: full create/edit/delete for Risks, Planning Items, and Topics; versioned replace with Make Current for Charter and Status; reference rendering on every detail pane via the shared ReferencesSection widget; calendar widget on date inputs (DateField); QTreeView master panel for Topics with reusable HierarchicalEntityPicker; Show-deleted toggle and Restore affordance on the Decisions panel. v0.1's 264 tests continue to pass after the slice A refactor. Sessions and References write surfaces remain deferred to v0.3 per DEC-027.",
  "artifacts_produced": "Six prompts (CLAUDE-CODE-PROMPT-v2-ui-v0.2-A through F) under PRDs/product/crmbuilder-v2/prompts/. Source under crmbuilder-v2/src/crmbuilder_v2/ui/widgets/, base/crud_dialog.py, base/versioned_replace_dialog.py, plus per-entity dialogs and panel modifications. Test files under tests/crmbuilder_v2/ui/widgets/ and per-entity test_*_dialogs.py / test_*_panel_writes.py. Storage-system additions where required: list_decisions include_deleted query param plumbing, make-current endpoints for charter and status, and POST/PATCH/DELETE routers for risks/planning_items/topics where they didn't already exist.",
  "in_flight_at_end": "v0.3 backlog: References write surface as its own focused slice (relationship vocabulary picker, source/target picker UX, edge-deletion semantics); Sessions write surface only if DEC-013/DEC-014 are revised to permit non-Claude session records; full styling design pass per DEC-024; reference filtering by relationship type if reference volume warrants it; diff-with-current view for the JSON payload editor if friction surfaces; methodology entity panels post-schema-design; global search across entities; keyboard shortcuts beyond Qt defaults; export visible panel to CSV/JSON; bulk operations."
}
```

### Status update

Via `PUT /status`. Build on the prior status (v0.7 from slice A) and update phase, sub_step, version_label:

```json
{
  "phase": "v0.2 complete",
  "sub_step": "All six v0.2 slices shipped (A foundation refactor, B risks CRUD, C planning items CRUD, D topics CRUD + QTreeView + HierarchicalEntityPicker, E charter and status replace flows + sessions references, F show-deleted toggle + polish + closeout). v2 stack now offers full CRUD for the four governance entity types with daily-use needs (Decisions, Risks, Planning Items, Topics), versioned replace + history for Charter and Status, and uniform reference rendering. Next priorities are v0.3 backlog (References write surface, full styling pass, possibly Sessions write surface pending DEC-013/DEC-014 revisit) and resuming planning dimensions #6/#7/#8.",
  "active_work": "None — v0.2 shipped. Awaiting v0.3 planning conversation.",
  "live_inventory.in_database": "31 decisions (DEC-001 through DEC-031), 7 sessions (SES-001 through SES-007), charter unchanged, 8+ status versions (this is the new current), references count grew correspondingly.",
  ...
  "version_label": "0.8"
}
```

Read `db-export/status.json` to see the current shape and preserve fields not explicitly bumped above.

### Verify

After the writes:
- `db-export/sessions.json` includes SES-007.
- `db-export/status.json` reflects the new version with phase `"v0.2 complete"`.
- `db-export/change_log.json` has corresponding entries.

## Step 8 — Verify and commit

Run the full test suite:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: all v0.1 tests + all v0.2 slice A through F tests. Estimated 360+ passing.

### Final manual acceptance pass

Run through PRD Section 6's 15 acceptance criteria one last time. Note which have been verified during prior slices and which require explicit re-verification in slice F (most are stable from prior slices; AC#11 — Show-deleted toggle and Restore — is new in this slice and must be verified).

### Commit strategy: three commits

**Commit 1: show-deleted toggle**

```
v2: ui show-deleted toggle on decisions panel + restore affordance

Closes the v0.1 slice H deferred item: a "Show deleted" checkbox on
the Decisions panel toolbar that surfaces soft-deleted decisions
(hidden by default per slice H's soft-delete model). Default off;
toggling on calls list_decisions(include_deleted=True) and renders
deleted rows with strikethrough. Detail pane on a deleted record
shows Restore + Edit buttons (no Delete); Restore PATCHes status
back to Active.

StorageClient gains restore_decision() as a convenience around
update_decision(status='Active'). list_decisions() formalizes the
include_deleted parameter on the client method (and verifies the
?include_deleted=true query parameter is plumbed through the API).
```

**Commit 2: polish**

```
v2: ui v0.2 polish — about dialog version bump, README, friction items

About dialog displays version 0.2.0. README "User interface" section
updated to reflect v0.2's expanded write surface. Friction items
addressed across the per-entity dialogs and panels:

- Tab order verified in new dialogs.
- Window titles consistent.
- Tree picker scroll-to-current verified for the Topics edit flow.
- ReferencesSection error-state rendering improved.
- Log noise cleanup for routine operations.

pyproject.toml: package version bumped to 0.2.0.
```

**Commit 3: closeout**

```
v2: ui v0.2 closeout — append SES-007, update status to v0.2 complete

Closes the v2-ui-v0.2 workstream. Captures the six-prompt build via
SES-007 (UI v0.2 build) and bumps the status to phase='v0.2 complete'.

The v0.2 backlog deferred to v0.3 is captured in SES-007's
in_flight_at_end field per DEC-014.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. Show-deleted toggle is present on the Decisions panel toolbar; default off.
2. Toggling on reveals deleted rows with strikethrough; toggling off hides them.
3. Detail pane on a deleted decision shows Restore and Edit buttons (no Delete).
4. Restore button confirms and PATCHes the status back to Active; the row reappears in the default (Show-deleted-off) view. (PRD AC#11.)
5. About dialog displays version `0.2.0`.
6. README "User interface" section reflects v0.2.
7. Full v2 test suite passes.
8. SES-007 and status v0.8 update are present in `db-export/sessions.json` and `db-export/status.json`.
9. Three commits on `origin/main`: show-deleted toggle, polish, closeout — in that order.
10. PRD Section 6's 15 acceptance criteria all verified end-to-end.

## Out of slice

The following are explicitly NOT in scope for slice F:

- Any new write surface beyond Show-deleted/Restore on Decisions. References, Sessions, methodology entities all remain deferred.
- Full styling design pass — deferred again to v0.3 per DEC-024.
- Diff-with-current view for the JSON editor.
- Bulk operations.

## Constraints

- **No new external dependencies.**
- **Storage additions only if needed** (verify include_deleted query param works; verify restore via PATCH works). If both already work from slice H, no storage additions are needed.
- **Do not introduce new architectural patterns.** Polish is refinement, not redesign.
- **The v0.1 + v0.2 acceptance criteria must all hold** at the end of this slice.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the ten gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum: Show-deleted toggle on/off; Restore on a deleted record; About dialog version display.
- **Final state of the build** — confirmation that v0.2 is shipped, with a brief inventory of what was delivered across all six slices: foundation framework + widgets, three CRUD entities, two versioned-replace entities, references-everywhere, show-deleted toggle, calendar widget.
- **Deviations from this prompt** — anything that diverged.
- **Open questions or surprises** — anything that came up that should be flagged for v0.3 planning.
- **Closeout records** — confirmation that SES-007 and status v0.8 wrote successfully and appear in `db-export/`.
