# CLAUDE-CODE-PROMPT-v2-ui-v0.2-E-charter-status-replace

**Last Updated:** 05-08-26
**Series:** v2-ui-v0.2
**Slice:** E (5 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.2-D (topics CRUD + tree picker)

## Purpose

Slice E delivers the versioned-replace flow for Charter and Status, plus the `ReferencesSection` widget on the Charter, Status, and Sessions detail panes (closing the read-only-panel parity work).

After this slice:

- A "New Version" button appears in the Charter panel toolbar. Clicking opens `VersionedReplaceDialog`, pre-populated with the current charter's payload as pretty-printed JSON. The dialog has a Validate button that parses the editor text as JSON and surfaces invalid-format errors. Save creates a new charter version through `PUT /charter`. The version-history list pane updates.
- The Status panel has the same New Version flow.
- Each non-current version row in the version-history list pane has a "Make Current" button (or context-menu action). Clicking opens a confirmation modal; confirming flips `is_current` to that version.
- The Charter, Status, and Sessions detail panes get the `ReferencesSection` widget, completing v0.2's "ReferencesSection on every detail pane" goal.

## Project context

Slice A created the `VersionedReplaceDialog` skeleton (raises `NotImplementedError`). This slice is its full implementation. The dialog is intentionally schema-blind — it presents JSON, validates JSON, and submits JSON, per DEC-029. Charter and Status share the dialog framework with different save callbacks.

The storage system already supports versioned replace for Charter and Status from v0.1 (the panels show version history). The PUT semantics: a successful PUT creates a new version row with the new payload and `is_current=true`; the prior current version's `is_current` flips to false automatically. Verify against the access-layer code; if the contract differs, follow the access layer.

The "Make Current" affordance requires a path to flip `is_current` to a non-current version without creating a new version. If the storage system does not currently expose this (the v0.1 versioned-replace was always "create a new version, which becomes current"), the slice adds an endpoint: `PATCH /charter/versions/{n}/make-current` (and the corresponding for status), with the access-layer repository method behind it. This is mechanical work; surface as an open question if invasive.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice D is on `main`.
6. Confirm the v2 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.2.md` — section 4.5 (Charter and Status replace flows), section 4.6 (References).
3. `PRDs/product/crmbuilder-v2/ui-v0.2-implementation-plan.md` — Step E in section 4.
4. Slice A's deliverables:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py` — the skeleton.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`.
5. Existing Charter/Status panels:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/charter.py`, `status.py`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_panel.py`.
6. Existing Sessions panel:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/sessions.py`.
7. Storage system surfaces:
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/charter.py` and `status.py` — the versioned-replace logic.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/charter.py` and `status.py`.
8. **Tier 2 orientation**: current charter, current status, SES-006, DEC-029 (slice E's design rationale), DEC-031 (ReferencesSection generalization).

## Step 1 — Implement `VersionedReplaceDialog`

Replace the slice A skeleton in `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py` with the full implementation.

```python
"""VersionedReplaceDialog — JSON payload editor for versioned-replace
entities (charter, status). Per ui-PRD-v0.2.md §4.5 and DEC-029.
"""
import json
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    StorageClientError, StorageConnectionError, ValidationError,
)
from crmbuilder_v2.ui.workers import run_in_thread


class VersionedReplaceDialog(QDialog):
    """Modal JSON editor for replacing a versioned entity's payload.

    Constructor takes:
    * current_payload: dict — pre-populated as pretty-printed JSON.
    * save_callback: callable(payload: dict) → record — invoked on
      Save (through a worker).
    * title: str — window title and header text.

    Layout:
    * QPlainTextEdit (monospace, ~600px tall) showing the payload.
    * Validate button + status label below the editor.
    * Save / Cancel button bar at the bottom.

    Validate parses the editor text as JSON; on valid, sets the
    status label to 'Valid JSON'; on invalid, sets the status label
    to 'Invalid JSON: <error>' and disables Save until the user
    edits the text and Validate runs again successfully.

    Save runs Validate first; if valid, calls save_callback through
    a worker. On success, accepts. ValidationError → ErrorDialog
    with the API's error envelope detail (the access layer may
    reject schema-mismatch payloads). StorageConnectionError →
    reject. Other StorageClientError → ErrorDialog.
    """

    def __init__(
        self,
        current_payload: dict,
        save_callback: Callable[[dict], dict],
        *,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 700)
        self._save_callback = save_callback
        self._validated_payload: dict | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>{title}</b>"))

        self._editor = QPlainTextEdit()
        font = QFont("Monaco")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self._editor.setFont(font)
        self._editor.setPlainText(json.dumps(current_payload, indent=2, sort_keys=False))
        layout.addWidget(self._editor)

        # Validate row.
        validate_row = QHBoxLayout()
        self._validate_btn = QPushButton("Validate")
        self._validate_btn.clicked.connect(self._on_validate)
        validate_row.addWidget(self._validate_btn)
        self._validation_status = QLabel("")
        validate_row.addWidget(self._validation_status, 1)
        layout.addLayout(validate_row)

        # Editor edits invalidate the prior validation.
        self._editor.textChanged.connect(self._invalidate_prior_validation)

        # Buttons.
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self._save_btn = button_box.button(QDialogButtonBox.Save)
        self._save_btn.clicked.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initial state: validate the pre-populated content.
        self._on_validate()

    def _on_validate(self) -> None:
        text = self._editor.toPlainText()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            self._validation_status.setText(
                f"<span style='color: #B22222;'>Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}</span>"
            )
            self._validated_payload = None
            return
        if not isinstance(parsed, dict):
            self._validation_status.setText(
                "<span style='color: #B22222;'>Top-level value must be an object (dict).</span>"
            )
            self._validated_payload = None
            return
        self._validation_status.setText(
            "<span style='color: #1F3864;'>Valid JSON.</span>"
        )
        self._validated_payload = parsed

    def _invalidate_prior_validation(self) -> None:
        if self._validated_payload is not None:
            self._validation_status.setText(
                "<span style='color: gray;'>(modified — re-validate before saving)</span>"
            )
            self._validated_payload = None

    def _on_save(self) -> None:
        # Re-validate first.
        self._on_validate()
        if self._validated_payload is None:
            return  # Validation failed; status label shows why.
        self._save_btn.setEnabled(False)
        run_in_thread(
            lambda: self._save_callback(self._validated_payload),
            on_success=self._on_save_success,
            on_error=self._on_save_error,
        )

    def _on_save_success(self, _result: dict) -> None:
        self.accept()

    def _on_save_error(self, exc: BaseException) -> None:
        self._save_btn.setEnabled(True)
        if isinstance(exc, StorageConnectionError):
            self.reject()
            return
        if isinstance(exc, ValidationError):
            ErrorDialog(
                "Invalid payload",
                "The payload was rejected by the server.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        if isinstance(exc, StorageClientError):
            ErrorDialog(
                "Could not save",
                "An error occurred while saving the new version.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        # Unexpected.
        ErrorDialog(
            "Unexpected error",
            "An unexpected error occurred.",
            detail=repr(exc),
            parent=self,
        ).exec()
```

### Tests

`tests/crmbuilder_v2/ui/test_versioned_replace_dialog_base.py`:

- Construction with a sample payload renders the editor pre-populated with pretty-printed JSON.
- Validate button on the initial pre-populated content shows "Valid JSON".
- Editing the text to break JSON syntax → Validate shows "Invalid JSON: ...".
- Editing back to valid → Validate shows "Valid JSON".
- Save with invalid JSON does not call the save callback.
- Save with valid JSON calls the save callback with the parsed dict.
- StorageConnectionError on save → dialog rejects.
- ValidationError on save → ErrorDialog opens, dialog stays open.
- ServerError on save → ErrorDialog opens, dialog stays open.

## Step 2 — Charter replace flow

### `dialogs/charter_replace.py` (new)

A thin wrapper:

```python
"""Charter replace dialog. Per ui-PRD-v0.2.md §4.5."""
from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.versioned_replace_dialog import VersionedReplaceDialog
from crmbuilder_v2.ui.client import StorageClient


class CharterReplaceDialog(VersionedReplaceDialog):
    def __init__(
        self,
        client: StorageClient,
        current_payload: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            current_payload,
            client.replace_charter,
            title="New Charter Version",
            parent=parent,
        )
```

### Extend `StorageClient`

```python
def replace_charter(self, payload: dict) -> dict:
    """PUT /charter. Creates a new charter version with the given payload.
    Returns the new version record.
    """
    return self._request("PUT", "/charter", json={"payload": payload})


def make_charter_version_current(self, version_number: int) -> dict:
    """PATCH /charter/versions/{n}/make-current. Flips is_current to
    the specified version. Returns the version record.
    """
    return self._request(
        "PATCH",
        f"/charter/versions/{version_number}/make-current",
    )
```

If the API doesn't have `make-current` endpoints, add them. Pattern: thin route in `api/routers/charter.py` calling an access-layer method `charter.make_version_current(session, version_number)` that flips `is_current` flags atomically (set new version's flag to True, all others to False).

### Extend `panels/charter.py`

Add a "New Version" button in the toolbar:

```python
self._new_version_btn = QPushButton("New Version")
self._new_version_btn.clicked.connect(self._on_new_version_clicked)
self._action_layout.addWidget(self._new_version_btn)


def _on_new_version_clicked(self) -> None:
    # Find the current version's payload.
    current = self._find_current_version()
    if current is None:
        ErrorDialog(
            "No current charter",
            "No current charter version exists.",
            parent=self,
        ).exec()
        return
    dialog = CharterReplaceDialog(self._client, current["payload"], self)
    if dialog.exec() == QDialog.Accepted:
        self.refresh()
```

Add Make Current buttons on each non-current version row. The implementation depends on the existing version-list rendering; the cleanest approach is to add a small button on each non-current row's right side:

```python
# In the version list rendering:
for version in versions:
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.addWidget(QLabel(f"v{version['version']} — {version['created_at']}"))
    if version.get("is_current"):
        row_layout.addWidget(QLabel("(current)"))
    else:
        make_current_btn = QPushButton("Make Current")
        make_current_btn.clicked.connect(
            lambda _checked=False, v=version: self._on_make_current(v)
        )
        row_layout.addWidget(make_current_btn)
    # ... existing selection wiring ...


def _on_make_current(self, version: dict) -> None:
    confirm = QMessageBox.question(
        self,
        "Make Current",
        f"Make charter version {version['version']} the current version?\n"
        "The current version will become a non-current historical record.",
    )
    if confirm != QMessageBox.Yes:
        return
    try:
        self._client.make_charter_version_current(version["version"])
    except StorageClientError as exc:
        ErrorDialog(
            "Could not make current",
            "An error occurred while flipping the current version.",
            detail=str(exc),
            parent=self,
        ).exec()
        return
    self.refresh()
```

Run the make-current call through a worker per the v0.2 threading rules. The above sketch is synchronous for clarity; actual implementation uses `run_in_thread`.

### `fetch_detail_extras` override and `ReferencesSection` on Charter detail pane

The Charter panel needs a `fetch_detail_extras` override per slice A's actual `ReferencesSection` API (pure rendering, pre-fetched payload). Charter and status records identify by version number, not a string identifier like decisions; the references graph uses whatever stable identifier the storage layer's `references` table records as the entity_id for charter/status entries — verify by inspecting an existing reference row or the `list_references_touching` output for an existing charter version, and adjust the identifier expression accordingly. If charter/status versions don't have inbound or outbound references in practice, `list_references_touching` returns empty groups and the widget renders "(none)" — that's fine.

```python
def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
    identifier = record.get("identifier_or_id")  # adjust per actual record shape
    if not identifier:
        return {"references": {"as_source": [], "as_target": []}}
    return {
        "references": self._client.list_references_touching(
            "charter", identifier
        ),
    }
```

```python
references_section = ReferencesSection(
    "charter",
    record["identifier_or_id"],
    extras.get("references") or {},
)
references_section.navigate_requested.connect(self.navigate_requested)
```

### Tests

`tests/crmbuilder_v2/ui/test_charter_replace.py`:

- New Version button is present in the toolbar.
- Clicking it opens CharterReplaceDialog with the current charter's payload pre-populated.
- Successful Save refreshes the panel.
- Make Current button appears on non-current version rows; clicking opens a confirmation; confirming calls `make_charter_version_current`.
- ReferencesSection renders on Charter detail pane.

## Step 3 — Status replace flow (mirror of step 2)

### `dialogs/status_replace.py` (new)

```python
class StatusReplaceDialog(VersionedReplaceDialog):
    def __init__(
        self,
        client: StorageClient,
        current_payload: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            current_payload,
            client.replace_status,
            title="New Status Version",
            parent=parent,
        )
```

### Extend `StorageClient`

```python
def replace_status(self, payload: dict) -> dict:
    return self._request("PUT", "/status", json={"payload": payload})


def make_status_version_current(self, version_number: int) -> dict:
    return self._request(
        "PATCH",
        f"/status/versions/{version_number}/make-current",
    )
```

### Extend `panels/status.py` per the same pattern as Charter

New Version button + Make Current button + ReferencesSection.

### Tests

`tests/crmbuilder_v2/ui/test_status_replace.py` mirrors `test_charter_replace.py`.

## Step 4 — `ReferencesSection` on the Sessions detail pane

`panels/sessions.py` is read-only — no write surface in v0.2. Add the `fetch_detail_extras` override and the `ReferencesSection` widget per slice A's actual `ReferencesSection` API (pure rendering, pre-fetched payload):

```python
def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
    identifier = record.get("identifier")
    if not identifier:
        return {"references": {"as_source": [], "as_target": []}}
    return {
        "references": self._client.list_references_touching(
            "session", identifier
        ),
    }
```

```python
references_section = ReferencesSection(
    "session",
    record["identifier"],
    extras.get("references") or {},
)
references_section.navigate_requested.connect(self.navigate_requested)
```

Append the `ReferencesSection` to the detail pane layout beneath the existing form fields.

### Test

Add a smoke check to `tests/crmbuilder_v2/ui/test_smoke.py` (or wherever the sessions panel test lives) that asserts the ReferencesSection is present on the Sessions detail pane after a row is selected.

## Step 5 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: slice A + B + C + D tests + new tests. Estimated 360+ passing.

Manual verification:

1. **Charter new version.** Launch UI, navigate to Charter. Click New Version. The dialog opens with the current payload pre-populated as JSON. Click Validate; "Valid JSON". Modify the payload (e.g., add a new key); click Validate; "Valid JSON". Click Save; confirm the dialog closes and the new version appears in the version-history list.
2. **Charter invalid JSON.** Click New Version; break the JSON (delete a closing brace); click Validate; "Invalid JSON: ...". Save is disabled (or pressing Save shows the validation error and doesn't fire). Fix the JSON; Validate passes; Save works.
3. **Charter make current.** With multiple charter versions, click Make Current on a non-current version. Confirm the modal; click Yes. Confirm the version-history list now shows that version as current.
4. **Status new version.** Same flow on Status panel.
5. **Status make current.** Same flow on Status panel.
6. **References on Charter, Status, Sessions panels.** Select a record on each panel; confirm the ReferencesSection renders.
7. **Watcher integration.** `curl PUT /charter` while the panel is open; confirm the new version appears in the list.

Commit shape:

```
v2: ui charter and status replace flows + sessions references section

Implements slice E of the v2-ui-v0.2 series. Per ui-PRD-v0.2.md §4.5
and §4.6.

- VersionedReplaceDialog (base/versioned_replace_dialog.py): full
  implementation replacing slice A's skeleton. JSON editor with
  monospace font, ~700px tall. Validate button parses JSON
  client-side; status label shows valid/invalid. Save runs Validate
  first; valid → save callback through worker. ValidationError on
  save → ErrorDialog with API envelope detail.
  StorageConnectionError → reject. Other errors → ErrorDialog.

- CharterReplaceDialog and StatusReplaceDialog as thin wrappers of
  the base. Toolbar New Version buttons on Charter and Status
  panels. Make Current buttons on each non-current version row;
  confirmation modal; PATCH /<entity>/versions/{n}/make-current.

- StorageClient extended with replace_charter, replace_status,
  make_charter_version_current, make_status_version_current.

- ReferencesSection on Charter, Status, and Sessions detail panes.
  Sessions panel gains the widget without any other changes (read-
  only-only).

- ~20 new tests covering the dialog, wrappers, panels, and references
  rendering.

Out of slice: show-deleted toggle, About dialog version bump,
closeout (slice F).
```

If storage additions were needed:

```
v2: storage adds make-current endpoints for charter and status versions
```

Push to origin/main.

## Acceptance gates

1. New Version button on Charter opens the dialog pre-populated with the current payload. Validate works. Save creates a new version. (PRD AC#7.)
2. Same flow on Status. (PRD AC#8.)
3. Make Current button on a non-current version flips `is_current` after confirmation. (PRD AC#9.)
4. ReferencesSection renders on Charter, Status, and Sessions detail panes. (PRD AC#10 complete after this slice.)
5. Live refresh works for charter/status replace.
6. Test suite passes.
7. Commit(s) on origin/main.

## Out of slice

- Show-deleted toggle, About dialog version bump, closeout records. Slice F.
- Diff-with-current view for the JSON editor. Possible v0.3.
- Structured form for the payload. Possible v0.3.

## Constraints

- **No new external dependencies.**
- **Storage additions only if needed** (make-current endpoints if not already present). Mechanical and aligned with existing patterns.
- **Reuse the dialog framework from slice A.** No bespoke per-entity payload editing.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- Acceptance gates pass/fail.
- Files created or modified.
- Storage additions (if any).
- Test results.
- Manual verification confirmation.
- Deviations.
- What slice F will need (e.g., any rough edges to address in polish).
