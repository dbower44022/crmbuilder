# CLAUDE-CODE-PROMPT-v2-ui-v0.3-D-sessions-create-dialog

**Last Updated:** 05-09-26 17:30
**Series:** v2-ui-v0.3
**Slice:** D (4 of 5)
**Status:** Ready to execute (after slice C is reported complete)
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.3-C (References write surface)

## Purpose

This is the fourth of five slices that build the CRMBuilder v2 desktop UI v0.3. This prompt builds slice **D — Sessions create dialog**.

Slice D delivers the Sessions create-only surface: a dialog (instance of `EntityCrudDialog`) that authors a new session record with auto-assigned identifier, sensible defaults, and placeholder text hinting at DEC-025 conventions; a `New Session` toolbar button on the Sessions panel; a `New session` whitespace right-click action extending the slice-B context menu.

After this slice, the user can record a session entirely through the UI — meaning the next planning conversation after v0.3 can be captured by Doug, in the app, with no script runs. That is the user-facing acceptance test for v0.3 itself.

Per DEC-013 and DEC-034, the Sessions surface is **append-only**:

- **No edit button** anywhere.
- **No delete button** anywhere.
- **No restore.**
- **No "Save draft" mode.** The dialog is fill-everything-once-and-save.
- **No broadening** of session scope to non-Claude.ai conversations.

This slice does NOT relax any of those constraints.

## Project context

Slices A through C landed:
- The `ListDetailPanel` factory refactor and Topics migration (slice A).
- Right-click context menus across all eight existing panels (slice B), including the Sessions panel's existing read-only actions (`Go to references`, `Copy identifier`).
- The full References write surface — dialogs, widget, panel button, detail-pane affordance, right-click delete (slice C).
- Planning records SES-008, DEC-032 through DEC-037, references, PI-NNN, status v0.9.

Per DEC-034, sessions are now user-authorable through the UI. The dialog renders the nine-field schema in PRD §2.4. Identifier auto-assignment runs at dialog-open time. Required-field validation surfaces inline via the existing `EntityCrudDialog` pattern.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `git config user.name` returns `Doug`; `git config user.email` returns `doug@dougbower.com`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice C landed:
   - `dialogs/reference_create.py` and `dialogs/reference_delete.py` exist.
   - `widgets/entity_identifier_picker.py` exists.
   - References panel has a `New Reference` toolbar button.
   - `widgets/references_section.py` has an `Add reference` button.
6. Confirm storage system is operational. Verify-first: `curl -sf http://127.0.0.1:8765/health` — if 200, proceed. If it fails, start the API in the background (`uv run crmbuilder-v2-api &`), wait ~3 seconds, re-check; if still failing, stop and report.
7. Confirm test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Expected ~554 passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.3.md` §4.4 (Sessions create-only surface) and §2.4 (the field schema table) — the contract.
3. `PRDs/product/crmbuilder-v2/ui-v0.3-implementation-plan.md` §4 Step D.
4. v2 governance decisions:
   - **DEC-013** (one Claude.ai conversation = one session record; append-only)
   - **DEC-014** (every v2 conversation produces a session record)
   - **DEC-025** (conversation_reference is descriptive text; topics_covered opens with verbatim seed prompt; no transcript URL)
   - **DEC-034** (this slice's authorizing decision — user-authored sessions permitted; append-only stays strict; narrow-scoped to Claude.ai conversations)
5. **Storage layer surfaces** (read-only first; modify only if Step 1 finds gaps):
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `SESSION_STATUSES`.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/sessions.py` — `create_session` (or whatever the access-layer method is named); `list_sessions` for the auto-assignment query.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py` — `POST /sessions`; `GET /sessions`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas/sessions.py` (or wherever the Pydantic models live).
6. **UI surfaces**:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sessions.py` — to add the `New Session` toolbar button and extend the slice-B context menu with `New session` on whitespace right-click. Confirm the panel does NOT show any Edit, Delete, or Restore button on the detail pane.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — `EntityCrudDialog` and the `FieldSchema` extension from slice C (if Option 1 was taken). The session create dialog uses the framework directly without cascade — straightforward EntityCrudDialog usage.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — to add `create_session`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — confirm `sessions` is in the entity-type → signal map; extend if not.
7. v0.2 dialog patterns: `dialogs/decision_create.py`, `dialogs/risk_create.py`, `dialogs/topic_create.py` — for the EntityCrudDialog usage idiom.

## Step 1 — Investigate the storage layer surface

### `POST /sessions` endpoint

Read `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py`. Confirm the `POST /sessions` endpoint exists and accepts the nine-field payload per PRD §2.4:

- `identifier` (string, e.g., `"SES-009"`)
- `session_date` (string, MM-DD-YY format)
- `status` (string, one of `SESSION_STATUSES`)
- `title` (string)
- `summary` (string, multi-line)
- `topics_covered` (string, multi-line)
- `artifacts_produced` (string, multi-line)
- `in_flight_at_end` (string, multi-line, may be empty)
- `conversation_reference` (string, multi-line)

If `POST /sessions` is missing or has a different shape than the access-layer `create_session` accepts, add or repair the endpoint. The existing `apply_dec_025.py` script's session-writing path is the reference for what the access layer accepts; the HTTP endpoint must be a thin wrapper around the same access-layer call.

### `GET /sessions` for identifier auto-assignment

The dialog reads the existing session list to compute the next `SES-NNN` identifier. The simplest path: call `client.list_sessions()` at dialog-open time, find the highest existing `SES-NNN`, and increment.

If the existing sessions list is large enough (>1000 records) that this becomes slow, consider adding a `GET /sessions/next-identifier` endpoint that returns just the next identifier. For v0.3's session count (~10 today), the simple approach is fine.

### Refresh service

Confirm `sessions` is in the refresh service's file → entity-type → signal map. Extend if missing. The pattern follows the v0.2 entries:

```python
ENTITY_TYPE_FILE_MAP = {
    "decisions.json": "decision",
    "sessions.json": "session",  # confirm this is present
    # ...
}
```

If a signal connection on the Sessions panel side is missing (it should be there from v0.1, but verify), wire it.

### Storage commit

If any storage-layer change was made, commit as a separate first commit:

```
v2: storage — sessions POST endpoint + refresh map
```

(Adjust based on what was actually changed.)

## Step 2 — `SessionCreateDialog`

Create `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/session_create.py`.

```python
from datetime import date

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.vocab import SESSION_STATUSES
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient


SESSION_TOPICS_PLACEHOLDER = (
    'Seed prompt: "..." \n\n'
    "Followed by structured discussion summary "
    "(per DEC-025 conventions)."
)

SESSION_CONVERSATION_REF_PLACEHOLDER = (
    "Descriptive text identifying the conversation by its outputs "
    "(PRDs, prompts, decisions). No transcript URL "
    "(per DEC-025)."
)


class SessionCreateDialog(EntityCrudDialog):
    """Append-only session record creation dialog.

    Identifier is auto-assigned at dialog-open time by querying the
    latest session and incrementing. Required-field validation surfaces
    inline via the EntityCrudDialog base.
    """

    def __init__(
        self,
        parent: QWidget,
        client: StorageClient,
    ) -> None:
        self._client = client
        next_identifier = self._compute_next_identifier()

        schema = [
            FieldSchema(
                key="identifier",
                label="Identifier",
                widget="line",
                required=True,
                read_only=True,  # auto-assigned, not user-editable
            ),
            FieldSchema(
                key="session_date",
                label="Session date",
                widget="date",
                required=True,
            ),
            FieldSchema(
                key="status",
                label="Status",
                widget="combo",
                required=True,
                vocab=frozenset(SESSION_STATUSES),
            ),
            FieldSchema(
                key="title",
                label="Title",
                widget="line",
                required=True,
            ),
            FieldSchema(
                key="summary",
                label="Summary",
                widget="text",
                required=True,
            ),
            FieldSchema(
                key="topics_covered",
                label="Topics covered",
                widget="text",
                required=True,
                placeholder=SESSION_TOPICS_PLACEHOLDER,
            ),
            FieldSchema(
                key="artifacts_produced",
                label="Artifacts produced",
                widget="text",
                required=True,
            ),
            FieldSchema(
                key="in_flight_at_end",
                label="In flight at end",
                widget="text",
                required=False,  # optional per PRD §2.4
            ),
            FieldSchema(
                key="conversation_reference",
                label="Conversation reference",
                widget="text",
                required=True,
                placeholder=SESSION_CONVERSATION_REF_PLACEHOLDER,
            ),
        ]

        initial_values = {
            "identifier": next_identifier,
            "session_date": date.today().strftime("%m-%d-%y"),
            "status": "Complete",
        }

        super().__init__(
            parent=parent,
            title="New Session",
            schema=schema,
            on_save=self._save_session,
            initial_values=initial_values,
        )

    def _compute_next_identifier(self) -> str:
        sessions = self._client.list_sessions()
        max_n = 0
        for record in sessions:
            ident = record.get("identifier", "")
            if ident.startswith("SES-"):
                try:
                    n = int(ident.removeprefix("SES-"))
                    max_n = max(max_n, n)
                except ValueError:
                    continue
        return f"SES-{max_n + 1:03d}"

    def _save_session(self, values: dict) -> None:
        self._client.create_session(
            identifier=values["identifier"],
            session_date=values["session_date"],
            status=values["status"],
            title=values["title"],
            summary=values["summary"],
            topics_covered=values["topics_covered"],
            artifacts_produced=values["artifacts_produced"],
            in_flight_at_end=values.get("in_flight_at_end", ""),
            conversation_reference=values["conversation_reference"],
        )
```

The exact `EntityCrudDialog` API may differ — adapt the construction to match the existing v0.2 base contract. The key requirements:

- Nine fields in the order shown above.
- `identifier` read-only (auto-assigned at dialog-open).
- `session_date` defaults to today.
- `status` defaults to `"Complete"`.
- `topics_covered` and `conversation_reference` show DEC-025-aware placeholder text.
- `in_flight_at_end` is the only optional field.
- Save sends all fields to `client.create_session(...)`.

If the `EntityCrudDialog` from slice C's framework extension supports `read_only=True` cleanly, use that for identifier. If not, render identifier as a `QLabel` above the form rather than as a disabled `QLineEdit` — the slice prompt for slice C noted this option.

### Tests

Create `tests/crmbuilder_v2/ui/test_session_create_dialog.py`:

- `test_dialog_has_nine_fields_in_correct_order` — assert field-key order matches the PRD §2.4 table.
- `test_identifier_auto_assigned_from_latest_session` — mock `list_sessions` returning `[{"identifier": "SES-008"}, {"identifier": "SES-007"}]`; assert identifier shown as `"SES-009"`.
- `test_identifier_skips_invalid_records` — mock `list_sessions` returning records with malformed identifiers; assert auto-assignment still works.
- `test_session_date_defaults_to_today`
- `test_status_defaults_to_Complete`
- `test_topics_covered_placeholder_present` — assert the DEC-025 hint text is in the placeholder.
- `test_conversation_reference_placeholder_present` — same.
- `test_in_flight_at_end_optional` — empty `in_flight_at_end`; click Save; assert successful save.
- `test_required_fields_block_save_with_inline_error` — leave a required field empty; click Save; assert inline error appears and `client.create_session` not called.
- `test_save_calls_client_with_all_field_values` — fill all fields; click Save; assert `client.create_session(...)` called with the expected kwargs.
- `test_identifier_is_read_only` — try to edit the identifier field; assert it can't be modified.
- `test_save_handles_validation_error_envelope` — mock client raises validation error; assert error rendered inline.
- `test_save_handles_identifier_collision_retry` — mock client raises identifier-collision error on first call; assert dialog re-fetches list and retries; succeeds on second call.

## Step 3 — Storage client extension

In `crmbuilder-v2/src/crmbuilder_v2/ui/client.py`, add:

```python
def create_session(
    self,
    *,
    identifier: str,
    session_date: str,
    status: str,
    title: str,
    summary: str,
    topics_covered: str,
    artifacts_produced: str,
    in_flight_at_end: str,
    conversation_reference: str,
) -> dict:
    response = self._post(
        "/sessions",
        json={
            "identifier": identifier,
            "session_date": session_date,
            "status": status,
            "title": title,
            "summary": summary,
            "topics_covered": topics_covered,
            "artifacts_produced": artifacts_produced,
            "in_flight_at_end": in_flight_at_end,
            "conversation_reference": conversation_reference,
        },
    )
    return response
```

The exact method shape (`_post`, error handling, etc.) follows the v0.2 client conventions.

### Tests

Add to the client tests file:

- `test_create_session_posts_correct_payload`
- `test_create_session_propagates_validation_error`
- `test_create_session_propagates_identifier_collision`

## Step 4 — Sessions panel write integration

Open `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sessions.py`.

### Toolbar `New Session` button

Add a button to the panel's toolbar (next to Refresh, between Refresh and any existing buttons):

```python
self._new_session_button = QPushButton("New Session", self)
self._new_session_button.clicked.connect(self._on_new_session_clicked)
self._toolbar.addWidget(self._new_session_button)

def _on_new_session_clicked(self) -> None:
    dialog = SessionCreateDialog(self, client=self._client)
    if dialog.exec() == QDialog.Accepted:
        # File-watch will refresh; explicit refresh as fast-path safety net
        self._refresh()
        # Select the newly-created row by identifier if possible
        identifier = dialog.values().get("identifier")
        if identifier:
            self.select_record_by_identifier(identifier)
```

(`dialog.values()` is illustrative — use whatever method `EntityCrudDialog` exposes for retrieving the saved field values, or capture the identifier in a member variable inside the dialog and expose a getter.)

### Extend `_build_context_menu` from slice B

Slice B added `Go to references` and `Copy identifier` to row context. Extend the whitespace branch to add `New session`:

```python
def _build_context_menu(self, index: QModelIndex) -> QMenu:
    menu = QMenu(self)
    if not index.isValid():
        new_action = menu.addAction("New session")
        new_action.triggered.connect(self._on_new_session_clicked)
        return menu

    # Row context — unchanged from slice B
    record = self._record_at_index(index)
    if record:
        go_refs = menu.addAction("Go to references")
        go_refs.triggered.connect(lambda: self._show_references_for(index))
        copy_id = menu.addAction("Copy identifier")
        copy_id.triggered.connect(
            lambda: QApplication.clipboard().setText(record["identifier"])
        )
    return menu
```

The row context branch must NOT include any Edit / Delete / Restore action — append-only stays strict.

### Verify NO Edit / Delete / Restore button on detail pane

Read the existing Sessions detail-pane code (likely in the same `panels/sessions.py` file). Confirm it does not include any Edit, Delete, or Restore button. If any such button was added in error during a previous slice, remove it and add a regression test.

### Tests

Update or add to `tests/crmbuilder_v2/ui/test_sessions_panel_writes.py`:

- `test_new_session_button_renders_in_toolbar`
- `test_new_session_button_opens_create_dialog`
- `test_create_dialog_save_creates_session_and_refreshes_panel`
- `test_create_dialog_save_selects_new_row_by_identifier`
- `test_context_menu_whitespace_includes_new_session`
- `test_context_menu_row_does_not_include_edit_or_delete` — explicit assertion that the row context menu has only `Go to references` and `Copy identifier`.
- `test_detail_pane_has_no_edit_button` — explicit assertion no Edit button is rendered.
- `test_detail_pane_has_no_delete_button` — explicit assertion no Delete button is rendered.
- `test_detail_pane_has_no_restore_button` — explicit assertion no Restore button is rendered.

The slice-B `test_context_menus.py` Sessions tests need updating to assert the extended whitespace action set:

- Whitespace context: `["New session"]`
- Row context: `["Go to references", "Copy identifier"]` (unchanged)

## Step 5 — Run tests

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: ~554 tests from slice C + ~25 new tests across this slice. Total ~579 passing.

If any earlier-slice test breaks: debug. The session create dialog and panel additions should not affect any existing read-only behavior on Sessions or any other panel.

### Manual verification

Beyond automated tests, run the application (`uv run crmbuilder-v2-ui`) and verify:

1. Sessions panel shows a `New Session` toolbar button.
2. Clicking opens the dialog with identifier auto-filled, session_date defaulted to today, status defaulted to Complete, and placeholder text on `topics_covered` and `conversation_reference`.
3. The identifier is read-only (cannot be edited).
4. Leaving a required field empty surfaces inline error on Save.
5. `in_flight_at_end` empty allowed; Save succeeds.
6. After successful save, the panel refreshes, and the new row is selected.
7. Right-click on a session row surfaces only `Go to references` and `Copy identifier` — no Edit, no Delete, no Restore.
8. Right-click on whitespace in the panel surfaces `New session`.
9. Sessions detail pane shows no Edit, no Delete, no Restore buttons.
10. Writing a session via `curl POST /sessions` while the UI is open causes the panel to refresh (file-watch).

### Optional dogfood test

If you want to exercise the slice end-to-end, the prompt itself can be the source for a fresh session record. After all tests pass and the manual verification is clean, open `New Session` and use the dialog to author a small placeholder session — title `"SES-D-test"`, status `"Complete"`, etc. Confirm the row appears. Then revert (delete the row directly via `curl DELETE` or a small script) before commit. This is optional but a useful real-world sanity check.

## Step 6 — Commit, push, report

One commit (or two if a storage-layer commit was needed in Step 1):

```
v2: ui v0.3 — session create dialog + Sessions panel write integration
```

Push:

```
git pull --rebase origin main
git push origin main
```

## Acceptance gates

- [ ] `POST /sessions` endpoint exists and accepts the nine-field payload.
- [ ] Refresh service map includes `sessions`.
- [ ] `dialogs/session_create.py` houses `SessionCreateDialog` with the nine-field schema in the documented order.
- [ ] Identifier is auto-assigned at dialog-open time and is read-only.
- [ ] `session_date` defaults to today; `status` defaults to `Complete`.
- [ ] `topics_covered` and `conversation_reference` placeholders hint at DEC-025 conventions.
- [ ] `in_flight_at_end` is the only optional field.
- [ ] Sessions panel shows `New Session` toolbar button; whitespace right-click shows `New session`.
- [ ] Sessions panel detail pane shows NO Edit, Delete, or Restore button.
- [ ] Sessions panel row right-click shows only `Go to references` and `Copy identifier` — no Edit, Delete, or Restore action.
- [ ] `client.py` extended with `create_session`.
- [ ] Manual verification cases all pass.
- [ ] Full v2 test suite passes (~579 tests).
- [ ] One commit pushed (plus optional storage commit).

## Out of slice

- Any session edit or delete affordance — strictly forbidden per DEC-013 / DEC-034.
- "Save draft" mode for in-progress sessions — strictly forbidden.
- Broadening sessions to non-Claude.ai conversations — out of v0.3 scope.
- Closeout artifacts (SES-009, status v1.0, About 0.3.0, README) — slice E.

## Constraints

- Append-only is a hard governance constraint. No code path in this slice introduces any way to edit, delete, restore, or draft-save a session record.
- The dialog is fill-everything-once-and-save. The user composes content outside the dialog if needed; the UI write happens once.
- The identifier auto-assignment algorithm reads existing sessions at dialog-open time. Cached lists from the panel are acceptable; the algorithm tolerates a stale cache by retrying once on identifier collision.
- The dialog must use the existing `EntityCrudDialog` base. If the base needs minor extensions (e.g., per-field placeholder support if not already present, read-only field rendering if not already present), add them as part of slice D and ensure they don't break existing dialogs.

## Reporting

After all six steps complete, report:

- Confirmation that all acceptance gates above are checked.
- Any storage-layer additions made in Step 1.
- Any extensions to `EntityCrudDialog` required to support the schema (placeholder text per field, read-only field rendering).
- The final test count.
- Any deviations or surprises.
- Any open items for slice E.

Slice E (closeout) is the next slice. Its prompt is `CLAUDE-CODE-PROMPT-v2-ui-v0.3-E-closeout.md`.
