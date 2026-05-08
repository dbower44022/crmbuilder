# CLAUDE-CODE-PROMPT-v2-ui-G-decisions-crud

**Last Updated:** 05-08-26 23:30
**Series:** v2-ui
**Slice:** G (7 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-F (commit `59a8c01`)

## Purpose

Slice G delivers the only write surface in v0.1: full create/edit/delete operations for decisions. After this slice:

- A "New Decision" button in the Decisions panel toolbar opens a modal create dialog with all eleven inputs per PRD section 4.7. Saving sends `POST /decisions` and on success closes the dialog, refreshes the panel, and selects the newly-created row.
- "Edit" and "Delete" buttons appear in the Decisions detail pane (visible when a row is selected). Edit opens a pre-populated dialog with the identifier read-only; saving sends a partial-update `PATCH` with only the fields that changed. Delete opens a confirmation dialog; confirming sends `DELETE`.
- Validation errors from the API surface inline on the offending field. When the API's error envelope carries a `field` key, the corresponding form widget shows a red-text error label beneath it; the dialog stays open. When `field` is absent, a generic error dialog appears.
- Conflict errors (HTTP 409) on create surface as inline errors on the Identifier field ("An identifier with this value already exists."). Conflict errors on delete (the decision is referenced by other records) surface as a dialog-level error with only a Cancel button.
- A new generic `ErrorDialog` is the catchall for unexpected errors and 5xx responses.
- The status dropdown is bound to the `DECISION_STATUSES` vocabulary (`Active`, `Superseded`, `Withdrawn`) imported directly from the access layer's `vocab.py`. Single source of truth.

After this slice, the v0.1 acceptance gate set is closed except for the polish slice. PRD AC#7 (create), AC#8 (edit), AC#9 (delete), AC#10 (inline validation) are all addressed.

## Project context

Slice F landed at commit `59a8c01`. The file-watch refresh service is live: any successful API write produces a refresh on the visible panel within ~500ms regardless of who initiated it. This means slice G's dialogs do not strictly need explicit panel refresh after a successful write — the watcher will catch it. However, the recommended pattern is still explicit refresh + select-by-identifier on create, because:

- The user expects to see the new/edited row immediately, not after a debounce window.
- For create, selecting the newly-created identifier requires knowing it; the explicit `panel.select_record_by_identifier(new_id)` (which already includes a refresh-then-select via `_pending_select_identifier` from slice D) is the natural mechanism.
- For edit, the currently-selected record gains updated fields; an explicit refresh keeps the detail pane in sync immediately.
- For delete, the deletion is its own visual confirmation (row disappears); explicit refresh just makes the timing crisp.

The implementation plan section 4 / Step G specifies the deliverables. PRD sections 4.7, 4.8, 4.9, and 4.11 are the authoritative behavior specs.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. **Note:** slice F's manual verification may have left audit-log entries in the local DB. If `git diff PRDs/product/crmbuilder-v2/db-export/change_log.json` shows changes from those test writes (DEC-099, DEC-091..DEC-095, RSK-099, etc.), `git checkout` that file before starting slice G so the snapshot stays clean.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice F is on `main`: `git log --oneline -3` should show `59a8c01` (slice F file-watch) at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 198 tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.7 (create), 4.8 (edit), 4.9 (delete), 4.11 (error matrix).
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step G in section 4.
4. Slice F's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — to confirm dialog refresh-on-success is decoupled from file-watch path.
5. Slice C/D code touching the decisions write path:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/exceptions.py` — `ValidationError.field_errors()` is the API for inline field error display.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` — slice G extends this.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py` — slice G adds buttons.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_create.py`, `decision_edit.py`, `decision_delete.py`, `error.py` — currently docstring stubs; slice G fills them in.
6. Storage system surface (read-only — do not modify):
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `DECISION_STATUSES = frozenset({"Active", "Superseded", "Withdrawn"})`.
   - `crmbuilder-v2/src/crmbuilder_v2/api/schemas.py` — `DecisionCreateIn` and `DecisionUpdateIn` define the wire shape. All update fields are optional (None means "don't touch"); empty string means "set to empty".
   - `crmbuilder-v2/src/crmbuilder_v2/api/errors.py` — confirms 400 ValidationError carries a list of `{code, field, message}` items.
7. **Tier 2 orientation** (per DEC-011): current charter, current status, SES-004, DEC-020 (write scope: decisions only).

## Step 1 — Extend `StorageClient` with write methods

Add three new methods to `client.py`. Existing methods are unchanged.

```python
# --- decisions (write) ---
def create_decision(self, body: dict) -> dict:
    """POST /decisions. Returns the created record dict.

    Raises ValidationError on 400, ConflictError on 409 (duplicate
    identifier), other StorageClientError subclasses per the standard
    error matrix.
    """
    return self._request("POST", "/decisions", json=body)

def update_decision(self, identifier: str, body: dict) -> dict:
    """PATCH /decisions/{identifier}. Body should contain only the
    fields that changed. Returns the updated record dict.

    Raises ValidationError on 400, NotFoundError on 404 (decision was
    deleted by another writer between read and update), ConflictError
    on 409 (e.g., supersedes target doesn't exist).
    """
    return self._request("PATCH", f"/decisions/{identifier}", json=body)

def delete_decision(self, identifier: str) -> dict:
    """DELETE /decisions/{identifier}. Returns the API's response data.

    Raises NotFoundError on 404, ConflictError on 409 (decision is
    referenced by other records).
    """
    return self._request("DELETE", f"/decisions/{identifier}")
```

### Tests

Extend `tests/crmbuilder_v2/ui/test_client.py`:

- `create_decision({...})` returns the created dict on 201.
- `create_decision` with a duplicate identifier raises `ConflictError`.
- `create_decision` with invalid status raises `ValidationError`; `field_errors()` returns the right mapping.
- `update_decision("DEC-001", {"title": "new"})` returns the updated dict.
- `update_decision` with a non-existent identifier raises `NotFoundError`.
- `delete_decision("DEC-001")` returns the API response.
- `delete_decision` with a referenced decision raises `ConflictError`.

Use `httpx.MockTransport` with handler functions matching response codes per the existing test patterns from slice C and D.

## Step 2 — Implement `dialogs/error.py` (generic error dialog)

A reusable modal dialog for unexpected errors and any error case where inline-on-field display isn't applicable.

```python
class ErrorDialog(QDialog):
    """Generic modal error dialog.

    Used by the decision dialogs for:
    * 5xx ServerError responses
    * 422 RequestShapeError responses (programmer error)
    * Any 400/409 where the API's error envelope does NOT carry a
      `field` key
    * Any unexpected exception caught while submitting

    Constructor signature is intentionally permissive so dialogs can
    pass through whatever they have.
    """

    def __init__(
        self,
        title: str,
        message: str,
        detail: str | None = None,
        parent: QWidget | None = None,
    ) -> None: ...
```

### Visual

- Modal `QDialog` with the navy accent in the header (consistent with the rest of the app's styling stub).
- Title at top (bold, larger font).
- Message in the body (wrap text, accommodates 2-4 lines).
- If `detail` is provided, an expandable "Details" disclosure showing the detail text in a read-only `QPlainTextEdit`. Default collapsed.
- An "OK" button at the bottom that closes the dialog.

### Tests

`tests/crmbuilder_v2/ui/test_error_dialog.py` (new) or extension of an existing dialog test file:

- Construct without `detail` — assert the disclosure widget is absent.
- Construct with `detail` — assert the disclosure widget is present, default collapsed.
- OK button closes the dialog.

## Step 3 — Implement `dialogs/decision_create.py`

The full create dialog per PRD section 4.7.

### Class shape

```python
class DecisionCreateDialog(QDialog):
    """Modal create-decision dialog. Per PRD §4.7."""

    def __init__(self, client: StorageClient, parent: QWidget | None = None) -> None: ...

    def created_identifier(self) -> str | None:
        """The identifier of the created record after .accept(),
        or None if the dialog was cancelled or never accepted.
        """
```

### Fields

In a `QFormLayout` inside the dialog:

| Order | Label | Widget | Required | Notes |
|---|---|---|---|---|
| 1 | Identifier | QLineEdit | Yes | Placeholder: `DEC-NNN`. Widely used; first focus. |
| 2 | Title | QLineEdit | Yes | |
| 3 | Decision Date | QLineEdit | Yes | Placeholder: `MM-DD-YY`. Plain text — no calendar widget for v0.1. |
| 4 | Status | QComboBox | Yes | Items from `DECISION_STATUSES` (sorted alphabetically: Active, Superseded, Withdrawn). Default selection: `Active`. |
| 5 | Context | QPlainTextEdit | No | Min height ~80px; expandable. |
| 6 | Decision | QPlainTextEdit | No | Same. |
| 7 | Rationale | QPlainTextEdit | No | Same. |
| 8 | Alternatives Considered | QPlainTextEdit | No | Same. |
| 9 | Consequences | QPlainTextEdit | No | Same. |
| 10 | Supersedes | QLineEdit | No | Placeholder: `DEC-NNN or empty`. |
| 11 | Superseded By | QLineEdit | No | Same. |

Each field has an inline error label slot beneath it (a small `QLabel`, hidden by default, red text for errors, populated when the API returns a validation error keyed to that field).

### Buttons

- **Save** — primary action. Triggers form submission via worker.
- **Cancel** — secondary. Calls `self.reject()`.

Use `QDialogButtonBox` with `Save` and `Cancel` standard buttons, or build custom buttons if cleaner.

### Save behavior

1. **Client-side required-field check.** Before submitting, verify identifier, title, decision_date, status are non-empty. If any are missing, populate the inline error label on the offending field with `"This field is required."`; dialog stays open. No API call made.

2. **Construct request body.** Skip `supersedes` and `superseded_by` if empty (so the API treats them as None / not-set; the API's create input accepts None for both). Include all other fields (empty strings for the long-text fields are fine — that's the API's default).

3. **Submit through a worker.** Spawn via `run_in_thread` (same pattern as panel refreshes). Disable the Save button during submission to prevent double-clicks.

4. **On success (HTTP 201):**
   - Capture the created record's identifier from the response (the response data has the canonical identifier — same as input but normalize via the API).
   - Store on `self._created_identifier`.
   - Call `self.accept()`.

5. **On `ValidationError`:**
   - Iterate `exc.field_errors()`. For each `{field: message}`, populate the corresponding inline error label.
   - For any error in `exc.errors` whose `field` is None or doesn't match a form field, surface via the generic `ErrorDialog`.
   - Re-enable the Save button. Dialog stays open.

6. **On `ConflictError`:**
   - The most likely cause is duplicate identifier. Populate the Identifier field's inline error with `"An identifier with this value already exists."`.
   - Re-enable Save.

7. **On `StorageConnectionError`:**
   - Close the dialog with `self.reject()`. The MainWindow's existing crash-banner path (panels' `connection_lost` and lifecycle's `crashed`) will take over.
   - Do NOT show an error dialog from here — the banner is the right surface.

8. **On any other `StorageClientError`:**
   - Show the generic `ErrorDialog` with title `"Could not create decision"`, message `str(exc)`, and the exception's repr as detail.
   - Re-enable Save. Dialog stays open.

### Inline error display

Each form field has a paired `QLabel` for inline errors. When an error is shown, set:
- Color: navy `#1F3864` outline on the input + red text on the label (or red border + red text — implementer's choice).
- Visible: True.
- Text: the error message.

When the user starts editing the field again, clear the inline error (connect to the field's textChanged signal). This way the user sees their fix immediately reflected.

### Tests

`tests/crmbuilder_v2/ui/test_decision_create_dialog.py` (new):

1. **Construction.** Construct with stub client; assert all 11 fields are present with correct widget types; assert button box exists.
2. **Status dropdown is sourced from vocab.** Assert the dropdown items exactly match the `DECISION_STATUSES` set (sorted alphabetically) and the default selection is "Active".
3. **Required-field check blocks empty submissions.** Click Save with required fields empty; assert no API call was made and the inline error labels show "This field is required." on the four required fields.
4. **Successful create accepts the dialog.** Stub `client.create_decision` to return `{"identifier": "DEC-100", ...}`. Fill required fields, click Save, `qtbot.waitSignal(dialog.accepted)`, assert `dialog.created_identifier() == "DEC-100"`.
5. **400 ValidationError populates inline errors.** Stub the client to raise `ValidationError` with `field_errors() = {"status": "Invalid status value"}`. Fill the form, click Save. Assert the Status field's inline error shows the message; dialog is not accepted.
6. **409 ConflictError populates the Identifier inline error.** Stub the client to raise `ConflictError`. Click Save. Assert the Identifier field's inline error message is shown.
7. **StorageConnectionError closes the dialog via reject.** Stub the client to raise `StorageConnectionError`. Click Save. Assert `qtbot.waitSignal(dialog.rejected)` succeeds.
8. **5xx ServerError opens the generic error dialog.** Stub the client to raise `ServerError`. Click Save. Assert an ErrorDialog appears (intercept via Qt's modal-tracking or inspect children); the create dialog stays open.

## Step 4 — Implement `dialogs/decision_edit.py`

Same shape as `DecisionCreateDialog` with three differences. Maximum reuse — consider factoring a shared base class `_DecisionFormDialog` if the shared code exceeds ~150 lines, but otherwise duplicate is acceptable for clarity.

### Differences from create

1. **Constructor takes the existing record dict.**
   ```python
   def __init__(self, client: StorageClient, record: dict, parent: QWidget | None = None) -> None: ...
   ```
   The record is fetched fresh from the API by the caller (the panel) right before opening the dialog; it has all current values.

2. **Identifier field is read-only.** Construct as `QLineEdit` with `setReadOnly(True)`; visually distinct (slightly grayed). Pre-populated with `record["identifier"]`.

3. **Save sends a partial PATCH with only changed fields.**
   - On dialog open, store the initial values (a snapshot of the record's relevant fields).
   - On Save, compare current values to initial. Build a body dict containing only fields where current != initial.
   - For `supersedes` and `superseded_by`, the comparison is between `record["supersedes_identifier"]` (current API-enriched value, or empty string if None) and the dialog's current text. If unchanged, omit from the body. If changed (including from "DEC-005" to empty, which means clear), include with the new value (empty string for clear).
   - If the body is empty (no changes), close the dialog with `accept()` immediately without making an API call. Optionally show a brief "No changes" status — minimal is fine.
   - Otherwise submit `client.update_decision(identifier, body)` through a worker.

4. **Window title and Save button label.**
   - Title: `"Edit decision"` (or just include the identifier: `"Edit DEC-018"`).
   - Save button label: just `"Save"`.

### Error handling

Same as create, with one addition:
- **`NotFoundError` (404):** The decision was deleted by another writer between when the panel selected it and when we submitted the PATCH. Show the generic `ErrorDialog` with title `"Decision not found"`, message `"This decision was deleted while the dialog was open. The list will refresh."`, then close the dialog (via `accept()` rather than reject — accepting indicates the operation completed; the panel's refresh handles the cleanup). The file watcher will pick up the deletion within the debounce window, but call `panel.refresh()` from the panel's edit-success handler unconditionally to keep the timing crisp.

### Tests

`tests/crmbuilder_v2/ui/test_decision_edit_dialog.py` (new):

1. **Construction pre-populates from the record.** Pass a record dict; assert each form field shows the corresponding value.
2. **Identifier is read-only.** Assert the QLineEdit is `isReadOnly()`.
3. **No changes → empty PATCH not sent.** Open dialog, click Save without modifying. Assert `client.update_decision` was NOT called and the dialog was accepted.
4. **Single field change sends a one-field PATCH.** Modify only `title`. Click Save. Assert `update_decision` was called with body `{"title": "new value"}` (only that one key).
5. **Clearing supersedes sends empty string.** Initial record has `supersedes_identifier="DEC-005"`. User clears the supersedes field. Click Save. Assert body is `{"supersedes": ""}`.
6. **Setting supersedes from empty sends new value.** Initial `supersedes_identifier=None`. User enters "DEC-007". Click Save. Assert body is `{"supersedes": "DEC-007"}`.
7. **404 NotFoundError shows error dialog and accepts.** Stub `update_decision` to raise `NotFoundError`. Click Save. Assert ErrorDialog appears AND the edit dialog accepts (closes with `Accepted`).
8. **400 ValidationError handled inline (same as create).** Quick smoke test that the same handler logic applies.

## Step 5 — Implement `dialogs/decision_delete.py`

Confirmation dialog for deletion. PRD section 4.9.

### Class shape

```python
class DecisionDeleteDialog(QDialog):
    """Confirmation dialog for deleting a decision. Per PRD §4.9."""

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None: ...
```

### Visual

- Modal. Title `"Delete decision"`.
- Body text: `f"Delete {identifier} — {title}? This cannot be undone."` (matches PRD section 4.9 example).
- Buttons: `Delete` (destructive) and `Cancel`. Cancel is the default focus.

The Delete button can be styled to indicate destruction — red text, or a red border, or a red background. Cosmetic; minimal is fine.

### Confirm behavior

- Click Delete → spawn worker calling `client.delete_decision(identifier)`. Disable Delete button during submission.
- **On success (HTTP 200):**
  - `self.accept()`.
- **On `ConflictError` (HTTP 409):** This is the documented case — the decision is referenced by other records. Replace the dialog's body text with a richer message: `f"{identifier} cannot be deleted because it is referenced by other records: {detail}."`. Hide the Delete button; only Cancel remains. The user must dismiss with Cancel.
  - The `detail` from the error envelope (when present) lists the referencing records. If available, render. If not, just say "other records".
- **On `NotFoundError`:** The decision was already deleted by another writer. Treat this as success: show a brief banner-style message in the dialog ("Already deleted; refreshing.") and `self.accept()`. The panel's refresh handles cleanup.
- **On `StorageConnectionError`:** Close the dialog via `reject()`; banner takes over.
- **On any other error:** Show the generic `ErrorDialog`; dialog stays open with Delete still available for retry.

### Tests

`tests/crmbuilder_v2/ui/test_decision_delete_dialog.py` (new):

1. **Construction shows identifier and title.** Pass `("DEC-007", "Universal references pattern...")`; assert the body text includes both.
2. **Successful delete accepts.** Stub `client.delete_decision` to return `{"deleted": True}`. Click Delete; `qtbot.waitSignal(dialog.accepted)`.
3. **Conflict shows reference detail and removes Delete button.** Stub to raise `ConflictError(message="referenced by SES-004, REF-12")`. Click Delete; assert the Delete button is hidden and the body text contains "referenced".
4. **NotFoundError accepts (treats as already deleted).** Stub to raise `NotFoundError`. Click Delete; assert dialog accepts.

## Step 6 — Wire dialogs into the Decisions panel

`panels/decisions.py` already has the slice-D structure: full PRD-§4.6 columns, structured detail pane, inbound-references rendering. Slice G adds three buttons.

### Toolbar "New Decision" button

In the panel's `__init__`, add a `QPushButton("New Decision")` to `self._action_layout` (the existing toolbar slot from the base class). Connect its `clicked` signal to a method:

```python
def _on_new_decision_clicked(self) -> None:
    dialog = DecisionCreateDialog(self._client, self)
    if dialog.exec() == QDialog.Accepted:
        new_id = dialog.created_identifier()
        if new_id:
            # Triggers refresh + select via _pending_select_identifier (slice D).
            self.select_record_by_identifier(new_id)
```

### Detail pane "Edit" and "Delete" buttons

The existing `render_detail(record, extras)` produces a `QFormLayout` inside a `QScrollArea`. Add a small button strip at the top of the form:

```
┌──────────────────────────────────────────────────────┐
│  [Edit]   [Delete]                                   │  ← button strip
├──────────────────────────────────────────────────────┤
│  Identifier:  DEC-018                                │
│  Title:       UI is a standalone application…        │
│  ...                                                 │
└──────────────────────────────────────────────────────┘
```

Buttons get the current record's identifier and title via closures (the record is in scope when constructing the strip).

```python
edit_btn.clicked.connect(lambda: self._on_edit_clicked(record))
delete_btn.clicked.connect(lambda: self._on_delete_clicked(record))
```

### `_on_edit_clicked`

```python
def _on_edit_clicked(self, record: dict) -> None:
    # Re-fetch the record fresh, in case it changed since the panel
    # last fetched. Cheap; one HTTP request.
    try:
        fresh = self._client.get_decision(record["identifier"])
    except NotFoundError:
        # Already deleted; just refresh the panel.
        self.refresh()
        return
    except StorageClientError:
        # Connection or server error — surface via generic error dialog.
        ErrorDialog(
            "Could not load decision",
            "Could not load the latest version of this decision.",
            parent=self,
        ).exec()
        return

    dialog = DecisionEditDialog(self._client, fresh, self)
    if dialog.exec() == QDialog.Accepted:
        self.refresh()
```

The fresh fetch happens on the UI thread inside the click handler. It's a single HTTP request with a 5-second timeout (the StorageClient's default); acceptable on the UI thread for a click action. If this becomes laggy in practice, slice H polish can wrap it in a worker with a "Loading…" overlay, but for v0.1 the simple approach is correct.

### `_on_delete_clicked`

```python
def _on_delete_clicked(self, record: dict) -> None:
    dialog = DecisionDeleteDialog(
        self._client,
        record["identifier"],
        record["title"],
        self,
    )
    if dialog.exec() == QDialog.Accepted:
        self.refresh()
```

### Disable Edit/Delete when no record is selected

The button strip is rendered as part of `render_detail`, which only runs when a record is selected. So the buttons only exist when a record is selected — no enable/disable logic needed. The placeholder shown when no row is selected (the `"Select a record to view detail"` widget from the base class) does not contain Edit/Delete buttons. Clean.

## Step 7 — Tests for the panel integration

Add `tests/crmbuilder_v2/ui/test_decisions_panel_writes.py` (new):

1. **Toolbar New Decision button opens the create dialog.** Construct `DecisionsPanel`; locate the "New Decision" button; click; assert a `DecisionCreateDialog` instance is shown (intercept via Qt's QApplication.activeModalWidget or by patching the dialog class).
2. **Successful create triggers select_record_by_identifier.** Patch the dialog to immediately accept and return identifier "DEC-100". Assert `panel.select_record_by_identifier("DEC-100")` was called.
3. **Detail pane has Edit and Delete buttons when a record is selected.** Populate the panel with stub data; select a row; render the detail; assert the rendered widget has buttons named "Edit" and "Delete".
4. **Edit click fetches the fresh record and opens the edit dialog.** Stub `client.get_decision` to return a different version of the record (e.g., a newer title). Click Edit; assert `client.get_decision` was called with the right identifier; assert the EditDialog is constructed with the fresh dict.
5. **Successful edit triggers panel.refresh().** Patch the edit dialog to accept; assert `panel.refresh()` was called after.
6. **Delete click opens the delete dialog with identifier and title.** Click Delete; assert the DeleteDialog is constructed with the record's identifier and title.
7. **Successful delete triggers panel.refresh().** Patch the delete dialog to accept; assert `panel.refresh()` was called.

The existing tests must continue to pass.

## Step 8 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 198 prior tests + ~30 new tests across steps 1, 2, 3, 4, 5, 7. Estimated ~225-230 passing, all green.

Manual verification (recommended):

1. **Create flow.** Launch UI, navigate to Decisions, click "New Decision". Fill all required fields; click Save. Confirm the dialog closes, the new row appears, and is selected. Open the detail pane — confirm fields match what you entered.
2. **Create with validation error.** Click "New Decision", leave Status empty (or set it to a value not in vocab — though the dropdown prevents this; instead leave Decision Date in wrong format). Click Save. Confirm the inline error label appears on the right field; dialog stays open. Fix the error; click Save again — confirm save succeeds.
3. **Create with duplicate identifier.** Click "New Decision", enter an existing identifier (e.g., DEC-001). Fill required fields. Click Save. Confirm inline error on Identifier: "An identifier with this value already exists."
4. **Edit flow.** Select a decision; click Edit; modify the Title; click Save. Confirm the row in the table shows the new title and the detail pane updates.
5. **Edit with no changes.** Open Edit; click Save without changing anything. Confirm the dialog closes immediately; no flicker; no API call.
6. **Delete flow.** Select a decision; click Delete; confirm the dialog body shows the identifier and title; click Delete. Confirm the row disappears and the detail pane clears.
7. **Delete a referenced decision.** Select a decision that has inbound references (e.g., one of DEC-018 through DEC-024 — they all have decided_in from SES-004). Click Delete. Confirm the conflict path: dialog body shows "cannot be deleted because it is referenced…"; Delete button is hidden; only Cancel remains.
8. **Watcher + write integration.** Open another UI window (or use curl) and DELETE a decision that's currently visible in the first UI's table. Confirm within ~1 second the row disappears (file-watch path).

Commit shape: single commit covering all of slice G.

```
v2: ui decisions CRUD — create, edit, delete dialogs

Implements slice G of the v2-ui series. Closes PRD AC#7 (create),
AC#8 (edit), AC#9 (delete), and AC#10 (inline validation) per PRD
§4.7, §4.8, §4.9, and §4.11.

- DecisionCreateDialog (dialogs/decision_create.py): modal create
  dialog with all 11 fields per PRD §4.7. Status dropdown sourced
  from access-layer DECISION_STATUSES vocab. Required-field client-
  side check; API errors routed inline (validation) or to the
  generic error dialog (5xx, 422, no-field 400). Conflict on
  identifier → inline on Identifier field.

- DecisionEditDialog (dialogs/decision_edit.py): same shape as
  create with identifier read-only and partial-PATCH semantics.
  Tracks initial values; sends only fields that changed. Empty
  string clears a previously-set field. NotFoundError treated as
  "already deleted by another writer" with refresh-and-accept.

- DecisionDeleteDialog (dialogs/decision_delete.py): confirmation
  dialog showing identifier and title. ConflictError on referenced
  decisions hides the Delete button and explains the conflict.
  NotFoundError treated as "already deleted; refreshing".

- ErrorDialog (dialogs/error.py): generic modal for 5xx, 422, and
  no-field 400 responses. Optional collapsible detail section.

- StorageClient extended with create_decision, update_decision,
  delete_decision.

- DecisionsPanel: "New Decision" button in toolbar action layout;
  Edit and Delete buttons in the detail pane button strip rendered
  by render_detail. Edit re-fetches the record fresh before opening
  the dialog. Successful create calls select_record_by_identifier
  on the new ID. Successful edit/delete call panel.refresh().

~30 new tests covering client write methods, the four dialog
classes, and the panel integration.

Out of slice: write surfaces for any other entity (deferred to
v0.2). Polish slice H closes v0.1.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. The "New Decision" button in the Decisions panel toolbar opens the create dialog. Filling required fields and clicking Save creates the record, closes the dialog, refreshes the panel, and selects the new row. (PRD AC#7.)
2. Editing a selected decision via the Edit button opens a pre-populated dialog. Modifying a field and clicking Save updates the record. The panel reflects the change. (PRD AC#8.)
3. Deleting a selected decision via the Delete button opens a confirmation dialog. Confirming deletes the record. The panel reflects the deletion. (PRD AC#9.)
4. Submitting a duplicate identifier on create surfaces an inline error on the Identifier field; dialog stays open. Submitting an invalid status (via API contract violation, since the dropdown is locked) surfaces inline on Status. (PRD AC#10.)
5. Submitting an edit with no changes closes the dialog immediately without making an API call.
6. Deleting a decision that is referenced by other records surfaces the conflict explanation in the dialog body and removes the Delete button.
7. The full v2 test suite passes, including all new tests from steps 1, 2, 3, 4, 5, and 7.
8. One commit on `origin/main` with the message shape above.

## Out of slice

The following are explicitly NOT in scope for slice G:

- Create/edit/delete for any entity other than decisions. Write surfaces for sessions, risks, planning items, topics, charter, status, references all defer to v0.2.
- Bulk operations (multi-row select + delete, etc.).
- Undo. Once a delete is confirmed, it's gone.
- Optimistic concurrency control (e.g., version-stamped PATCH with conflict detection if another writer updated the record). v0.1 is last-write-wins per PRD risk register.
- Calendar widget for the Decision Date input. Plain text per slice spec; v0.2 polish if desired.
- Polish — slice H.

## Constraints

- **No new external dependencies.**
- **Do not modify the API or access-layer code.** If a write semantic is wrong (e.g., empty-string clear isn't actually accepted by the access layer), surface as an open question — do not patch the API.
- **Do not modify schema, migrations, or vocab.** Import vocab values, but don't change the values themselves.
- **Do not modify the lifecycle, refresh service, or any other panel.**
- **Keep slice C's QThread-subclass Worker pattern.** All API calls in dialogs go through `run_in_thread`.
- **Don't add a "Save and Add Another" button.** v0.2 if needed.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the eight gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum scenarios 1, 4, 6, and 7. Scenarios 2, 3, 5, 8 recommended.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for slice H polish or v0.2.
- **What slice H will need** — friction points discovered during D/E/F/G that the polish slice should address. Specifically: any UX rough edges, the file-watch all-snapshots-rewritten property (potential content-hash fix), and any other items worth attention before v0.1 ships.
