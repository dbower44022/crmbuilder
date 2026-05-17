# CLAUDE-CODE-PROMPT-v2-ui-v0.5-C-engagement-management-panel

**Last Updated:** 05-16-26 21:00
**Series:** v2-ui-v0.5
**Slice:** C (3 of 5)
**Status:** Ready to execute (after slice B passes)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Companion schema:** `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md`
**Predecessor slice:** v2-ui-v0.5-B (engagement schema + REST API)

## Purpose

This is the third of five slices that build CRMBuilder v2 UI v0.5. This prompt builds slice **C — Engagement Management Panel**.

Slice C exposes the slice-B-shipped engagement REST API through a `ListDetailPanel` subclass. Four categories of work:

1. **Engagement management panel.** `ui/panels/engagement_panel.py` — `ListDetailPanel` subclass registered as the single entry in the Engagements sidebar group (the empty group was introduced in slice A). Master pane with five columns; detail pane with form fields per `engagement.md` §3.6.3; right-click context menu; empty-state rendering.

2. **CRUD dialogs.** `ui/dialogs/engagement_crud.py` — Create and Edit dialogs as `EntityCrudDialog` subclasses; Edit dialog has `engagement_code` read-only (rename is v0.6+ candidate per PRD Out of Scope).

3. **Delete dialog with forbid-active-engagement behavior.** `ui/dialogs/engagement_delete.py` — `EntityCrudDeleteDialog` subclass implementing PRD §5.6's forbid-active-delete (with the only-engagement edge case).

4. **Refresh-service registration.** The panel subscribes to the slice-A-registered `db-export/meta/engagements.json` file-watch signal AND to the `active_engagement_changed` Qt signal from `ActiveEngagementContext`.

After this slice, the engagement panel renders. Users can navigate to it via the new "Engagements" sidebar entry; they can see the existing CRMBUILDER row (and any others created via direct API in slice B); they can create new engagement records via the dialog (creates a meta DB row only — the per-engagement DB file is not created and activation is not initiated, both of which land in slice D). Edit, soft-delete, and restore operations work end-to-end. The forbid-active-engagement check is enforced.

This slice does NOT include the single-gesture creation+activation flow (slice D), the top-strip widget or picker (slice D), the activation worker (slice D), the version bump (slice E), or the README release note (slice E). The "Switch engagement" button in the delete dialog's forbid-active state is wired as inert in slice C — slice D rewires it to open the picker.

## Project context

Slice A laid the foundation infrastructure including the empty Engagements sidebar group container. Slice B built the engagement REST API. Slice C wires the UI to the API.

The engagement panel inherits the v0.4 `ListDetailPanel` pattern unchanged at the base level — the slice's UI work is composition over the existing framework. Visual treatment inherits from `styling-design-pass.md`'s shipped tokens (light theme; cool-blue accent #1F5FBF; Inter Variable body; left-accent-bar selected state) per the SES-027 styling Conversation 1 closeout. If the styling workstream's tokens module has not shipped by slice C execution time, slice C ships with literal token values inlined as constants and a TODO comment for retrofit when the tokens module lands.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity is set.
4. Pull latest from origin.
5. **Verify slice B is in place.** `crmbuilder-v2/src/crmbuilder_v2/access/engagement.py` exists. `crmbuilder-v2/src/crmbuilder_v2/api/routers/engagements.py` exists with the eight standard endpoints. `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` has the eight engagement methods. The slice-B tests pass.
6. Confirm API operational: `curl -sf http://127.0.0.1:8765/engagements | python3 -m json.tool` returns the envelope-wrapped engagement list including CRMBUILDER.
7. Confirm slice B's test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — API envelope contract.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §5.1, §5.6, §6, §9 (styling coordination).
3. `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md` Step C.
4. `PRDs/product/crmbuilder-v2/methodology-schema-specs/engagement.md` §3.6 (UI shape detail; the engagement panel's deliberate-deviation justification).
5. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (committed at SES-027 by the parallel styling workstream) — design tokens to consume. Note any token values needed for the master-pane column types, the active-engagement marker, the status-aware coloring.
6. v0.4 panel precedent (read carefully to mirror):
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/domain_panel.py` — `ListDetailPanel` subclass pattern
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/domain_crud.py` — `EntityCrudDialog` subclass pattern
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/domain_delete.py` — `EntityCrudDeleteDialog` subclass pattern
7. Slice A's deliverables:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py` — confirm the `active_engagement_changed` signal signature
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py` — confirm the Engagements group container; slice C populates the single entry
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — confirm the file-watch entry for `db-export/meta/engagements.json`; slice C registers the panel as subscriber

## Step 1 — Engagement management panel

Create `crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagement_panel.py`. The panel is a `ListDetailPanel` subclass registered as the single entry in the Engagements sidebar group from slice A.

### 1.1 Master pane

Five columns per PRD §5.1:

| Column | Type | Width | Font |
|--------|------|-------|------|
| Identifier | text | 80px | mono, small |
| Code | text | 100px | mono, small |
| Name | text | flexible | body |
| Status | text | 80px | body, status-aware color |
| Last Opened | text | 120px | body, relative date |

Status-aware coloring per PRD §5.1: `active` in normal body text color; `paused` in `color.warning.default` or equivalent neutral (use the styling tokens); `archived` in `color.neutral.500`.

Last Opened formatting per PRD §5.1's working assumption — "N hours/days ago" / "—" when null. Use a helper function `format_relative_date(dt: datetime | None) -> str`. Cases:
- null → `"—"`
- within last 60 minutes → `"N minutes ago"`
- within last 24 hours → `"N hours ago"`
- within last 30 days → `"N days ago"`
- older → ISO date `"YYYY-MM-DD"` (this resolves PRD Open Question 3's "common alternative")

Default sort: Last Opened descending (most-recent first). Soft-deleted records sort to the bottom regardless of last_opened_at value. The columns are sortable by clicking the header (use the existing `ListDetailPanel` sort mechanism).

### 1.2 Active-engagement marker

The currently-active engagement is marked with two visual treatments:

1. Left accent bar on the row (consume `color.accent.default` from styling tokens; mirror the styling design pass's selected-state vocabulary).
2. A Lucide `check` icon (14px, `color.accent.default`) prepended to the Identifier column's text.

Active-engagement comparison: against `ActiveEngagementContext.engagement_identifier()`.

### 1.3 Soft-deleted row treatment

Soft-deleted rows render in `color.neutral.500` text plus a Lucide `trash-2` icon (14px, `color.neutral.500`) prepended to the Identifier column. Rows appear only when `?include_deleted=true` is the active filter.

The filter toggle is a checkbox above the master pane labeled "Show soft-deleted" — default unchecked. When checked, the panel re-fetches via `client.list_engagements(include_deleted=True)`.

### 1.4 Right-click context menu

Standard menu with four items:
- **New** — opens the Create dialog (`engagement_crud.EngagementCreateDialog`)
- **Edit** — opens the Edit dialog (`engagement_crud.EngagementEditDialog`) prefilled with the selected row's data
- **Delete** — opens the Delete dialog (`engagement_delete.EngagementDeleteDialog`) prefilled
- **Restore** — appears only when a soft-deleted row is right-clicked; calls `client.restore_engagement()` directly without a confirmation dialog (mirrors v0.4 entity panels' restore pattern)

The menu does NOT include "Activate" — the picker (slice D) is the switching gesture per PRD §5.2.

### 1.5 Detail pane

Form per `engagement.md` §3.6.3 and PRD §5.1:

| Field | Type | Editable | Notes |
|-------|------|----------|-------|
| Identifier | text | no | mono font |
| Code | text | only on Create | mono; regex constraint hint visible |
| Name | text | yes | |
| Purpose | multi-line text | yes | 80px minimum height |
| Status | combo | yes | three values; default `active` |
| Export dir | text + browse button | yes | placeholder + tooltip per PRD §5.1 |
| Created at | datetime | no | relative date |
| Updated at | datetime | no | relative date |
| Deleted at | datetime | no | visible only when soft-deleted |

The export-dir directory-browser button uses `QFileDialog.getExistingDirectory()`. The selected path replaces the text field's value. The placeholder text reads "Optional — leave blank to disable auto-export." The tooltip reads "Where this engagement's JSON snapshots will be written. Recommend a path inside the client repo so exports travel with the engagement documents."

The detail pane is read-only when no row is selected; it activates on row click. Edits in the detail pane are NOT auto-saved — the user explicitly invokes the Edit dialog for changes. The detail pane is a viewer; the dialog is the editor.

**No References section.** Engagement entity has no relationships in v0.5 per `engagement.md` §3.8. The references section that other entity panels include is absent here.

### 1.6 Empty state

When the panel renders with no engagements (fresh install before migration, or hypothetically after soft-deleting every engagement — though §5.6 prevents that final state), the master pane shows a centered message:

```
No engagements yet

Create your first engagement to begin

[Create Engagement]
```

The "Create Engagement" button opens `EngagementCreateDialog` (the slice C dialog, not the slice D `NewEngagementDialog` — the difference is that slice C's dialog creates a meta DB row only; slice D's extension creates the file and activates).

## Step 2 — Engagement CRUD dialogs

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_crud.py` with two classes:

### 2.1 `EngagementCreateDialog`

`EntityCrudDialog` subclass for creating an engagement. Fields per PRD §5.1's master-pane / detail-pane requirements:

- `engagement_code` (with placeholder constraint hint visible: "2-10 characters, uppercase letters and digits, must start with a letter")
- `engagement_name`
- `engagement_purpose` (multi-line, 80px min)
- `engagement_status` (combo with three values; default `active`)
- `engagement_export_dir` (with directory-browser button; placeholder + tooltip per Step 1.5)

The dialog inherits validation-error display from `EntityCrudDialog` (inline-on-field). On Submit, calls `client.create_engagement(...)`. On success, closes the dialog and refreshes the panel via the existing `panel.refresh()` hook. On failure, displays validation errors inline and stays open.

Note: slice C's `EngagementCreateDialog` creates the meta DB row only — it does NOT create the per-engagement DB file and does NOT initiate activation. Both are slice D's `NewEngagementDialog` extension. In slice C, after a successful POST, the engagement record exists in the meta DB but no DB file exists at `engagements/{code}.db`. This is a working-but-incomplete state in slice C; users who try to switch to such an engagement in slice D will get a reachability-check failure, which is acceptable interim behavior. (The slice C dialog's docstring notes this.)

### 2.2 `EngagementEditDialog`

`EntityCrudDialog` subclass for editing an existing engagement. Pre-fills all fields from the selected row. Differences from Create:

- `engagement_identifier` shown read-only at the top of the form.
- `engagement_code` shown read-only (mirrors PRD §2 Out of Scope: rename is v0.6+ candidate; the dialog disables the field with a tooltip "Engagement code cannot be changed after creation.").
- On Submit, calls `client.patch_engagement(identifier, ...)` with only the changed fields (compare against pre-fill values).

## Step 3 — Engagement delete dialog

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_delete.py`:

`EngagementDeleteDialog` is an `EntityCrudDeleteDialog` subclass implementing the forbid-active-engagement behavior per PRD §5.6.

### 3.1 Behavior selector at dialog open

At dialog open, the dialog compares the target row's `engagement_identifier` against `ActiveEngagementContext.engagement_identifier()`. Two cases:

**Case A: target is NOT the active engagement.**

Standard `EntityCrudDeleteDialog` behavior: edge-text confirmation field; Delete button; on confirmation, calls `client.delete_engagement(identifier)`; on success refreshes panel.

**Case B: target IS the active engagement.**

The edge-text confirmation field is replaced with a static message:

```
<engagement_name> is currently active. Switch to a different engagement
first, then soft-delete this one.
```

The Delete button is replaced with a "Switch engagement" button.

**Last-engagement edge case (Case B sub-case): target is the active engagement AND there are no other engagements on the install.** Check this by calling `client.list_engagements()` and counting non-deleted records. If count is 1 (only the active engagement exists), the message changes to:

```
<engagement_name> is the only engagement on this install. Create
another engagement before soft-deleting this one.
```

The button label changes to "Create engagement".

### 3.2 Slice C button-action wiring

In slice C, the buttons are wired but mostly inert:

- "Switch engagement" button: wired to a placeholder that prints `"[TODO slice D] open picker"` to stdout. Slice D rewires to open the picker dropdown.
- "Create engagement" button: opens the slice-C `EngagementCreateDialog` directly. Slice D rewires to open `NewEngagementDialog` (the single-gesture variant).

The TODO comments are explicit so slice D's prompt can locate and update them.

## Step 4 — Refresh-service registration

In `engagement_panel.py`'s constructor (or wherever the v0.4 panel pattern registers signal subscriptions):

```python
# File-watch refresh on db-export/meta/engagements.json
refresh_service.register_subscriber(
    file_path="PRDs/product/crmbuilder-v2/db-export/meta/engagements.json",
    callback=self.refresh,
)

# Active-engagement signal refresh (to update the active-engagement marker)
active_engagement_context.active_engagement_changed.connect(self.refresh)
```

Both subscriptions are independent: the file-watch fires on engagement record changes (create/update/patch/delete/restore via the API); the signal fires on engagement switching (slice D). Both call the same `refresh()` method.

## Step 5 — Sidebar entry registration

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py` to populate the Engagements group's single entry. The entry is labeled "Engagements" and opens the engagement management panel.

The slice-A sidebar work introduced the empty Engagements group; slice C populates the entry. The pattern mirrors v0.4's slice-B through slice-E filling the Methodology group.

## Step 6 — Tests

### 6.1 `tests/crmbuilder_v2/ui/test_engagement_panel.py`

Tests using `qtbot` and `qapp` fixtures:

- Panel renders with the expected five columns.
- Default sort is Last Opened descending; clicking column headers re-sorts.
- Active engagement displays the left accent bar and check icon (verify by querying widget structure or rendered properties).
- Soft-deleted rows render in muted color with trash-2 icon when filter is on; hidden when filter is off.
- Empty-state renders correctly when no engagements present.
- "Create Engagement" empty-state button opens `EngagementCreateDialog`.
- Right-click menu shows the four standard items; "Restore" appears only on soft-deleted rows.
- File-watch refresh fires when `db-export/meta/engagements.json` changes.
- Signal-driven refresh fires when `active_engagement_changed` emits.

### 6.2 `tests/crmbuilder_v2/ui/test_engagement_crud_dialogs.py`

Tests covering the Create/Edit/Delete dialogs:

- `EngagementCreateDialog`: opens with empty form; submits with valid input; displays inline validation errors for each rule (lowercase code, too-short code, missing name, etc.); on success closes and refreshes panel.
- `EngagementEditDialog`: pre-fills fields from selected row; `engagement_code` is read-only with tooltip; submits PATCH with only changed fields.
- `EngagementDeleteDialog` Case A (non-active target): standard confirmation flow.
- `EngagementDeleteDialog` Case B (active target, multi-engagement install): message reads "Switch to a different engagement first"; button labeled "Switch engagement"; clicking the button hits the slice-C inert placeholder.
- `EngagementDeleteDialog` Case B sub-case (active target, only engagement): message reads "Create another engagement first"; button labeled "Create engagement"; clicking opens the Create dialog.

## Acceptance verification

Before committing:

1. **Slice C tests pass.** `uv run pytest tests/crmbuilder_v2/ui/test_engagement_panel.py tests/crmbuilder_v2/ui/test_engagement_crud_dialogs.py -v`.
2. **Full v0.5 suite passes.** `uv run pytest tests/crmbuilder_v2/ -v`.
3. **Manual smoke: panel renders.** Open the desktop. Navigate to the new Engagements sidebar entry. Confirm the panel renders with the CRMBUILDER row, default-sorted by Last Opened. Confirm the active-engagement marker is on CRMBUILDER (left accent bar + check icon).
4. **Manual smoke: edit CRMBUILDER.** Right-click CRMBUILDER → Edit. Change purpose to a new value. Submit. Confirm the panel refreshes and the new purpose appears. Confirm the JSON snapshot regenerated (check `db-export/meta/engagements.json` timestamp).
5. **Manual smoke: create new engagement (slice C variant).** Right-click → New. Submit a valid form with code "TEST", name "Test Engagement", purpose "Verification only". Confirm the engagement appears in the panel. Confirm no file exists at `crmbuilder-v2/data/engagements/TEST.db` (slice C creates the meta DB row only). Clean up: right-click TEST → Delete; complete the standard confirmation flow.
6. **Manual smoke: forbid-active delete.** Right-click CRMBUILDER → Delete. Confirm the dialog shows the forbid-active message and the "Switch engagement" button (inert in slice C — clicking prints the TODO message). Confirm Delete is NOT executable in this state.
7. **Manual smoke: forbid-active-and-only delete.** Soft-delete TEST (created in step 5) to leave CRMBUILDER as the only engagement. Right-click CRMBUILDER → Delete. Confirm the dialog shows the last-engagement message and the "Create engagement" button. Clicking "Create engagement" opens the slice-C Create dialog.

If any step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagement_panel.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/sidebar.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_crud.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_delete.py \
        tests/crmbuilder_v2/ui/test_engagement_panel.py \
        tests/crmbuilder_v2/ui/test_engagement_crud_dialogs.py
git commit -m "v2: v0.5 slice C — engagement management panel UI (master/detail panel, CRUD dialogs, forbid-active-delete with last-engagement edge case)"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT implement the top-strip widget or picker dropdown (slice D).
- Do NOT implement the single-gesture creation+activation flow (slice D). The slice C Create dialog creates the meta DB row only.
- Do NOT implement the activation worker or any kill-relaunch dance (slice D).
- Do NOT modify the slice B REST API or access-layer methods. Slice C consumes them as-is.
- Do NOT bump `__version__` (slice E).
- Do NOT modify any v0.4 panel behavior. The four methodology entity panels (Domains, Entities, Processes, CRM Candidates) and the governance panels (Sessions, Decisions, etc.) are unchanged.
- Do NOT remove the slice-C inert TODO placeholders in the delete dialog's forbid-active state — they are the wiring point for slice D.
- Do NOT write any session, decision, or planning records (those land at v0.5 build closeout).

---

*End of prompt.*
