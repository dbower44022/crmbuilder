# CLAUDE-CODE-PROMPT-v2-ui-v0.5-D-engagement-switching

**Last Updated:** 05-16-26 21:00
**Series:** v2-ui-v0.5
**Slice:** D (4 of 5)
**Status:** Ready to execute (after slice C passes)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md`
**Companion architecture:** `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md`
**Predecessor slice:** v2-ui-v0.5-C (engagement management panel)

## Purpose

This is the fourth of five slices that build CRMBuilder v2 UI v0.5. This prompt builds slice **D — Engagement Switching, Top-Strip, Picker, and Single-Gesture Creation+Activation**.

Slice D is the highest-density UI slice in v0.5. Five categories of work:

1. **Top-strip widget** at the top of the sidebar container. Always visible. Shows the active engagement's name with code in parentheses; clicking opens the picker.

2. **Picker dropdown.** Live engagements ordered by `engagement_last_opened_at` descending; paused and archived rendered muted and sorted to the bottom; active marked with a check icon; footer "Manage engagements..." item.

3. **Activation worker** — `QThread` implementing the 12-step activation sequence per `multi-engagement-architecture.md` §4 with the PRD §3 question-6 amendment (`engagement_last_opened_at` PATCH deferred until after new API subprocess is up).

4. **Activation overlay.** Centered widget binding to the activation worker's progress signals; converts to error state with retry/stay affordances on failure.

5. **Single-gesture creation+activation flow.** `NewEngagementDialog` extending slice-C's `EngagementCreateDialog` with three sequential operations: POST `/engagements` → create per-engagement DB file → activate via worker. Three-label progress indicator; graceful failure recovery per PRD §5.3.

After this slice, the full engagement-switching UX works end-to-end. Doug can switch between CRMBUILDER and any other engagement record via the picker; the kill-relaunch dance executes per spec; the active-engagement state persists across restart via `current_engagement.json`. Single-gesture engagement creation works: one click creates the meta DB row, creates the per-engagement DB file with Alembic at head, and activates the new engagement, with graceful inline failure handling at each stage.

This slice does NOT include the version bump (slice E), the README release note (slice E), or the end-to-end smoke test (slice E).

## Project context

Slice A provided the foundation: meta DB, two-database API, ActiveEngagementContext, `current_engagement.json` cross-restart load, lazy-migration helper. Slice B built the engagement REST API. Slice C built the management panel.

Slice D's centerpiece is the 12-step activation sequence. The sequence is the most complex piece of v0.5 — it orchestrates a kill-relaunch dance across the API and MCP subprocesses while updating in-memory state and persisting cross-restart state. The activation overlay is the user-facing surface of the dance; the worker is the orchestration. Both are new in this slice.

The single-gesture creation+activation flow combines the slice-C Create dialog with the activation worker. The single-gesture flow is the primary path for creating engagements after slice D lands; the slice-C "create-record-only" path remains available for unusual cases (e.g., scripted creation followed by deliberate non-activation).

## Pre-flight

1. Confirm working directory.
2. Confirm `git status` clean.
3. Confirm git identity.
4. Pull latest.
5. **Verify slice C is in place.** Engagement panel renders. CRUD dialogs operate. Forbid-active-delete behavior works with TODO placeholders for the "Switch engagement" / "Create engagement" buttons. Slice C tests pass.
6. Confirm API operational.
7. Confirm slice C's test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry. Pay attention to the v0.4 subprocess-management section if present.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` §3 (architecture summary), §5.2 (switching affordance), §5.3 (single-gesture creation), §5.6 (forbid-active-delete — the slice D wiring point).
3. `PRDs/product/crmbuilder-v2/ui-v0.5-implementation-plan.md` Step D.
4. `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` §4 — the 12-step activation sequence detail. This is the authoritative spec for the activation worker. Note the amendment in PRD §3: step 7's `engagement_last_opened_at` PATCH is **deferred** to after the new API subprocess is up. The amended order: kill (4) → kill (5) → write current_engagement.json (6) → update in-memory context (7, was step 8) → launch new API (8, was step 9) → launch new MCP (9, was step 10) → PATCH `engagement_last_opened_at` via new API (10, was step 7 originally) → emit signal (11) → UI restore (12).
5. `PRDs/product/crmbuilder-v2/styling-design-pass.md` — design tokens for the top-strip, picker dropdown, activation overlay, and the new-engagement dialog progress indicator.
6. v1 precedent for engagement switching:
   - `automation/ui/active_client_context.py` — the active-state pattern
   - `automation/core/client_reachability.py` — the reachability check that slice D's activation step 2 mirrors
7. Slice A, B, C deliverables:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py` — slice D updates the in-memory context post-activation
   - `crmbuilder-v2/src/crmbuilder_v2/migration/lazy_migration.py` — `run_engagement_migrations(code)` called from activation step 3
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_delete.py` — the slice-C inert "Switch engagement" / "Create engagement" buttons that slice D rewires
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_crud.py` — `EngagementCreateDialog`, which `NewEngagementDialog` extends

## Step 1 — Top-strip widget

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/engagement_top_strip.py`.

The widget renders inside the sidebar container, positioned above the existing sidebar group entries (Engagements group, then Governance, then Methodology). Inherits `QWidget`.

### 1.1 Visual structure

Content row: active engagement's `engagement_name` (body text), code in parentheses (small, `color.neutral.500`), right-aligned Lucide chevron-down at 14px. Background `color.neutral.100`. Padding `space.2 × space.3`. Height 48px. 1px hairline `color.neutral.200` border below (separates from sidebar groups).

Clicking anywhere on the strip opens the picker dropdown (Step 2).

### 1.2 Active-engagement display

The widget subscribes to `ActiveEngagementContext.active_engagement_changed` and re-renders on change.

Display formats:

- When engagement is set: "<engagement_name> (<engagement_code>) ▾" — the chevron-down Lucide icon at the right.
- When engagement is None (no engagement active; fresh-install case before any engagement is created): "No engagement selected ▾" in `color.neutral.500`. The chevron is still visible and operable — clicking opens the picker which shows only the "Manage engagements..." footer.

### 1.3 Application shell integration

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` to instantiate the top-strip and dock it above the sidebar group entries inside the sidebar container. The exact layout integration depends on the v0.4 sidebar implementation — the top-strip becomes the first child of the sidebar's main vertical layout.

## Step 2 — Picker dropdown

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/engagement_picker.py`.

The picker is a popup widget (`QWidget` with `Qt.Popup` window flag) anchored below the top-strip. Width matches the top-strip. Rounded corners per `radius.subtle`. Shadow per `shadow.dialog`.

### 2.1 Row content

Each row shows the engagement name + code in parentheses. Row height matches the v0.4 sidebar entry height. Hover row in `color.neutral.100`.

### 2.2 Ordering

Two-tier ordering:

1. **Live engagements** (status = `active`) first, ordered by `engagement_last_opened_at` descending (most recently opened first). Within this tier, the currently-active engagement appears at the top of this tier even if not strictly most-recently-opened, marked with the active-engagement indicator (see 2.3).

2. **Non-live engagements** (status = `paused` or `archived`) next, rendered in `color.neutral.500`, ordered by `engagement_last_opened_at` descending within their bucket.

Soft-deleted engagements are hidden from the picker by default (no toggle to show — that's the management panel's job).

### 2.3 Active-engagement indicator

The currently-active engagement is marked with a leading Lucide `check` icon (14px, `color.accent.default`) before the engagement name.

### 2.4 Footer item

Separated from engagement rows by a 1px hairline divider in `color.neutral.200`, the footer shows "Manage engagements..." text styled as a body-text row. Clicking the footer:

- Closes the picker
- Navigates the sidebar to the Engagements entry (raises a signal the sidebar listens to, or calls a method on the panel-router)
- Opens the engagement management panel (slice C's panel)

### 2.5 Row click triggers activation

Clicking on an engagement row (not the footer) closes the picker and initiates activation via the `ActivationWorker` (Step 3). The activation overlay (Step 4) appears immediately.

If the clicked row is the currently-active engagement, the picker just closes — no activation needed.

## Step 3 — Activation worker

Create `crmbuilder-v2/src/crmbuilder_v2/ui/activation_worker.py`.

`ActivationWorker` is a `QThread` (or a `QObject` moved to a thread) implementing the 12-step activation sequence per `multi-engagement-architecture.md` §4 with the PRD §3 question-6 amendment.

### 3.1 Worker shape

```python
class ActivationWorker(QObject):
    step_started = Signal(int, str)        # step_number, step_description
    step_completed = Signal(int, str)      # step_number, step_description
    step_failed = Signal(int, str, str)    # step_number, step_description, error_message
    completed = Signal(object)              # the activated Engagement
    failed = Signal(object, str)            # previous Engagement (or None), error_message

    def __init__(self, target_engagement: Engagement, previous_engagement: Engagement | None): ...

    @Slot()
    def run(self) -> None:
        """Execute the 12-step sequence. Emits progress signals at each step."""
```

### 3.2 The 12 steps (amended per PRD §3 / question-6)

1. **User-gesture entry point.** The worker is constructed with target engagement and previous engagement; `run()` begins.

2. **Reachability check.** Read engagement from meta DB (via `client.get_engagement(identifier)`); verify not soft-deleted; compute DB path as `crmbuilder-v2/data/engagements/{engagement_code}.db`; verify file exists and is readable via `os.access(path, os.R_OK)`. Failure: emit `step_failed(2, "...", "Engagement record references file at {path} that does not exist or is not readable")`.

3. **Pre-flight Alembic.** Call `run_engagement_migrations(engagement_code)` from slice A's lazy-migration helper. The helper opens the engagement's DB directly, runs `alembic upgrade head`, closes. Failure: emit `step_failed(3, "...", "Migration failed: {detail}")`.

4. **Kill API subprocess.** Send SIGTERM to the running API subprocess. Wait up to 5 seconds for process termination AND port 8765 release (poll `lsof` or `netstat` or attempt to bind). On 5s timeout, send SIGKILL. Failure (port still bound after SIGKILL): emit `step_failed(4, "...", "API subprocess did not release port 8765")`.

5. **Kill MCP subprocess.** Same SIGTERM-then-SIGKILL pattern for the MCP subprocess. The MCP subprocess port is configurable; consult the v0.4 subprocess-management code for the port value.

6. **Write `current_engagement.json` atomically.** Write to `.tmp` file first, then atomic `rename()` over the destination. The file content is `{"engagement_identifier": "...", "engagement_code": "...", "set_at": "<ISO 8601 UTC>"}`. Failure: emit step_failed; revert in-memory context to previous engagement.

7. **Update in-memory `ActiveEngagementContext`.** Call `context.set_engagement(target_engagement)`. This emits the `active_engagement_changed` signal, but UI components may not be ready to refresh until step 11. Subscribers are responsible for tolerating the in-progress state.

8. **Launch new API subprocess.** Spawn `crmbuilder-v2-api` with environment variable `CRMBUILDER_V2_DB_PATH=crmbuilder-v2/data/engagements/{engagement_code}.db` and the standard API port. Poll `http://127.0.0.1:8765/health` with exponential backoff: initial 100ms, doubling each retry, max delay 5s, total timeout 30s. Stop polling when health returns 200 OK.

9. **Launch new MCP subprocess.** Same pattern; the MCP subprocess connects to the new API (or uses the same connection model the v0.4 MCP server uses).

10. **PATCH `engagement_last_opened_at`** (the amended step from PRD §3 / question-6 — was step 7 in the original architecture-doc sequence; deferred to after the new API is up). Call `client.patch_engagement(identifier, engagement_last_opened_at=<ISO 8601 UTC now>)`. Failure here is logged but does not abort the activation (idempotent; will retry on next switch). Emit step_completed regardless.

11. **Emit `active_engagement_changed` signal.** Already emitted in step 7, but explicitly emit again to give UI components a clean refresh signal post-activation when all infrastructure is ready.

12. **UI restore.** Emit the worker's `completed(target_engagement)` signal. The activation overlay binds to this and dismisses.

### 3.3 Failure handling

Any step failure aborts the sequence and emits `failed(previous_engagement, error_message)`. The in-memory context reverts to the previous engagement if it was updated; `current_engagement.json` reverts if it was written; killed subprocesses are NOT re-launched against the previous engagement (the activation overlay's "Retry" affordance gives the user the option to attempt switching again, including back to the previous engagement). The previous-engagement subprocess is not restarted automatically — the user must explicitly retry or stay.

This means after a failed activation, the user is in a no-subprocess state until they take an action. The activation overlay surfaces this clearly.

### 3.4 Progress reporting

Each step emits `step_started(N, "Description")` before doing work and `step_completed(N, "Description")` on success. The activation overlay binds to these and displays the current step. Step descriptions for the 12 steps:

1. "Preparing..."
2. "Verifying engagement is reachable..."
3. "Upgrading engagement database..."
4. "Stopping API server..."
5. "Stopping MCP server..."
6. "Saving active engagement state..."
7. "Updating engagement context..."
8. "Starting API server..."
9. "Starting MCP server..."
10. "Recording last-opened timestamp..."
11. "Notifying panels..."
12. "Finalizing..."

## Step 4 — Activation overlay

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/activation_overlay.py`.

The overlay is a modal-like widget that appears centered over the main window during activation. Background: semi-transparent dark scrim (matches the `shadow.dialog` modal backdrop per styling design pass). Content: a rounded card with title, current-step description, progress indicator (12-step segmented or a percentage bar), and on failure, error message + retry/stay affordances.

### 4.1 Binding to the worker

Constructed with a reference to the `ActivationWorker`. Subscribes to `step_started`, `step_completed`, `step_failed`, `completed`, `failed`.

### 4.2 Success path

- Initial: title reads "Switching to <target_engagement_name>..."
- On `step_started(N, desc)`: title shows desc; progress indicator advances to step N of 12.
- On `step_completed(N, desc)`: progress indicator marks step N complete.
- On `completed(engagement)`: overlay fades out and is removed.

### 4.3 Failure path

- On `step_failed(N, desc, error_message)` or `failed(previous, error_message)`: title changes to "Switching failed at step <N>" (or "Switching failed"); error_message displayed; two affordances appear:
  - **"Try switching now"** — restarts the worker against the target engagement. Useful if the failure was transient (port-release timeout that resolves on retry, etc.).
  - **"Stay in <previous_engagement_name>"** — closes the overlay; the user remains in the previous engagement's state. If the previous engagement was killed during activation and no subprocess is running, the overlay's stay-button starts up a fresh API+MCP subprocess pointed at the previous engagement before closing.

## Step 5 — Single-gesture new engagement dialog

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/new_engagement_dialog.py`.

`NewEngagementDialog` extends slice-C's `EngagementCreateDialog`. The form fields are identical to the parent; the difference is in the submit behavior.

### 5.1 Submit flow

On Submit, runs three sequential operations behind one user click per PRD §5.3:

1. **POST `/engagements` via `client.create_engagement(...)`.** On success, capture the returned `Engagement` record. On failure, display validation errors inline (parent class behavior); dialog stays open.

2. **Create per-engagement DB file.** The desktop creates the file at `crmbuilder-v2/data/engagements/{engagement_code}.db` (empty SQLite file) and runs `alembic upgrade head` against it via slice A's `run_engagement_migrations(engagement_code)` helper. On failure, the dialog sends DELETE `/engagements/{identifier}` via `client.delete_engagement()` to roll back the meta DB row (the engagement record is effectively never-created); displays an error in the dialog ("Database initialization failed: <error>"); offers a "Try again" button that retries from step 2 (the meta DB row no longer exists, so the user re-submits which retries from step 1).

3. **Activate via `ActivationWorker`.** Construct an `ActivationWorker` with the new engagement as target and the current active engagement as previous. The dialog's body transitions to the activation-overlay state (or hands control to the overlay widget). On activation success: dialog closes; main UI is now showing the new engagement's state. On activation failure: dialog body shows the error state with two affordances per PRD §5.3:
   - **"Try switching now"** — retries activation only (engagement record and file persist).
   - **"Stay in <previous_engagement_name>"** — closes the dialog; engagement record persists; user can retry switching later from the picker.

### 5.2 Progress indicator

During the three operations, the dialog body shows three labels in turn:

- "Creating engagement record..." (during operation 1)
- "Initializing database..." (during operation 2)
- "Switching to <name>..." (during operation 3)

Each label transitions to a Lucide `check` icon (14px, `color.accent.default`) on success or a Lucide `circle-x` (14px, `color.danger.default`) on failure.

## Step 6 — Slice C button rewiring

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_delete.py` (slice C's file) to rewire the slice-C TODO placeholders:

- **"Switch engagement" button** (Case B in the forbid-active-engagement state): closes the delete dialog and opens the picker dropdown (programmatically — anchor below the top-strip and show it). Slice C had this wired to a stdout print; slice D replaces with the real call.
- **"Create engagement" button** (Case B sub-case in the last-engagement state): closes the delete dialog and opens `NewEngagementDialog` (the slice D extension). Slice C had this opening the slice-C Create dialog; slice D replaces with the single-gesture variant.

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagement_panel.py` (slice C's file) to rewire the "Create Engagement" empty-state button: opens `NewEngagementDialog` instead of slice-C's `EngagementCreateDialog`. Same change for the right-click context menu's "New" item.

The slice-C `EngagementCreateDialog` remains in the codebase (the parent class for `NewEngagementDialog`); it is no longer the default entry point but is still available for scripted use (e.g., creating a record without activation for testing or recovery scenarios).

## Step 7 — Tests

### 7.1 `tests/crmbuilder_v2/ui/test_engagement_top_strip.py`

- Renders with the active engagement's name and code.
- Renders "No engagement selected" when context is empty.
- Click triggers picker opening (verify via signal emission or qtbot click + picker-widget-visible assertion).
- Re-renders on `active_engagement_changed` signal.

### 7.2 `tests/crmbuilder_v2/ui/test_engagement_picker.py`

- Renders live engagements first, ordered by `engagement_last_opened_at` descending.
- Renders paused and archived at bottom in muted color, sorted by last_opened_at descending within bucket.
- Active engagement marked with check icon at top of live tier.
- Footer "Manage engagements..." present, separated by divider.
- Soft-deleted not rendered.
- Click on non-active engagement triggers activation (verify ActivationWorker construction or signal).
- Click on active engagement closes picker without activation.
- Click on footer closes picker and navigates to engagement panel.

### 7.3 `tests/crmbuilder_v2/ui/test_activation_worker.py`

Tests for the 12-step sequence. Most tests use mocked subprocess interactions and a temp DB setup.

- **Happy path:** all 12 steps emit step_started+step_completed; `completed(engagement)` emits at end; `current_engagement.json` updated; in-memory context updated; PATCH `engagement_last_opened_at` succeeds.
- **Step 2 failure (reachability):** engagement record references non-existent file; emits `step_failed(2, ..., ...)` and `failed(previous, ...)`; in-memory context preserved.
- **Step 3 failure (migration):** migration helper raises MigrationError; emits step_failed(3, ...); failed.
- **Step 4 failure (port-release timeout):** simulated by injecting a fake subprocess manager that doesn't terminate within 5s; emits step_failed(4, ...) after SIGKILL escalation also fails (configurable in mock).
- **Step 8 failure (API health-check timeout):** simulated by injecting a fake subprocess that doesn't respond to /health within 30s; emits step_failed(8, ...).
- **Step 10 failure (PATCH `engagement_last_opened_at` fails):** logged but does NOT abort activation; emits step_completed(10, ...) anyway; full sequence completes.

### 7.4 `tests/crmbuilder_v2/ui/test_new_engagement_flow.py`

- **Happy path:** POST succeeds, file creation succeeds, activation succeeds; dialog closes; main UI shows new engagement active.
- **POST failure:** dialog displays inline error; stays open; no file created; no activation initiated.
- **File-creation failure:** dialog displays error; meta DB row rolled back (DELETE call asserted); user can retry submit.
- **Activation failure after both creates succeed:** dialog body shows error state; engagement record persists in meta DB; file persists on disk; affordances visible; "Try switching now" reruns activation; "Stay in <previous>" closes dialog.

## Acceptance verification

Before committing:

1. **All slice D tests pass.** `uv run pytest tests/crmbuilder_v2/ui/test_engagement_top_strip.py tests/crmbuilder_v2/ui/test_engagement_picker.py tests/crmbuilder_v2/ui/test_activation_worker.py tests/crmbuilder_v2/ui/test_new_engagement_flow.py -v`.
2. **Full v0.5 suite passes.** `uv run pytest tests/crmbuilder_v2/ -v`.
3. **Manual smoke: top-strip renders.** Open desktop. Confirm top-strip is visible above sidebar groups; shows "CRMBuilder v2 (CRMBUILDER) ▾".
4. **Manual smoke: picker opens.** Click top-strip. Picker opens below; CRMBUILDER row is shown with check icon; footer "Manage engagements..." present.
5. **Manual smoke: create CBM engagement.** Open the picker → "Manage engagements..." → engagement panel → New (or top-strip → picker → close → click sidebar engagement entry → New). Submit code "CBM", name "Cleveland Business Mentoring", purpose "CBM Phase 1 pilot per the v0.5 dogfood discipline". Confirm the three-label progress indicator advances through "Creating engagement record..." → "Initializing database..." → "Switching to Cleveland Business Mentoring..." Confirm activation completes. Confirm top-strip now shows "Cleveland Business Mentoring (CBM) ▾". Confirm `crmbuilder-v2/data/engagements/CBM.db` exists. Confirm `current_engagement.json` references CBM.
6. **Manual smoke: switch back to CRMBUILDER.** Click top-strip. Picker shows CBM (active) at top of live tier with check, CRMBUILDER below (also active status). Click CRMBUILDER. Activation overlay appears with progress through the 12 steps. Completes. Top-strip shows CRMBUILDER.
7. **Manual smoke: per-engagement scope.** Switch to CBM. Open the Sessions panel — verify it is empty (no SES-027 from the dogfood). Switch back to CRMBUILDER. Open Sessions — verify SES-027 (or whatever the dogfood's latest is) is present. This confirms per-engagement identifier scope and DB isolation.
8. **Manual smoke: cross-restart persistence.** With CBM active, close the desktop. Reopen. Confirm CBM is restored as the active engagement (top-strip shows CBM; Sessions panel is empty). Switch to CRMBUILDER. Close desktop. Reopen. CRMBUILDER restored.
9. **Manual smoke: forbid-active-delete with slice D wiring.** Switch to CBM. Right-click CBM in the engagement panel → Delete. Confirm the forbid-active dialog appears with "Switch engagement" button. Click — picker opens. Click CRMBUILDER. Activation completes; the delete dialog is no longer relevant (different engagement is now active). Retry: right-click CBM → Delete. Now CBM is not active, so the standard confirmation flow runs. Soft-delete CBM. Verify the engagement panel shows CBM as soft-deleted when "Show soft-deleted" is checked.

If any verification step fails, stop and report.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/widgets/engagement_top_strip.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/widgets/engagement_picker.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/widgets/activation_overlay.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/activation_worker.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/new_engagement_dialog.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_delete.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagement_panel.py \
        crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        tests/crmbuilder_v2/ui/test_engagement_top_strip.py \
        tests/crmbuilder_v2/ui/test_engagement_picker.py \
        tests/crmbuilder_v2/ui/test_activation_worker.py \
        tests/crmbuilder_v2/ui/test_new_engagement_flow.py
git commit -m "v2: v0.5 slice D — engagement switching (top-strip, picker, 12-step activation worker with q6 amendment, single-gesture creation+activation flow)"
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT bump `__version__` (slice E).
- Do NOT add the README v0.5 release note (slice E).
- Do NOT add the end-to-end integration smoke test (slice E).
- Do NOT modify the slice B REST API surface. The API contract is frozen at slice B.
- Do NOT modify the slice C management panel's column layout or detail-pane structure. Slice D's panel touches are limited to rewiring the empty-state and context-menu New buttons to open `NewEngagementDialog`.
- Do NOT add an activate REST endpoint. Activation is desktop-side; PI-017 will add an activate endpoint at the prototype-to-production transition per DEC-081.
- Do NOT add multi-tenant API server changes. PI-017 anchors that work for the later transition.
- Do NOT change the 12-step activation sequence's step order beyond the documented amendment (PATCH deferred to step 10). The order is specified in `multi-engagement-architecture.md` §4 as amended.
- Do NOT write any session, decision, or planning records.

---

*End of prompt.*
