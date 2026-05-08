# CLAUDE-CODE-PROMPT-v2-ui-H-polish-and-styling-stub

**Last Updated:** 05-09-26 09:00
**Series:** v2-ui (final slice)
**Slice:** H (8 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-G (commit `6089ceb`)

## Purpose

Slice H closes v0.1. It packages three groups of changes:

1. **Storage-system fixes** required for v0.1 to ship with correct behavior end-to-end:
   - Decisions become soft-delete: `decisions.delete()` sets `status="Deleted"` instead of physically removing the row. Referential integrity is preserved by construction.
   - `_resolve_decision_id()` treats empty string as "clear FK" rather than "look up empty identifier", so `PATCH /decisions/{id}` with `supersedes=""` correctly clears the link.

2. **UI polish** discovered during D/E/F/G:
   - `RefreshService` content-hash gating eliminates false-positive stale-dot signals from the storage system's all-snapshots-rewritten property.
   - Client-side regex validation for Identifier (DEC-NNN) and Decision Date (MM-DD-YY) catches errors before the API roundtrip.
   - About dialog implementation wired to the `Help → About` menu placeholder.
   - Topics master-list "Parent Topic" cell click-to-navigate (closes a slice E open question).
   - Styling stub refinement (consistent navy accent, error-text color, focus styling).

3. **Closeout governance records** capturing the build:
   - `SES-005` session record summarizing the eight-prompt build.
   - Status update to `phase: "v0.1 complete"`.

After this slice, v0.1 is shipped: standalone PySide6 app with eight read-only entity panels, full CRUD for decisions, file-watch live refresh, lifecycle-managed API subprocess, and the storage-system fixes that make the documented contract correct end-to-end.

## Project context

Slice G landed at commit `6089ceb`. The decisions CRUD dialogs are in place but two storage-side defects make the documented contract non-functional in practice:

- `DELETE /decisions/{id}` does not enforce referential integrity — the dialog's conflict path (body explanation, Delete-button hide) is unreachable. Soft-delete sidesteps this entirely: every delete becomes a status change, references stay valid.
- `PATCH /decisions/{id}` with `supersedes=""` raises `ValidationError` because `_resolve_decision_id` falls through to a SELECT for an empty identifier. Users trying to clear a `supersedes` link see a generic error dialog instead of the field clearing. Fix: special-case empty string at the resolve helper.

Slice F surfaced the `RefreshService` false-positive issue: every API write rewrites all eight snapshot files because the storage system's snapshot exporter rebuilds the full set on every commit. Content-hash gating in the watcher suppresses no-op events.

The implementation plan section 4 / Step H covered polish and the styling stub. Doug (this PRD's owner) has expanded H's scope to fold in the two storage fixes per the conversation that produced this prompt.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. **Note:** if `git diff PRDs/product/crmbuilder-v2/db-export/` shows leftover changes from any earlier slice's manual verification (e.g., DEC-099, DEC-018 was deleted-and-restored in slice G), `git checkout` those files before starting.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice G is on `main`: `git log --oneline -3` should show `6089ceb` (slice G) at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 235 tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.7, 4.8, 4.9 (decisions dialogs); section 5.4 (logging); section 11 (open questions including the About-dialog scope).
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step H in section 4.
4. Storage-system code being modified:
   - `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — `DECISION_STATUSES` constant.
   - `crmbuilder-v2/src/crmbuilder_v2/access/models.py` — Decision's `ck_decision_status` CHECK constraint.
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` — `delete`, `list_all`, `_resolve_decision_id`.
   - `crmbuilder-v2/migrations/versions/0001_initial_schema.py` — pattern for the new migration.
5. UI code being modified:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — content-hash gating.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_create.py`, `decision_edit.py` — validation regexes.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/decision_delete.py` — remove ConflictError branch.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py` — currently a docstring stub.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — wire Help → About.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py` — cell click navigation.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` — refinement.
6. **Tier 2 orientation** (per DEC-011): current charter, current status (now v5), SES-004, DEC-020 (decisions write scope), DEC-022 (file-watch design), DEC-024 (styling deferred).

## Step 1 — Soft-delete migration

Create a new Alembic migration that updates the CHECK constraint on `decisions.status` to include `"Deleted"`.

### File

`crmbuilder-v2/migrations/versions/0002_soft_delete_decisions.py` (new). Naming follows the existing pattern (`0001_initial_schema.py` is the predecessor; revision id should be a stable string like `0002_soft_delete_decisions`).

### Content

```python
"""Add 'Deleted' to allowed decision statuses (soft-delete support).

Revision ID: 0002_soft_delete_decisions
Revises: 0001_initial_schema
Create Date: ...
"""
from alembic import op

revision = "0002_soft_delete_decisions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_constraint("ck_decision_status", type_="check")
        batch_op.create_check_constraint(
            "ck_decision_status",
            "status IN ('Active', 'Superseded', 'Withdrawn', 'Deleted')",
        )


def downgrade() -> None:
    # Pre-condition: no rows with status='Deleted' (otherwise the new
    # constraint cannot be applied). The downgrade does not auto-rewrite
    # those rows; the operator must clean up first.
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_constraint("ck_decision_status", type_="check")
        batch_op.create_check_constraint(
            "ck_decision_status",
            "status IN ('Active', 'Superseded', 'Withdrawn')",
        )
```

`batch_alter_table` is required because SQLite doesn't support direct ALTER on CHECK constraints — Alembic's batch mode does the standard "create new table, copy data, drop old, rename" dance.

### Apply the migration locally

After landing the migration file:

```
uv run alembic upgrade head
```

Verify the constraint is updated by inspecting the schema:

```
uv run python -c "
import sqlite3
con = sqlite3.connect('crmbuilder-v2/data/v2.db')
print(con.execute(\"SELECT sql FROM sqlite_master WHERE name='decisions'\").fetchone()[0])
"
```

The output should show `CHECK (status IN ('Active', 'Superseded', 'Withdrawn', 'Deleted'))`.

## Step 2 — Vocabulary and access-layer changes

### vocab.py

```python
DECISION_STATUSES: frozenset[str] = frozenset(
    {"Active", "Superseded", "Withdrawn", "Deleted"}
)
```

### `decisions.delete()` → soft-delete

In `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py`, replace the existing physical-delete with a status update:

```python
def delete(session: Session, identifier: str) -> dict:
    """Soft-delete: set status to 'Deleted', leave the row in place.

    Referential integrity is preserved by construction — references
    pointing at this decision continue to resolve via get(). The row
    is filtered out of list_all() by default, so the UI sees the row
    disappear from the decisions list, matching the pre-soft-delete
    user experience.
    """
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.status == "Deleted":
        # Idempotent: deleting an already-deleted record is a no-op.
        return _enrich(session, row)
    before = _enrich(session, row)
    row.status = "Deleted"
    session.flush()
    after = _enrich(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        change_type="update",
        record_id=row.id,
        record_identifier=row.identifier,
        before=before,
        after=after,
    )
    return after
```

Note that `change_type="update"` rather than `"delete"` reflects the actual operation now. The change_log audit trail accurately records that this was a status change. If a future need wants to surface "this was a soft-delete" semantically in the audit log, that's a separate enhancement.

### `decisions.list_all()` → filter out Deleted

```python
def list_all(session: Session, *, include_deleted: bool = False) -> list[dict]:
    stmt = select(Decision).order_by(Decision.identifier)
    if not include_deleted:
        stmt = stmt.where(Decision.status != "Deleted")
    rows = session.scalars(stmt).all()
    return [_enrich(session, r) for r in rows]
```

The `include_deleted` parameter is for future callers who may want to see the full history. v0.1's UI does not pass it; default behavior excludes Deleted.

`get()` is unchanged — it returns the record regardless of status. This is what makes reference-link navigation continue to work (clicking "Decided in: SES-X" then back to a decision that was later soft-deleted resolves successfully and the detail pane shows `Status: Deleted`).

### `_resolve_decision_id` → handle empty string

```python
def _resolve_decision_id(session: Session, identifier: str | None) -> int | None:
    """Resolve an identifier string to an integer FK.

    None and empty string both return None. Callers in update() use
    None to mean "don't touch" (the if-not-None guard prevents the
    assignment) and empty string to mean "clear the FK" (the guard
    fires; this helper returns None; the caller assigns None to the
    foreign-key column).
    """
    if identifier is None or identifier == "":
        return None
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise ValidationError(
            [FieldError("supersedes_or_superseded_by", "not_found",
                        f"decision {identifier!r} does not exist")]
        )
    return row.id
```

This is the only change to `update()`'s contract — it now accepts `supersedes=""` as "clear the link."

## Step 3 — Storage tests

Add or extend tests in `tests/crmbuilder_v2/access/test_decisions.py`:

1. **`delete` sets status to Deleted instead of physically removing.** After `delete("DEC-X")`, the row still exists in the database, has `status="Deleted"`, and `get("DEC-X")` returns it.
2. **`list_all()` excludes Deleted by default.** Create two decisions, delete one. `list_all()` returns one record.
3. **`list_all(include_deleted=True)` includes Deleted.** Same setup, `list_all(include_deleted=True)` returns both.
4. **References to a soft-deleted decision still resolve.** Create a decision and a reference to it. Soft-delete the decision. The reference's source/target identifiers continue to resolve via `get()`.
5. **Re-deleting an already-Deleted decision is a no-op.** No change_log entry for the second delete (or, depending on implementation, exactly one entry where before and after are identical).
6. **`update(supersedes="")` clears the FK.** Create two decisions, set one's supersedes to the other. Then `update(...,  supersedes="")`. The row's `supersedes_id` is now None.
7. **`update(supersedes="DEC-X")` sets the FK.** Create two decisions, update one's supersedes to the other. `supersedes_id` matches the target's id.
8. **`update(supersedes=None)` does not touch the FK.** Pre-existing supersedes value is preserved.
9. **`update(supersedes="DEC-NONEXISTENT")` raises ValidationError.** Lookup-failure path still works.

## Step 4 — UI cleanup for storage changes

The dialog and panel code authored in slice G need targeted cleanup now that the storage semantics are fixed.

### `dialogs/decision_delete.py`

Remove the ConflictError branch — soft-delete never conflicts. The dialog body is now the simple confirmation. Edit:

- Delete the conditional that hides the Delete button on ConflictError.
- Delete the body-replacement logic.
- Catch `ConflictError` in the worker error handler and route to the generic ErrorDialog as a defensive fallback (in case the API ever does return a 409 for some other reason). This is one line.

### `tests/crmbuilder_v2/ui/test_decision_delete_dialog.py`

Remove the test `test_conflict_replaces_body_and_hides_delete_button`. Replace it with a sanity check: `test_conflict_error_shows_generic_error_dialog` that stubs the client to raise ConflictError and asserts the ErrorDialog appears (rather than the body being replaced). This documents the new defensive fallback.

### `dialogs/decision_edit.py`

The edit dialog already handles `supersedes=""` correctly per slice G: it sends an empty string in the PATCH body. With Step 2's fix, the API now accepts this. No code change needed in `decision_edit.py`. **Verify** by running the existing test suite — `tests/crmbuilder_v2/ui/test_decision_edit_dialog.py::test_clearing_supersedes_sends_empty_string` should still pass; the wire format is correct, only the API's response semantics changed.

Add an integration test that exercises the full path: open Edit on a decision with a supersedes link, clear the field, save, verify the API call goes through and the row's supersedes is now empty. This may be added in `tests/crmbuilder_v2/ui/test_decisions_panel_writes.py` or a new integration test file.

## Step 5 — Content-hash gating in `RefreshService`

The current `RefreshService` emits `data_changed(entity_type)` whenever a snapshot file's mtime changes. The storage system rewrites all eight snapshots on every commit, so a single decision write produces eight emissions — and seven of them are no-op rewrites with byte-identical content. This pollutes the staleness-indicator UX.

### Fix

Add a hash cache to `RefreshService`. On each `directoryChanged`, before emitting `data_changed(entity_type)`, compare the new file's hash against the cached hash. If identical, suppress the emission. If different, update the cache and emit.

```python
class RefreshService(QObject):
    ...
    def __init__(self, snapshot_dir: Path, parent: QObject | None = None) -> None:
        ...
        self._content_hashes: dict[str, str] = {}  # filename → hex digest

    def _hash_file(self, path: Path) -> str:
        """SHA-256 hex digest of the file's content. Cheap (~1ms for
        snapshot-sized files). No security context — md5 would also
        be fine; sha256 is just the convenient stdlib default."""
        import hashlib
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    def _baseline_hashes(self) -> None:
        """Populate _content_hashes from the current state of the directory.
        Called once on start()."""
        for filename in _FILENAME_TO_ENTITY_TYPE:
            path = self._snapshot_dir / filename
            if path.exists():
                self._content_hashes[filename] = self._hash_file(path)

    def _on_directory_changed(self, _path: str) -> None:
        # Existing event handler; modify to hash-compare before queueing.
        for filename, entity_type in _FILENAME_TO_ENTITY_TYPE.items():
            path = self._snapshot_dir / filename
            if not path.exists():
                continue
            new_hash = self._hash_file(path)
            old_hash = self._content_hashes.get(filename)
            if new_hash and new_hash != old_hash:
                self._content_hashes[filename] = new_hash
                self._pending_emits.add(entity_type)
                self._debounce_timer.start()
```

The baseline-hash population on `start()` is important: without it, the first `directoryChanged` event after start has no cached hash and treats every file as changed, producing eight emissions on the first event. Computing baseline hashes once at start avoids this.

### Tests

Extend `tests/crmbuilder_v2/ui/test_refresh.py`:

1. **No-op rewrite is suppressed.** Start the service. Write `decisions.json` with content X. Wait for the data_changed emission. Then write `decisions.json` again with the same content X (`path.write_bytes(path.read_bytes())`). Within 2000ms, NO further `data_changed` emission occurs.
2. **Real change still fires.** Start the service. Write `decisions.json` with content X (initial emission), then write `decisions.json` with different content Y. The second write fires `data_changed("decision")`.
3. **Mixed-batch with one real change.** Write `decisions.json` (real change) and `sessions.json`, `risks.json`, `topics.json` etc. all with byte-identical content (no-op rewrites simulating the storage system's burst behavior). After debounce, exactly one emission for `"decision"` — none for the other entity types.

## Step 6 — Client-side validation regexes

In `dialogs/decision_create.py` and `dialogs/decision_edit.py`, add format validators that fire before the API call.

### Identifier regex (create only — Identifier is read-only on Edit)

Pattern: `^DEC-\d{3,}$` — "DEC-" followed by three or more digits. Permissive on the digit count to accommodate growth past DEC-999.

In the create dialog's pre-submission check (before the existing required-field check passes through to the API call):

```python
import re
_IDENTIFIER_RE = re.compile(r"^DEC-\d{3,}$")

def _validate_identifier(self) -> bool:
    text = self._identifier.text().strip()
    if not text:
        # Required-field check handles empty.
        return False
    if not _IDENTIFIER_RE.match(text):
        self._show_inline_error(
            self._identifier_error_label,
            "Identifier must be in format DEC-NNN (e.g., DEC-018).",
        )
        return False
    return True
```

If validation fails, show the inline error and don't make the API call.

### Decision date regex (create and edit)

Pattern: `^\d{2}-\d{2}-\d{2}$` — three two-digit groups separated by hyphens. Match what Doug's user preferences specify (`MM-DD-YY`). Permissive — does not validate that month is 01-12 or day is in range; that level of strictness goes against the existing pattern in this project where dates are stored as strings without parsing.

```python
_DECISION_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{2}$")

def _validate_decision_date(self) -> bool:
    text = self._decision_date.text().strip()
    if not text:
        return False
    if not _DECISION_DATE_RE.match(text):
        self._show_inline_error(
            self._decision_date_error_label,
            "Decision Date must be in format MM-DD-YY (e.g., 05-09-26).",
        )
        return False
    return True
```

### Tests

Extend the dialog tests:

- `test_invalid_identifier_format_shows_inline_error` — submitting "abc" doesn't make an API call, shows inline error on Identifier.
- `test_invalid_decision_date_format_shows_inline_error` — submitting "2026-05-09" (wrong format) shows inline error on Decision Date.
- `test_valid_format_passes_to_api` — "DEC-099" + "05-09-26" reaches the client.

## Step 7 — About dialog implementation

`crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py` — replace the docstring stub with the full implementation.

### Class shape

```python
class AboutDialog(QDialog):
    """Application About dialog. Shows the resolved configuration values.

    Per PRD section 11 open question #1, the dialog includes:
    * Application name
    * Version (read from pyproject.toml via importlib.metadata)
    * API base URL
    * Database path
    * Snapshot (export) directory
    """

    def __init__(self, parent: QWidget | None = None) -> None: ...
```

### Visual

`QFormLayout` with one row per field. Read-only `QLabel` values (selectable text so the user can copy paths). Bold labels. A close button at the bottom.

### Version source

```python
from importlib.metadata import version, PackageNotFoundError
try:
    app_version = version("crmbuilder-v2")
except PackageNotFoundError:
    app_version = "unknown (development install)"
```

### Configuration source

Read from `crmbuilder_v2.config.get_settings()`:
- `api_base_url` — already a string
- `db_path` — Path; render as `str(path)`
- `export_dir` — Path; render as `str(path)`

### Help → About menu wiring

In `main_window.py`, the Help menu has an existing About QAction (placeholder from slice A). Connect its `triggered` signal:

```python
self._about_action.triggered.connect(self._on_about_triggered)

def _on_about_triggered(self) -> None:
    AboutDialog(parent=self).exec()
```

### Tests

`tests/crmbuilder_v2/ui/test_about_dialog.py` (new):

- **Construction.** Construct the dialog; assert the form contains rows for app name, version, API URL, DB path, export dir.
- **Version handles PackageNotFoundError.** Patch `importlib.metadata.version` to raise; assert the dialog still constructs and shows the fallback string.

## Step 8 — Topics master-list "Parent Topic" cell click navigation

Slice E flagged this as an open question: the Topics panel's master list shows the raw Parent Topic identifier, but only the detail pane's link is clickable. Slice H closes the gap.

In `panels/topics.py`:

- Connect the QTableView's `clicked(index)` signal to a handler.
- In the handler: if the column is "Parent Topic" (column index 2 per slice E's column spec) and the cell value is non-empty, emit `navigate_requested("topic", parent_topic_identifier)`.

This mirrors the References panel's cell-click pattern from slice E.

### Tests

Extend `tests/crmbuilder_v2/ui/test_topics_hierarchy.py` (or wherever Topics has its tests):

- **Click on Parent Topic cell with value emits navigate_requested.** Stub records with TOP-1 and TOP-2 (TOP-2's parent is TOP-1). Click TOP-2's Parent Topic cell. Assert `navigate_requested.emit("topic", "TOP-1")` was called.
- **Click on Parent Topic cell with empty value does not emit.** Click TOP-1's (empty) Parent Topic cell. No emission.
- **Click on other columns does not emit.** Click TOP-2's Identifier or Name cell. No emission.

## Step 9 — Styling stub refinement

In `styling.py`, refine the QSS to ensure the navy accent color and Arial font apply consistently.

Targets to verify and adjust as needed:

- **Default font:** Arial 10pt across all widgets. Some default styles for QPlainTextEdit, QLineEdit, QLabel, QPushButton, QListWidget may need explicit font specification.
- **Selected `QListWidget::item`:** background `#1F3864`, white text. (Already in the slice A stub; verify.)
- **`QPushButton:focus`:** border `#1F3864`. Verify and tighten the rule.
- **Inline error labels:** consistent red text — define a CSS class or use `setStyleSheet` on the labels themselves with `color: #B22222;` (a deep red consistent with the navy palette). Standardize across create/edit/delete dialogs.
- **Selected row in QTableView:** background that matches the navy theme (e.g., a desaturated version of `#1F3864`, or use the OS default with the navy as the highlighted-text color).
- **Crash banner color** — verify the existing `#7A1F1F` deep red still pairs well with the navy after styling refinement.
- **About dialog headers:** consistent with the rest of the app.

This is not a full design pass — it's a refinement to make the existing stub coherent. If something looks visually off after the refinement, document it as a v0.2 polish item rather than redesigning here.

### No new tests for styling

QSS is not unit-testable in any meaningful way. Visual verification covers it.

## Step 10 — Friction polish

Items observed during D/E/F/G that haven't been called out yet, plus anything noticed during slice H execution. The list is non-exhaustive — Claude Code uses judgment to address what's actually rough.

Suggested items:

1. **Tab order in dialogs.** Verify that pressing Tab moves through fields in the order they're rendered. If not, set tab order explicitly via `QWidget.setTabOrder()`.
2. **Close-on-Escape.** All dialogs should close on Escape. QDialog default; verify.
3. **Dialog window titles.** Verify each dialog has an appropriate titlebar text ("New Decision", "Edit DEC-018", "Delete decision", "About CRMBuilder v2", "Error: ...").
4. **Status label clearing on success.** Verify the status label in each panel's toolbar transitions from "Loading…" back to "{n} records" cleanly on a successful refresh.
5. **No log noise on common operations.** Verify `~/.crmbuilder-v2/ui.log` doesn't fill with WARNING or ERROR lines for routine successful operations.

### No mandatory tests

Friction polish is by definition discovery work. Where a fix introduces a behavior change worth verifying, add a test. Where it's a cosmetic tweak, skip.

## Step 11 — README addition

Add a new "User interface" section to `crmbuilder-v2/README.md`. Slot it between the "MCP server" section and the "Maintenance" section (or wherever fits naturally given the README's current structure).

Content:

```markdown
## User interface

A standalone PySide6 desktop application for browsing and editing
storage system content.

```bash
uv run crmbuilder-v2-ui
```

The UI auto-launches the storage API (`crmbuilder-v2-api`) if it's not
already running, and shuts it down on close. If the API is already
running externally (e.g., for the MCP server), the UI uses the existing
instance.

Features:
- Sidebar navigation across all eight v2 entity types: Charter,
  Status, Decisions, Sessions, Risks, Planning Items, Topics,
  References.
- Master/detail layout per entity. Detail panes show full record
  content with cross-entity reference links (e.g., a decision's
  "Decided in" link navigates to the corresponding session).
- Live refresh via filesystem watcher on the snapshot directory:
  writes from MCP or other consumers update visible panels within
  ~500ms; non-visible panels show a stale-data indicator.
- Full create / edit / delete operations for decisions. Other
  entities are read-only in v0.1.

Full requirements: `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`.
```

## Step 12 — macOS visual verification

Best-effort. If a macOS environment is available:

1. Launch the UI on macOS.
2. Click through every sidebar entry; verify each panel renders.
3. Open and dismiss each dialog (New Decision, Edit, Delete, About).
4. Verify the styling stub looks reasonable on macOS native rendering (font sizing, button shapes, dialog modality).
5. Note any platform-specific issues in the report.

If no macOS environment is available, skip and note in the report.

## Step 13 — Closeout governance records

After all functional changes are committed, write the closing session and status update.

### SES-005 — UI v0.1 build

Via `POST /sessions`:

```json
{
  "identifier": "SES-005",
  "title": "UI v0.1 build",
  "session_date": "<today, MM-DD-YY format>",
  "status": "Complete",
  "topics_covered": "Eight-prompt execution of the UI v0.1 build per the implementation plan: scaffold (A), server lifecycle (B), HTTP client and list/detail base (C), read-only views round 1 — decisions, sessions, risks (D), read-only views round 2 — charter, status, topics, planning items, references (E), file-watch refresh (F), decisions CRUD (G), and polish (H).",
  "summary": "UI v0.1 shipped: standalone PySide6 desktop application that consumes the storage system REST API. Eight read-only entity panels with master/detail navigation and cross-panel reference links. Full create/edit/delete for decisions. File-watch live refresh. Detect-then-launch API subprocess management. Soft-delete semantics added to the access layer to preserve referential integrity. Content-hash gating in the refresh service eliminates false-positive stale-dot signals. About dialog and styling refinement complete.",
  "artifacts_produced": "Eight prompts (CLAUDE-CODE-PROMPT-v2-ui-A through H) under PRDs/product/crmbuilder-v2/prompts/. Source under crmbuilder-v2/src/crmbuilder_v2/ui/. ~25 test files under tests/crmbuilder_v2/ui/. Storage system additions: GET /health endpoint (slice A), soft-delete semantics for decisions (slice H).",
  "in_flight_at_end": "v0.2 backlog items: write surfaces for non-decision entities; reference rendering on Sessions/Risks/Charter/Status/Topics/Planning Items detail panes; charter/status replace flows with version history browsing; calendar widget on Decision Date input; QTreeView for Topics; styling design pass."
}
```

### Status update

Via `PUT /status`:

The new status payload reflects v0.1 complete. Build on the prior status v5 content but update phase and version_label:

```json
{
  "phase": "v0.1 complete",
  "version_label": "0.6",
  ... existing fields preserved ...
}
```

The exact payload structure should match status v5's structure. Read `db-export/status.json` to see the current shape and preserve it.

### Verify

After the writes:

- `db-export/sessions.json` includes SES-005.
- `db-export/status.json` reflects the new version.
- `db-export/change_log.json` has corresponding entries.

## Step 14 — Verify and commit

Run the full test suite:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 235 prior tests + new tests from steps 3, 5, 6, 7, 8. Estimated ~260+ passing, all green.

### Commit strategy: three commits

**Commit 1: storage fixes**

```
v2: storage soft-delete decisions and PATCH FK clear

Two access-layer fixes that make the documented contract correct
end-to-end for the v0.1 UI:

- Decisions become soft-delete: decisions.delete() sets status to
  'Deleted' instead of physically removing the row. References
  pointing at deleted decisions continue to resolve via get(). The
  decisions.list_all() function filters out Deleted records by
  default; an include_deleted parameter is provided for callers
  that need full history. The CHECK constraint on decisions.status
  is updated via Alembic migration 0002 to include 'Deleted'.

- _resolve_decision_id now treats empty string the same as None
  (returns None without raising), so PATCH /decisions/{id} with
  supersedes='' or superseded_by='' correctly clears the FK rather
  than raising a 'decision \"\" does not exist' validation error.

UI cleanup: removed the now-obsolete ConflictError branch in
DecisionDeleteDialog (soft-delete never conflicts) and replaced
with a defensive ErrorDialog fallback. The edit dialog already
sends empty string for cleared FKs; that wire format is now
correctly handled by the API.

Closes the two open questions surfaced during slice G verification.
```

**Commit 2: UI polish**

```
v2: ui v0.1 polish — refresh content-hash gating, validation, about dialog

Closes the slice H polish backlog:

- RefreshService gains content-hash gating. The storage system
  rewrites all eight snapshots on every commit; the watcher now
  computes a SHA-256 hash of each file and suppresses emission when
  content is byte-identical. Eliminates false-positive stale-dot
  signals for non-affected entity types.

- DecisionCreateDialog and DecisionEditDialog gain client-side
  format validation: identifier (DEC-NNN regex) and decision_date
  (MM-DD-YY regex). Errors display inline before the API call,
  catching common typos without a roundtrip.

- AboutDialog (about_dialog.py) implemented with QFormLayout
  showing app name, version (importlib.metadata-resolved),
  API URL, DB path, snapshot directory. Wired to the existing
  Help → About menu placeholder.

- TopicsPanel master-list 'Parent Topic' cell now navigates on
  single-click (mirrors ReferencesPanel). Closes a slice E
  open question.

- styling.py refined for consistent navy accent on selection
  highlights, table row selection, button focus borders, and
  inline error label color (#B22222).

- README adds a 'User interface' section with quickstart and
  link to the v0.1 PRD.

- Friction polish: tab order, dialog window titles, log noise
  cleanup as observed during the build.
```

**Commit 3: closeout**

```
v2: ui v0.1 closeout — append SES-005, update status to v0.1 complete

Closes the v2-ui workstream. Captures the eight-prompt build via
SES-005 (UI v0.1 build) and bumps the status to phase='v0.1 complete'.

The v0.1 backlog deferred to v0.2 is captured in SES-005's
in_flight_at_end field.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. `uv run alembic upgrade head` applies migration 0002 cleanly. The CHECK constraint on `decisions.status` includes `'Deleted'`.
2. Soft-delete works: `DELETE /decisions/DEC-X` sets the status; `GET /decisions/DEC-X` still returns the record with `status='Deleted'`; `GET /decisions` no longer returns it.
3. `PATCH /decisions/{id}` with `supersedes=""` clears the link; the next `GET` shows `supersedes_identifier: None`.
4. The DecisionDeleteDialog's ConflictError body-replacement path is removed; ConflictError now routes to the generic ErrorDialog as a defensive fallback.
5. RefreshService no longer emits `data_changed` for snapshot files whose content is byte-identical to the cached version.
6. Submitting an invalid identifier or decision_date format in the create/edit dialogs surfaces an inline error before any API call is made.
7. Help → About opens the AboutDialog showing app version, API URL, DB path, and snapshot directory.
8. Clicking a non-empty "Parent Topic" cell in the Topics panel master list navigates to that topic.
9. The full v2 test suite passes, including all new tests from steps 3, 5, 6, 7, 8.
10. SES-005 and the status v6 update are present in `db-export/sessions.json` and `db-export/status.json` after closeout.
11. Three commits on `origin/main`: storage fixes, ui polish, closeout — in that order.

## Out of slice

The following are explicitly NOT in scope for slice H:

- Write surfaces for non-decision entities. v0.2.
- Reference rendering on non-Decisions detail panes. v0.2.
- Charter/Status replace flows. v0.2.
- Calendar widget for Decision Date. v0.2 if user feedback wants it.
- QTreeView for Topics. v0.2.
- Full styling design pass. v0.2 per DEC-024.
- A "Show deleted" toggle in the decisions panel toolbar. v0.2 if needed.

## Constraints

- **No new external dependencies.** `hashlib` is stdlib; `importlib.metadata` is stdlib.
- **No schema changes beyond the CHECK constraint update on decisions.status.** No new tables, no new columns, no constraint additions to other tables.
- **No vocab changes beyond adding `'Deleted'` to `DECISION_STATUSES`.** Other vocabularies are unchanged.
- **Do not modify the lifecycle, sidebar widget, or any panel beyond the targeted edits in steps 5, 7, 8, and the friction polish.**
- **Do not introduce new architectural patterns.** Polish is refinement, not redesign.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the eleven gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum: soft-delete via curl, PATCH supersedes='' via curl, content-hash gating (multiple curl writes producing only one panel update), About dialog visual check.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for v0.2.
- **Final state of the build** — confirmation that v0.1 is shipped, with a brief inventory of what was delivered across all eight slices.
