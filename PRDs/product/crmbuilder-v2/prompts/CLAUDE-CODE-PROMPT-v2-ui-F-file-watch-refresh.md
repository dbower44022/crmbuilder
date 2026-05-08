# CLAUDE-CODE-PROMPT-v2-ui-F-file-watch-refresh

**Last Updated:** 05-08-26 22:00
**Series:** v2-ui
**Slice:** F (6 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-E (commit `7f303af`)

## Purpose

Slice F closes PRD acceptance criterion AC#11: writing data to the storage system via MCP (or any other consumer) while the UI is open causes the affected panel to update without manual intervention.

The mechanism leverages the storage system's existing snapshot side channel — every successful write atomically rewrites the JSON snapshot files in `PRDs/product/crmbuilder-v2/db-export/`. The UI watches that directory with `QFileSystemWatcher` and refetches the affected panel when the corresponding snapshot file changes. Per DEC-022, this leverages an architectural property that exists for free.

After this slice:

- A `RefreshService` (`refresh.py`) wraps `QFileSystemWatcher`, observes the snapshot directory, and emits a `data_changed(entity_type)` signal when an entity-type snapshot file is modified.
- Multi-write bursts (Claude writing seven decisions in succession, for example) are debounced so the UI refetches once per entity type rather than seven times.
- The `change_log.json` file is filtered out — it's not an entity panel target.
- When a panel that is currently visible receives a `data_changed` for its entity type, it refetches silently (no spinner; the table just updates when ready).
- When `data_changed` fires for an entity type whose panel is NOT currently visible, the sidebar entry for that panel displays a small dot indicator. Navigating to a stale panel clears the indicator and triggers an immediate refresh.
- The manual Refresh button on every panel continues to work as a fallback (already in place from slice C).

This slice does not implement decision dialogs (slice G) or polish (slice H). It does not change any existing panel — only `MainWindow` and `Sidebar` integrate with the new service, and the integration is purely additive.

## Project context

Slice E landed at commit `7f303af`. All eight sidebar entries route to real panels, and the read-only application is feature-complete. Each panel is a `ListDetailPanel` subclass with a public `refresh()` method that the file-watch service can call directly.

The snapshot directory comes from `crmbuilder_v2.config.get_settings().export_dir`. Same setting the API and access layer use, so the UI and writers agree on the directory by construction. The directory contains nine JSON files: eight entity snapshots plus `change_log.json` (the audit log — ignored by this slice).

The implementation plan section 4 / Step F specifies the deliverables. PRD section 4.10 is the authoritative behavior spec. DEC-022 is the architectural decision being implemented.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice E is on `main`: `git log --oneline -3` should show `7f303af` (slice E panels) at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 185 tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read section 4.10 (refresh) and section 4.11 (error handling).
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step F in section 4.
4. Slice E's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/refresh.py` — currently a docstring stub; slice F fills it in.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` — slice F adds the staleness-indicator API.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — slice F adds the RefreshService instance and routing.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — confirm the `refresh()` method's contract (no changes needed).
5. **Tier 2 orientation** (per DEC-011): current charter, current status, SES-004, DEC-022 (file-watch + manual refresh).

## Step 1 — Implement `refresh.py`

The full `RefreshService` module. Pure Qt, no Qt-foreign dependencies.

### Class shape

```python
class RefreshService(QObject):
    """File-watch refresh service.

    Watches the configured snapshot directory and emits data_changed
    signals when an entity-type snapshot file is modified. Multi-write
    bursts within the debounce window coalesce to a single emission
    per entity type.

    Signals:
    * data_changed(str)  — entity_type whose snapshot was rewritten.
                           One of: charter, status, decision, session,
                           risk, planning_item, topic, reference.
    * watch_failed(str)  — emitted if QFileSystemWatcher cannot watch
                           the directory. Argument carries diagnostic.
    """

    data_changed = Signal(str)
    watch_failed = Signal(str)

    DEBOUNCE_MS: ClassVar[int] = 500

    def __init__(self, snapshot_dir: Path, parent: QObject | None = None) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

### Filename mapping

A module-level constant:

```python
_FILENAME_TO_ENTITY_TYPE: dict[str, str] = {
    "charter.json": "charter",
    "status.json": "status",
    "decisions.json": "decision",
    "sessions.json": "session",
    "risks.json": "risk",
    "planning_items.json": "planning_item",
    "topics.json": "topic",
    "references.json": "reference",
}
# Note: change_log.json is intentionally absent — it's not an entity panel target.
```

### Watch strategy

- Watch the **directory**, not individual files. The storage system writes snapshots via atomic rename (write tempfile + rename to canonical name), which on most filesystems removes the watcher from individual file paths after each rename. Watching the directory is robust against this.
- On `directoryChanged(path)`, list the directory contents and check whether any entity-snapshot file's mtime changed since the last check. Track per-file mtimes in a small dict.
- Tempfiles created during atomic-rename writes (filenames not in the map) are ignored.
- `change_log.json` is in the map's denylist by absence — ignored.

An alternative is to use `directoryChanged` as the trigger and then check mtimes for each known snapshot file. That handles the broadest set of platform behaviors. Use this approach.

### Debounce mechanism

For each entity type, maintain a `QTimer.singleShot(DEBOUNCE_MS, …)` pattern using a per-entity-type pending flag. Multiple `directoryChanged` events for the same entity type within `DEBOUNCE_MS` coalesce: only one `data_changed` emission per entity type per debounce window.

Implementation:

```python
self._pending_emits: set[str] = set()  # entity_types pending emit
self._debounce_timer = QTimer(self)
self._debounce_timer.setSingleShot(True)
self._debounce_timer.setInterval(self.DEBOUNCE_MS)
self._debounce_timer.timeout.connect(self._flush_pending)
```

When `directoryChanged` is observed for an entity-type file:
- Add the entity type to `_pending_emits`.
- (Re)start the debounce timer.

When the timer fires:
- Iterate `_pending_emits`, emit `data_changed(entity_type)` for each.
- Clear the set.

This means a burst of 7 writes in 100ms produces a single emission ~500ms after the last write. Acceptable latency.

### `start()` and `stop()`

`start()`:
- Construct `QFileSystemWatcher` with the directory path.
- If `QFileSystemWatcher.directories()` does not include the directory after addPath, emit `watch_failed("Could not watch directory: {path}")` and return.
- Connect `directoryChanged` to the internal handler.
- Snapshot current mtimes of all entity-type files for the baseline.

`stop()`:
- Disconnect signals, remove the watcher's path, stop the debounce timer.

### Logging

`logging.getLogger("crmbuilder_v2.ui.refresh")`. Log:
- DEBUG: every `directoryChanged` event with the path.
- DEBUG: each `data_changed` emission with the entity type and elapsed-since-burst-start (helpful for tuning DEBOUNCE_MS later).
- WARNING: `watch_failed` events.

No file contents are logged.

### Tests

Add `tests/crmbuilder_v2/ui/test_refresh.py` (new). All tests use `tmp_path` for the watched directory and real `QFileSystemWatcher` (no mocks).

1. **Single write fires data_changed for the right entity type.** Start the service watching `tmp_path`. Write `decisions.json`. `qtbot.waitSignal(service.data_changed, timeout=2000)` succeeds with arg `"decision"`.
2. **change_log.json is ignored.** Write `change_log.json`. No `data_changed` signal within 1000ms.
3. **Tempfile creation is ignored.** Create a `decisions.json.tmp.abc123` file (a name not in the map). No `data_changed` signal within 1000ms.
4. **Multi-write burst is debounced.** Write `decisions.json` ten times in a tight loop (each write is `path.write_text(...)`). Within 2000ms, exactly one `data_changed("decision")` emission occurs.
5. **Multiple entity types fire separately.** Write `decisions.json` then `sessions.json` within the debounce window. Both `data_changed("decision")` and `data_changed("session")` fire after debounce.
6. **Watch failure on non-existent directory emits watch_failed.** Construct service with a path that doesn't exist. Call `start()`. `qtbot.waitSignal(service.watch_failed, timeout=1000)` succeeds.
7. **stop() prevents further emissions.** Start, write a file, observe emission, call `stop()`, write another file, assert no further emission within 1000ms.

Tests may need `qtbot.wait(50)` or similar between filesystem operations to let the OS dispatch events. PySide6's QFileSystemWatcher on Linux uses inotify which is fast but not synchronous.

## Step 2 — Extend `Sidebar` with staleness indicator

The sidebar currently is a `QListWidget`. Slice F adds a small filled-circle icon on stale entries.

### Changes to `sidebar.py`

Add two methods:

```python
class Sidebar(QListWidget):
    ...
    def set_stale(self, label: str, stale: bool) -> None:
        """Show or hide the staleness indicator for a sidebar entry."""

    def is_stale(self, label: str) -> bool:
        """Whether an entry is currently marked stale."""
```

Implementation:

- Add a module-level helper `_make_stale_pixmap() -> QPixmap` that returns an 8×8 transparent QPixmap with a filled circle drawn in the navy accent color (`#1F3864`). Use `QPainter.setRenderHint(QPainter.Antialiasing, True)` for a smooth circle.
- `set_stale(label, True)`: find the `QListWidgetItem` for the label; call `item.setIcon(QIcon(pixmap))`.
- `set_stale(label, False)`: `item.setIcon(QIcon())` (clears the icon).
- `is_stale(label)`: returns whether the item's icon is non-null.

The pixmap is constructed once at module load (cheap singleton) so all stale items share the same icon resource.

### Tests

Extend `tests/crmbuilder_v2/ui/test_smoke.py` (or add a small `test_sidebar.py`):

- **set_stale toggles icon.** Construct a Sidebar, call `set_stale("Decisions", True)`, assert `is_stale("Decisions")` is True. Call `set_stale("Decisions", False)`, assert `is_stale("Decisions")` is False.
- **set_stale with an unknown label is a no-op.** Should not raise.

## Step 3 — Wire `RefreshService` into `MainWindow`

### Construction

In `MainWindow.__init__`, after the panels are wired up:

```python
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.ui.refresh import RefreshService

settings = get_settings()
self._refresh_service = RefreshService(settings.export_dir, self)
self._refresh_service.data_changed.connect(self._on_data_changed)
self._refresh_service.watch_failed.connect(self._on_watch_failed)
self._refresh_service.start()

self._stale_entries: set[str] = set()  # sidebar labels with pending stale data
```

The service is started during MainWindow construction. It runs for the lifetime of the window.

### `_on_data_changed` slot

```python
def _on_data_changed(self, entity_type: str) -> None:
    label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
    if label is None:
        return
    visible_label = self._sidebar.current_text()
    if label == visible_label:
        # Visible panel: refetch silently.
        page = self._stack.widget(self._pages_by_entry[label])
        if isinstance(page, ListDetailPanel):
            page.refresh()
    else:
        # Mark stale; user will see indicator next to that sidebar entry.
        self._stale_entries.add(label)
        self._sidebar.set_stale(label, True)
```

### Update sidebar selection handler to clear staleness

The existing sidebar selection-changed handler already swaps the stack page. Extend it to clear staleness:

```python
def _on_sidebar_selection_changed(self, label: str) -> None:
    # Existing: swap content stack
    if label in self._pages_by_entry:
        self._stack.setCurrentIndex(self._pages_by_entry[label])

    # NEW: if the entry was stale, clear the indicator and refresh.
    if label in self._stale_entries:
        self._stale_entries.discard(label)
        self._sidebar.set_stale(label, False)
        page = self._stack.widget(self._pages_by_entry[label])
        if isinstance(page, ListDetailPanel):
            page.refresh()
```

The clear-on-navigate semantics: the dot disappears the moment the user navigates to the stale entry. The refresh that follows may succeed or fail with its own visual feedback (loading state in toolbar, banner on connection loss). The dot does not represent "user has unfulfilled refresh"; it represents "data has changed since you last looked."

### `_on_watch_failed` slot

```python
def _on_watch_failed(self, message: str) -> None:
    _log.warning("File-watch refresh disabled: %s", message)
    # Manual Refresh button on each panel continues to work; the
    # user can refresh on demand. No banner, no modal — file-watch
    # is a convenience, not a correctness requirement.
```

### Cleanup on window close

Extend `closeEvent` to call `self._refresh_service.stop()` before the existing cleanup:

```python
def closeEvent(self, event: QCloseEvent) -> None:
    self._refresh_service.stop()
    self._lifecycle.terminate()
    self._client.close()
    super().closeEvent(event)
```

## Step 4 — Tests for the integration

Add `tests/crmbuilder_v2/ui/test_refresh_integration.py` (new). End-to-end tests with a real MainWindow and a real RefreshService against a tmp_path snapshot directory.

These tests do not exercise the actual API or storage system — they exercise the wire from "snapshot file modified" through "panel refresh called". The panel refresh call is intercepted by stubbing the StorageClient.

1. **Visible panel refreshes silently on data_changed for its entity.** Construct MainWindow with stub client returning predictable data. Default selected entry is Decisions. Write `decisions.json` to the snapshot dir. After debounce, assert the StorageClient's `list_decisions` was called more than once (initial load + refresh).

2. **Non-visible panel marks sidebar stale.** Default Decisions visible; write `sessions.json`. After debounce, assert the Sessions sidebar entry has a stale icon, and the StorageClient's `list_sessions` has NOT been called more than its initial.

3. **Navigating to a stale entry clears the indicator and refreshes.** Continue from test 2. Click the Sessions sidebar entry. Immediately assert the stale icon is cleared and the StorageClient's `list_sessions` is called.

4. **MainWindow construction with non-existent export_dir does not crash.** Construct MainWindow with a config that points at a non-existent directory. Assert the watch_failed signal fires (but the window itself constructs fine).

The existing tests must continue to pass.

## Step 5 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 185 prior + new tests from steps 1, 2, 4. Estimated ~200 passing, all green.

Manual verification (recommended):

1. **Live API write while UI is open.** Start the API. Launch the UI with Decisions visible. From another terminal: `curl -X POST http://127.0.0.1:8765/decisions -H "Content-Type: application/json" -d '{"identifier":"DEC-099","title":"Test","decision_date":"05-08-26","status":"Active"}'`. Within ~1 second, the new row should appear in the Decisions table without manual refresh. Then: `curl -X DELETE http://127.0.0.1:8765/decisions/DEC-099`. Within ~1 second, the row should disappear.

2. **Stale indicator on non-visible entry.** With UI on Decisions, do the curl POST/DELETE on `/sessions` instead (use a real session payload — note this is just for testing the watcher; actual session data is up to you). The Sessions sidebar entry should show the stale dot. Click Sessions; the dot disappears and the panel refreshes.

3. **Burst write coalescing.** Run a small script that POSTs five decisions back-to-back. The Decisions table should update once after ~500ms, not five times. Confirm via the panel's status label momentarily showing "Loading…" once.

4. **Watch-failure tolerance.** Temporarily move the snapshot directory away (`mv PRDs/product/crmbuilder-v2/db-export /tmp/db-export-bak`). Launch the UI. The lifecycle starts the API, panels populate (the API itself recreates the directory on first write), but the `_on_watch_failed` slot logs a warning. Manual Refresh on each panel still works. Restore: `mv /tmp/db-export-bak PRDs/product/crmbuilder-v2/db-export` and restart the UI to re-arm the watcher.

Commit shape: single commit covering all of slice F.

```
v2: ui file-watch refresh service

Implements DEC-022 file-watch refresh per implementation plan slice F.
Closes PRD AC#11.

- RefreshService (refresh.py): wraps QFileSystemWatcher to observe
  the snapshot directory; emits data_changed(entity_type) when an
  entity-type snapshot file is modified. Multi-write bursts within
  500ms coalesce to a single emission per entity type. change_log.json
  and tempfile names are filtered out.

- Sidebar gains a set_stale(label, bool) method that toggles a small
  navy-filled circle icon on stale entries.

- MainWindow constructs and owns the RefreshService. Visible-panel
  data_changed triggers a silent refresh; non-visible-panel
  data_changed marks the sidebar entry stale. Navigating to a stale
  entry clears the indicator and triggers a refresh. RefreshService
  is stopped during closeEvent.

- watch_failed handling: logs a warning, does not surface modal or
  banner. Manual Refresh button on every panel remains the fallback.

7 unit tests for RefreshService (filename mapping, debounce, ignore
list, watch failure, stop semantics) + 4 integration tests covering
the visible/non-visible/navigate-clear flows.

PRD AC#11 (live refresh) addressed.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. Writing a new decision via curl or MCP while the Decisions panel is visible causes the new row to appear within ~1 second without manual refresh. (PRD AC#11.)
2. Writing a new session while the Decisions panel is visible causes the Sessions sidebar entry to display a small dot indicator. Navigating to Sessions clears the indicator and refreshes the panel.
3. Multiple writes to the same entity type within 500ms produce a single visible refresh, not multiple.
4. `change_log.json` modifications do NOT trigger any panel refresh.
5. The manual Refresh button on every panel continues to function. (Already from slice C; verify untouched.)
6. The full v2 test suite passes, including new tests from steps 1, 2, and 4.
7. One commit on `origin/main` with the message shape above.

## Out of slice

The following are explicitly NOT in scope for slice F:

- Decision create/edit/delete dialogs — slice G.
- About dialog content, friction polish — slice H.
- Reference rendering on Sessions, Risks, Charter, Status, Topics, or Planning Items detail panes — v0.2.
- Charter/Status replace flows — v0.2.
- WebSocket or HTTP push from the API — explicitly out of scope per DEC-022.
- A "stale data" indicator on the visible panel itself (only sidebar entries get the dot — when visible, the silent refresh is the indicator). The PRD does not require this; if user feedback wants it, it's a v0.2 polish.

## Constraints

- **No new external dependencies.** `QFileSystemWatcher` is core PySide6.
- **Do not modify the API, access-layer, schema, migrations, or vocab.**
- **Do not modify the lifecycle module.**
- **Do not modify any panel implementation.** The integration is purely on the MainWindow + Sidebar side. Panels expose `refresh()` and the service calls it; panels are unaware of the file watcher's existence.
- **Do not change the manual Refresh button behavior.** It exists as the documented fallback per DEC-022 and PRD section 4.10.
- **Stop and ask if uncertain.**

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the seven gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum scenarios 1 and 2 above. Scenarios 3 and 4 are recommended.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for slice G or slice H.
- **What slice G will need** — the file-watch service automatically reflects API writes from the UI's own dialogs, so slice G's create/edit/delete dialogs do not need to manually refresh after a successful write — the next debounce-window will pick it up. Note any caveats around this.
