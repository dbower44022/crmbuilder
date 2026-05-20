# CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-B-ui-refactor-affordances

**Last Updated:** 05-19-26 16:00
**Operating mode:** DETAIL
**Series:** multi-tenancy-routing-fix
**Slice:** B — UI refactor + operator affordances + integration
**Status:** Ready to execute (requires slice A to have landed first)
**Companions:**
- `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md` — overall plan (§5 slice B section is authoritative for acceptance criteria).
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-A-helpers-cli-gate.md` — slice A prompt (predecessor).
- `PRDs/product/crmbuilder-v2/multi-tenancy-routing-investigation-report.md` — diagnostic context.

---

## Purpose

Land the UI half of the multi-tenancy routing fix. Refactor the existing `ui/app.py:_route_api_at_active_engagement` and `ui/active_engagement_context.py` to call the slice A helpers instead of duplicating the inline routing logic. Surface the new failure conditions (null `engagement_export_dir`, missing path on disk) to operators via warning bands in the Engagements panel, visual emphasis in the Edit Engagement dialog, and graceful error-dialog handling. Add pytest-qt integration tests across a two-engagement state to verify the full UI-launched path matches the CLI-launched path.

After this slice lands:
- UI-launched and CLI-launched API paths share one routing implementation.
- Operators see why a write failed before they hit it (or at the latest in the error dialog with a clear remediation action).
- PI-021 is dischargeable.

This slice depends on slice A having landed first — it imports from `crmbuilder_v2.runtime.engagement_routing` and `crmbuilder_v2.runtime.exceptions`.

---

## Pre-flight

1. **Confirm working directory.** `pwd` should resolve to the crmbuilder repo clone root. Stop if unexpected.

2. **Confirm `git status` is clean.** Stop and report if there are uncommitted changes.

3. **Confirm git identity is set:**

   ```bash
   git config user.name "Doug Bower"
   git config user.email "doug@dougbower.com"
   ```

4. **Pull latest from origin:**

   ```bash
   git pull --rebase origin main
   ```

   Stop and report if there are conflicts.

5. **Confirm slice A has landed.** Verify the slice A module exists:

   ```bash
   ls -la crmbuilder-v2/src/crmbuilder_v2/runtime/engagement_routing.py
   ls -la crmbuilder-v2/src/crmbuilder_v2/runtime/exceptions.py
   ```

   Both must exist. If either is missing, slice A hasn't landed; stop and ask Doug to run slice A first.

6. **Read CLAUDE.md and the companion documents:**

   - `CLAUDE.md` (root) — review the existing UI patterns, particularly the "Direct-API writes for prefixed-identifier entity types" note and the `{data, meta, errors}` envelope convention.
   - `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md` — slice B section (§5) is authoritative for acceptance criteria.
   - `PRDs/product/crmbuilder-v2/ui-PRD-v0.5.md` and `ui-PRD-v0.6.md` — particularly any references to the Engagements panel and Edit Engagement dialog architecture.

7. **Discover the actual file paths** for the UI components slice B touches. The slice plan lists candidate paths but slice B starts with a code-read to confirm:

   ```bash
   find crmbuilder-v2/src/crmbuilder_v2/ui -name "*.py" | xargs grep -l -i "engagement" | head -20
   ```

   Identify:
   - The Edit Engagement dialog file (likely `ui/dialogs/engagement_edit.py` or similar).
   - The Engagements panel file (likely `ui/panels/engagements.py` per the v0.5 plural-naming convention, but confirm).
   - The error-handler / error-dialog file (likely `ui/dialogs/error.py` per the v0.6 styling work).
   - The about_dialog file (already at `ui/about_dialog.py` per CLAUDE.md).

8. **Confirm the test suite is currently green.** Baseline before any changes:

   ```bash
   cd crmbuilder-v2
   uv run pytest tests/crmbuilder_v2/ -v --tb=short 2>&1 | tail -30
   cd ..
   ```

9. **Read the relevant code paths** without modifying:
   - `ui/app.py:226-253` — the existing `_route_api_at_active_engagement` (the inline path slice B refactors).
   - `ui/active_engagement_context.py:32-138` — the existing JSON-read path.
   - The Edit Engagement dialog identified in step 7.
   - The Engagements panel identified in step 7.
   - The error-dialog file identified in step 7.
   - `ui/about_dialog.py:148` — the existing "Snapshot directory" display line.

10. **Verify the slice A helpers behave as expected.** Run the slice A test suite:

    ```bash
    cd crmbuilder-v2
    uv run pytest tests/crmbuilder_v2/runtime/ -v
    cd ..
    ```

    Green confirms slice A is functioning.

---

## Workflow

Seven numbered steps. Each step's acceptance is the test invocation noted at its end.

### Step 1 — Refactor `ui/app.py:_route_api_at_active_engagement`

The current `_route_api_at_active_engagement(active, log)` at `ui/app.py:226-253` inlines: read engagement code → compute db_path → set env var → reset caches. Replace this inline logic with one call to `route_settings_to_engagement(code)`.

Steps:

- Add import: `from ..runtime.engagement_routing import route_settings_to_engagement`.
- Add import: `from ..runtime.exceptions import UnknownEngagementError`.
- Replace the inline body of `_route_api_at_active_engagement` with: extract the engagement code from `active` (whatever the signature is — likely `active.engagement_code()` or `active.code`), call `route_settings_to_engagement(code)` wrapped in try/except for `UnknownEngagementError`. On exception: log via the `log` callback and show an error dialog (use the existing UI error pattern — likely calls a function in `ui/dialogs/error.py` or equivalent).
- Preserve the existing function signature so callers don't need updating.
- Preserve any logging side effects (the function probably emits a status log line at start and end; keep those).

**Acceptance:** UI launches, switches between CRMBUILDER and CBM via the Engagements panel, both routes work. Manual smoke required since this is UI; see Step 7 for integration test coverage.

### Step 2 — Refactor `ui/active_engagement_context.py` to use `resolve_active_engagement`

The current `ActiveEngagementContext` reads `current_engagement.json` directly in two places (lines ~32-34 at construction, lines ~85-138 in a refresh method). Replace these reads with calls to `resolve_active_engagement()`.

Steps:

- Add import: `from ..runtime.engagement_routing import resolve_active_engagement`.
- Replace the direct JSON-read code in `__init__` with `code = resolve_active_engagement()`.
- Replace the refresh-method JSON-read code similarly.
- Preserve the Signal/Slot interface (`engagement_code()`, `active_engagement_changed(object)` Signal) exactly.
- Preserve the existing behavior when the marker is missing (probably emits Signal with None or doesn't emit; match exactly).

**Acceptance:** The UI still detects engagement changes correctly. The existing pytest-qt tests for `ActiveEngagementContext` pass unchanged. Run: `uv run pytest tests/crmbuilder_v2/ui/ -v -k "active_engagement" 2>&1 | tail -20` from inside `crmbuilder-v2/`.

### Step 3 — Update `ui/about_dialog.py` to render sentinel and missing-path states

At line ~148 the dialog currently displays `("Snapshot directory", str(settings.export_dir))`. Update to render three states:

- If `str(settings.export_dir)` equals `__UNCONFIGURED__` (use the constant from `runtime.engagement_routing.UNCONFIGURED_SENTINEL`): display `"(not configured)"`.
- Else if `settings.export_dir.is_dir()` is False: display `f"(missing — {settings.export_dir})"`.
- Else: display `str(settings.export_dir)` (today's behavior).

The display label "Snapshot directory" stays unchanged.

**Acceptance:** Three new unit tests in the existing `test_about_dialog.py`: one for each state. Run: `uv run pytest tests/crmbuilder_v2/ui/test_about_dialog.py -v 2>&1 | tail -10`.

### Step 4 — Add Open Engagement warning band when export_dir is null or missing

In the Engagements panel (path identified in pre-flight step 7, likely `ui/panels/engagements.py`):

- After the active-engagement header / detail render block, add a `WarningCallout` widget (from slice E of v0.6 per the styling work, if available; otherwise build a small ad-hoc QWidget with QSS-styled background and a label + button).
- The callout has two states:
  - **Null state (yellow):** When the active engagement's `engagement_export_dir` is null/empty. Text: `"This engagement has no export directory configured. Reads will work; writes are disabled until you set one via Edit Engagement."` Action button: `"Set export directory…"` opens Edit Engagement dialog focused on the `engagement_export_dir` field.
  - **Missing state (red):** When the active engagement's `engagement_export_dir` is set but the path doesn't exist on disk. Text: `f"Configured export directory does not exist on disk: {path}. Either create the directory or update the engagement via Edit Engagement."` Action button: `"Edit engagement…"` opens Edit Engagement dialog.
  - **Hidden:** Otherwise.
- The callout's state is recomputed whenever the active engagement changes (subscribe to `ActiveEngagementContext.active_engagement_changed`) and whenever the Engagements panel receives a `file_changed` refresh signal.

To check the disk-existence state, use `pathlib.Path(export_dir).is_dir()`. To check null/empty, the engagement record's `engagement_export_dir` field — fetch from the meta DB or read from whatever data model the panel already has loaded.

**Acceptance:** Manual smoke: configure an engagement with null export_dir, activate it, verify yellow band appears. Set the export_dir to a path that doesn't exist, activate, verify red band appears. Set to a valid path, verify band hidden. Click the action button, verify Edit Engagement dialog opens (focused on the field for the null case).

### Step 5 — Update Edit Engagement dialog with visual emphasis on null export_dir + save validation

In the Edit Engagement dialog (path identified in pre-flight step 7):

- The `engagement_export_dir` field (likely a `LineEdit` + Browse button combo) gets a subtle visual emphasis when null/empty. Use the existing styling tokens from v0.6 — likely a warning-amber border via `setStyleSheet` with a token reference, or a small icon overlay. Match the existing pattern for other emphasis surfaces in v0.6 dialogs.
- On dialog save, validate the field's value:
  - If empty: save as null. No additional prompt.
  - If non-empty AND `Path(value).is_dir()` is True: save as the path. No prompt.
  - If non-empty AND path doesn't exist: prompt `f"The path '{value}' does not exist. Save anyway? You can create the directory later."` with `[Save anyway]` (default) and `[Cancel]` buttons. On Save anyway: save the path. On Cancel: return focus to the dialog without closing.

The "focus on engagement_export_dir field" hook for the warning band's action button: add a public method `focus_export_dir_field(self)` that calls `self.export_dir_input.setFocus()`. The warning band's action button instantiates the dialog and calls this method before showing.

**Acceptance:** Manual smoke: open Edit Engagement on an engagement with null export_dir, verify visual emphasis. Save with no path → succeeds, field stays null. Save with a path that doesn't exist → confirmation prompt → Save anyway lands the path, Cancel returns. Save with valid path → no prompt. Plus existing dialog tests pass: `uv run pytest tests/crmbuilder_v2/ui/test_engagement_edit*.py -v` from inside `crmbuilder-v2/`.

### Step 6 — Update error-dialog handling for new exceptions

In the UI's error-handler (likely `ui/dialogs/error.py` or wherever uncaught HTTP errors are rendered into operator-facing dialogs):

- When the API returns HTTP 500 with a body containing `EngagementExportDirNotConfigured` or `EngagementExportDirMissing` (or the matching error message text — confirm by reading `api/errors.py` for how exceptions get rendered into HTTP responses), render a friendly error dialog with:
  - **Title:** `"Cannot save — export directory issue"` (or similar).
  - **Body:** The exception message (e.g., the messages defined in slice A's exceptions module).
  - **Action button:** `"Edit engagement…"` that opens the Edit Engagement dialog for the active engagement.
  - **Dismiss button:** `"Cancel"` / `"OK"`.

The HTTP response shape depends on slice A's choice of how the FastAPI exception handler renders `EngagementExportDirError` subclasses. If they're allowed to propagate as 500s with the message in the body, that's the path. If slice A added explicit handlers returning 422 or another code, match that.

If `api/errors.py` doesn't have handlers for these exceptions yet, this step also includes adding them: register exception handlers in `api/main.py` (or wherever FastAPI app setup lives) that catch `EngagementExportDirError` and return HTTP 500 with the standard `{data: null, meta: ..., errors: [...]}` envelope per CLAUDE.md.

**Acceptance:** Manual smoke: with an engagement whose export_dir is null/missing, attempt a write via the UI (create a session, edit a decision). Verify a friendly error dialog appears with an "Edit engagement" action button. Click the action button, verify Edit Engagement opens. Plus any new tests in `tests/crmbuilder_v2/api/test_errors.py` for the new handlers.

### Step 7 — Write pytest-qt integration tests

Create `crmbuilder-v2/tests/crmbuilder_v2/ui/test_app_engagement_routing.py` containing at minimum:

- **`test_switch_engagements_routes_to_correct_db`** — fixture sets up two engagements (CRMBUILDER + CBM) with distinct meta records. Activate CRMBUILDER, write a session record via the UI, verify it lands in CRMBUILDER.db. Activate CBM, write a session record, verify it lands in CBM.db. No cross-contamination.
- **`test_switch_engagements_routes_to_correct_export_dir`** — same fixture, distinct `engagement_export_dir` paths. Activate CRMBUILDER, commit, verify snapshot lands in CRMBUILDER's path. Activate CBM, commit, verify snapshot lands in CBM's path. CRMBUILDER's path untouched by the CBM commit.
- **`test_activate_engagement_with_null_export_dir_shows_yellow_warning_band`** — fixture creates an engagement with null `engagement_export_dir`. Activate, verify the warning band appears with yellow state.
- **`test_activate_engagement_with_missing_export_dir_shows_red_warning_band`** — fixture creates an engagement with a path that doesn't exist on disk. Activate, verify the warning band appears with red state.
- **`test_save_engagement_with_nonexistent_export_dir_prompts_confirm`** — open Edit Engagement, enter a path that doesn't exist, click Save, verify confirmation prompt appears. Click Save anyway, verify path is saved.

Use the existing pytest-qt fixtures for app/main_window setup; reference an existing test in `tests/crmbuilder_v2/ui/` for the pattern.

**Acceptance:** `uv run pytest tests/crmbuilder_v2/ui/test_app_engagement_routing.py -v` returns green from inside `crmbuilder-v2/`.

---

## Acceptance gate

Before committing, verify every acceptance criterion from §5 slice B of the slice plan:

- B1 — B9 as enumerated. Walk through each.
- Full test suite passes (`uv run pytest tests/crmbuilder_v2/ -v` returns 0).
- Manual smoke: open the desktop UI, switch engagements via Engagements panel, verify warning bands appear at the right times, verify Edit Engagement dialog visual emphasis, verify writes go to the right place. Capture a screenshot of each new UI state (yellow band, red band, dialog emphasis, error dialog with action button) and save to `PRDs/product/crmbuilder-v2/styling-screenshots/multi-tenancy-routing-fix/` for retrospective reference. Optional but recommended; matches the v0.6 screenshot capture protocol per DEC-107.

---

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/app.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/active_engagement_context.py
git add crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py
# Add the actual paths discovered in pre-flight step 7:
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/engagement_edit.py  # path TBD
git add crmbuilder-v2/src/crmbuilder_v2/ui/panels/engagements.py        # path TBD
git add crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py             # path TBD
git add crmbuilder-v2/src/crmbuilder_v2/api/errors.py                   # if exception handlers added
git add crmbuilder-v2/src/crmbuilder_v2/api/main.py                     # if handler registration added
git add crmbuilder-v2/tests/crmbuilder_v2/ui/test_app_engagement_routing.py
# Plus any updated existing UI tests

# Optionally:
git add PRDs/product/crmbuilder-v2/styling-screenshots/multi-tenancy-routing-fix/

git status   # confirm only expected files staged
```

Commit message:

```
v2: multi-tenancy routing fix slice B — UI refactor + operator affordances

Completes the multi-tenancy routing fix. UI and CLI now share one
routing implementation (the slice A helpers). Operators see why a
write would fail before they hit it, or in the error dialog with a
clear remediation action when they do.

UI refactors (no behavior change):
- ui/app.py:_route_api_at_active_engagement — calls
  runtime.engagement_routing.route_settings_to_engagement() instead
  of duplicating env-var-set + cache-reset code
- ui/active_engagement_context.py — uses
  runtime.engagement_routing.resolve_active_engagement() instead of
  duplicating the marker-file JSON read

UI affordances (new):
- ui/about_dialog.py — Snapshot directory line renders
  "(not configured)" for unconfigured sentinel, "(missing — <path>)"
  for paths that don't exist on disk, raw path otherwise
- ui/panels/engagements.py — yellow warning band on Open Engagement
  when export_dir is null; red warning band when path is missing;
  each band has an action button opening Edit Engagement
- ui/dialogs/engagement_edit.py — visual emphasis on the
  engagement_export_dir field when null; save validates path
  existence with [Save anyway] / [Cancel] confirm for non-existent
  paths
- ui/dialogs/error.py — friendly error dialog for
  EngagementExportDirNotConfigured and EngagementExportDirMissing
  with an "Edit engagement…" action button
- api/main.py / api/errors.py — exception handlers register the new
  EngagementExportDirError subclasses; HTTP 500 with standard
  {data, meta, errors} envelope per CLAUDE.md

Tests:
- tests/crmbuilder_v2/ui/test_app_engagement_routing.py — 5 pytest-qt
  integration tests covering switch-routes-correctly, both warning
  band states, save-with-nonexistent-path confirm flow
- Updated about_dialog tests for the three display states
- Updated existing dialog tests for the new field emphasis

Full regression: uv run pytest tests/crmbuilder_v2/ -v passes.

Manual smoke at slice end captured screenshots at
PRDs/product/crmbuilder-v2/styling-screenshots/multi-tenancy-routing-fix/
(if captured).

PI-021 dischargeable after this slice lands.

Refs SES-044, PI-021.
```

Doug pushes.

---

## Done

After commit lands and Doug pushes:

- Both bugs from the investigation are fixed end-to-end.
- UI and CLI paths share one routing implementation.
- Operators see the new failure conditions clearly.
- PI-021 is ready to close.

**Next governance step:** discharge PI-021 via the desktop UI's planning-items panel or via direct API POST. Status: `Open` → `Closed (resolved)`. Reference SES-044 as `is_about`.

**Next build step:** none. The multi-tenancy routing fix workstream is complete. Resume the SES-001 paper-test apply attempt that surfaced these bugs in the first place, against the now-fixed system.
