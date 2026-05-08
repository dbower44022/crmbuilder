# CLAUDE-CODE-PROMPT-v2-ui-C-http-client-and-list-detail-base

**Last Updated:** 05-08-26 09:00
**Series:** v2-ui
**Slice:** C (3 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-B (commit `2cfadb8`)

## Purpose

Slice C delivers the data-layer foundation that the per-entity panels in slices D and E will build on. After this slice, the UI:

- Has a typed `StorageClient` (`client.py`) that wraps `httpx.Client` synchronously, parses the storage system's response envelope, and raises typed exceptions on every non-2xx response.
- Has six typed exception classes (`exceptions.py`) covering the full error matrix from PRD section 4.11.
- Has a generic `Worker` pattern (`workers.py`) so any blocking operation runs off the UI thread with success/failure callbacks delivered via Qt signals.
- Has a reusable `ListDetailPanel` base class (`base/list_detail_panel.py`) that all entity panels in slices D and E will subclass.
- Has a working Decisions panel that fetches live data from the API, presents identifier/title/status in a master list, and shows the full record JSON in the detail pane on row selection. This is the only entity panel slice C produces — the rest stay as placeholders for slices D and E.
- Promotes any `ConnectionError` from panel-level data fetches to the existing crash banner, the same surface lifecycle uses when an owned subprocess dies.

This slice does not implement the full read-only entity panels (slices D and E), file-watch refresh (slice F), decision dialogs (slice G), or the polish pass (slice H). The Decisions panel built here is intentionally minimal — it exercises the entire stack end-to-end so slice D can replace it with the real one.

## Project context

Slice B landed at commit `2cfadb8`. The UI now has a populated `ServerLifecycle` and `CrashBanner`. The `MainWindow` takes a `lifecycle` argument, mounts the crash banner above the sidebar+stack layout, and disables the sidebar and stack on `lifecycle.crashed`. The lifecycle's own thin `httpx.get` probes against `/health` are deliberately independent of the formal `StorageClient` this slice builds — they have different lifetimes and concerns.

The implementation plan section 4 / Step C specifies the deliverables. PRD section 4.11 is the authoritative spec for the error matrix. The full REST surface the UI consumes is enumerated in `crmbuilder-v2/src/crmbuilder_v2/api/routers/`; slice C only adds the two read methods needed for the smoke-grade Decisions panel (`list_decisions` and `get_decision`) — slices D, E, and G grow `client.py` with the methods they need.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`. If not, configure.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice B is on `main`: `git log --oneline -5` should show `2cfadb8` (slice B) at or near the top.
6. Confirm the existing UI test suite passes: `uv run pytest tests/crmbuilder_v2/ui/ -v` should show 7 tests passing (1 health + 6 lifecycle + smoke set).

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.5 (master/detail), 4.10 (refresh, especially the manual Refresh button), 4.11 (error matrix). Slice C does NOT implement file-watch refresh — that's slice F.
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step C in section 4.
4. Slice B's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/server_lifecycle.py` (note: it has its own thin `httpx.get` probe; the formal StorageClient is separate)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` (the constructor signature changes again in this slice — see Step 6 below)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py`
5. Storage system surface:
   - `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py` (the `{data, meta, errors}` shape)
   - `crmbuilder-v2/src/crmbuilder_v2/api/errors.py` (status code → exception mapping on the API side; mirror this on the client side)
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/decisions.py` (the routes the smoke panel consumes)
6. **Tier 2 orientation** (per DEC-011): current charter, current status (now v5), SES-004, DEC-019 (REST as the consumed interface), DEC-021 (sidebar + master/detail).

## Step 1 — Implement `exceptions.py`

Six typed exception classes plus a base. All inherit from `Exception` (not from one another's siblings). The hierarchy is:

```
StorageClientError(Exception)              # base — never raised directly
├── ConnectionError                        # network-level failure
├── ServerError                            # 5xx
├── RequestShapeError                      # 422 — programmer error
├── NotFoundError                          # 404
├── ConflictError                          # 409
└── ValidationError                        # 400 with validation_error code
```

**Do NOT name the connection-failure class `ConnectionError`** — that shadows Python's built-in. Name it `StorageConnectionError`. Same for ValidationError if it conflicts in any module — but in this UI context, ValidationError is fine because the UI does not import from `crmbuilder_v2.access.exceptions` anywhere.

To be safe and explicit, use these exact class names:

- `StorageClientError` — abstract base, all others inherit from it.
- `StorageConnectionError` — network-level failure (e.g., httpx.ConnectError, ReadTimeout, ConnectTimeout). Carries `original: Exception | None` and `message: str`.
- `ServerError` — 5xx response. Carries `status_code: int`, `errors: list[dict]` (from the envelope), and `message: str`.
- `RequestShapeError` — 422 response. Same shape as ServerError but with code typically `request_validation_error`.
- `NotFoundError` — 404. Carries `errors: list[dict]` and `message: str`.
- `ConflictError` — 409. Carries `errors: list[dict]` and `message: str`.
- `ValidationError` — 400. Carries `errors: list[dict]` (each with `code`, `field`, `message` keys per the API's contract) and a convenience method `field_errors() -> dict[str, str]` mapping field name to first message for that field. Useful for inline-on-field error display in slice G.

Each exception's `__str__` should be the human-readable `message`, so `str(exc)` produces something useful for log lines and the status label.

Provide a module-level helper `from_response(resp: httpx.Response) -> StorageClientError` that takes a non-2xx httpx response, parses the envelope, and returns the appropriate typed exception. The mapping mirrors `crmbuilder-v2/src/crmbuilder_v2/api/errors.py`:

| HTTP status | Body shape | Exception |
|---|---|---|
| 400 (with `validation_error` code in any error) | `{"errors": [{"code", "field", "message"}, ...]}` | ValidationError |
| 400 (any other code) | same | ValidationError (still — 400 with a different code is still a validation problem) |
| 404 | `{"errors": [{"code": "not_found", "message"}]}` | NotFoundError |
| 409 | `{"errors": [{"code": "conflict_error", "message"}]}` | ConflictError |
| 422 | `{"errors": [{"code": "request_validation_error", "field", "message"}, ...]}` | RequestShapeError |
| 500+ | any | ServerError |
| any other 4xx | any | ServerError (catchall — unexpected status from the API) |

If the response body is not parseable JSON or doesn't have an `errors` list, fall back to `ServerError(status_code=resp.status_code, errors=[], message=f"Unexpected response (status {resp.status_code})")`.

## Step 2 — Implement `client.py`

The synchronous `StorageClient`. No Qt dependencies in this module — it must be testable with plain pytest, no `qtbot`. Slice C adds only the read methods needed for the smoke Decisions panel (`list_decisions` and `get_decision`); slices D, E, and G grow this client further.

### Class shape

```python
class StorageClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        request_timeout: float = 5.0,
    ) -> None: ...

    def close(self) -> None:
        # Close the owned httpx.Client (if we constructed it).

    def __enter__(self) -> StorageClient: ...
    def __exit__(self, *exc_info) -> None: ...

    # --- decisions (read) ---
    def list_decisions(self) -> list[dict]: ...
    def get_decision(self, identifier: str) -> dict: ...
```

### Constructor behavior

- If `client` is provided, the StorageClient does not own it (does not close it on `close()`). Useful for tests that want to inject a mock transport.
- If `client` is None, the StorageClient constructs its own `httpx.Client(base_url=base_url, timeout=request_timeout)` and owns it.
- Track ownership with a `_owns_client: bool` instance flag.

### Request handling

A private `_request(method: str, path: str, *, json: dict | None = None) -> object` method:

1. Calls `self._client.request(method, path, json=json)` inside a try/except.
2. On `httpx.ConnectError`, `httpx.ConnectTimeout`, `httpx.ReadTimeout`, `httpx.ReadError`, `httpx.NetworkError`: catch and raise `StorageConnectionError(message=str(e), original=e)`.
3. On any 2xx response: parse JSON body, return `body["data"]`.
4. On any non-2xx response: call `exceptions.from_response(resp)` and raise.
5. If JSON parsing of a 2xx response fails (extremely unexpected), raise `ServerError(status_code=resp.status_code, errors=[], message="Response body was not parseable JSON")`.

### Read methods

```python
def list_decisions(self) -> list[dict]:
    return self._request("GET", "/decisions")

def get_decision(self, identifier: str) -> dict:
    return self._request("GET", f"/decisions/{identifier}")
```

That's it for slice C. Add docstrings explaining the return shape (matches the API's response models). Do NOT add any other methods in this slice — D, E, and G own their respective additions.

### Logging

Use `logging.getLogger("crmbuilder_v2.ui.client")`. Log: every request with method+path at DEBUG level, every error response with status+code at INFO level. Do not log response bodies (avoids accidental capture of governance content per PRD section 5.4).

## Step 3 — Implement `workers.py`

Generic worker pattern. Every panel will use this for fetches; slice G's dialogs will use it for writes.

### Class shape

```python
class Worker(QObject):
    succeeded = Signal(object)            # arg: the return value of the callable
    failed = Signal(object)               # arg: the raised Exception
    finished = Signal()                   # always fires (after succeeded or failed)

    def __init__(self, fn: Callable[[], Any], parent: QObject | None = None) -> None: ...
    def run(self) -> None:
        # The slot connected to QThread.started.

def run_in_thread(
    fn: Callable[[], Any],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    parent: QObject | None = None,
) -> tuple[QThread, Worker]:
    """Construct a worker, move it to a new QThread, wire callbacks,
    and start. Caller must keep the returned (thread, worker) tuple
    alive until `finished` fires (typically by storing them on the
    parent widget).

    Cleanup is automatic: on `finished`, the thread quits and is
    scheduled for deletion via deleteLater.
    """
```

### Worker.run

The slot wired to `QThread.started`. Calls `self._fn()`; on success emits `succeeded(result)`; on any `Exception` emits `failed(exc)`; always emits `finished` afterwards.

`KeyboardInterrupt` and `SystemExit` propagate normally — do not catch.

### Thread management notes

- The thread quits in response to `Worker.finished` via a connection that calls `thread.quit()`.
- After the thread emits `finished`, both the thread and the worker are scheduled for deletion via `deleteLater()`. This avoids leaking QThread instances over a long session with many fetches.
- Callers (panels) must keep a reference to the (thread, worker) tuple in an instance attribute until they observe `finished`. Otherwise garbage collection can destroy the worker before the thread has fired its slot. The list of in-flight workers is kept in `_in_flight_workers` on the panel; on `finished`, the entry is removed.

### Tests for workers

`tests/crmbuilder_v2/ui/test_workers.py` (new):

1. **Successful run.** `run_in_thread(lambda: 42, on_success=cb)` — `qtbot.waitSignal(worker.finished)`; `cb` was called with 42.
2. **Failed run.** `run_in_thread(lambda: 1/0, on_error=cb)` — `cb` was called with a `ZeroDivisionError` instance.
3. **`finished` always fires.** Both for success and failure.

## Step 4 — Implement `base/list_detail_panel.py`

The reusable master/detail base. Per PRD section 4.5.

### Class shape

```python
class ListDetailPanel(QWidget):
    """Abstract base for entity panels.

    Subclasses implement:
    * entity_title() -> str
    * fetch_records() -> list[dict]              # called from a worker thread
    * list_columns() -> list[ColumnSpec]
    * render_detail(record: dict) -> QWidget     # widget shown in the detail pane

    The base class owns: top toolbar, list (QTableView), detail pane,
    refresh wiring, status label, in-flight worker tracking, and
    connection-loss promotion.
    """

    connection_lost = Signal(str)   # promoted to main window → crash banner

    def __init__(self, client: StorageClient, parent: QWidget | None = None): ...
    def refresh(self) -> None: ...                # public: triggers a fetch
    def set_enabled_state(self, enabled: bool) -> None: ...   # disable on disconnection
```

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ [Title]  [Refresh]  [Status: 12 records]      [Action slot]  │  ← toolbar
├──────────────────────┬───────────────────────────────────────┤
│  list pane (QTable)  │  detail pane (QStackedWidget)         │
│  ~40% width          │  ~60% width                           │
│                      │                                       │
└──────────────────────┴───────────────────────────────────────┘
```

Use a `QSplitter(Qt.Horizontal)` to allow the user to drag the divider. Initial sizes: 40/60.

### ColumnSpec

```python
@dataclass(frozen=True)
class ColumnSpec:
    field: str                    # key in the record dict
    title: str                    # column header text
    width: int | None = None      # initial pixel width; None = stretch
```

### Toolbar

Title is a `QLabel` with bold font (slightly larger than body). Refresh is a `QPushButton` labeled "Refresh"; clicking it calls `self.refresh()`. Status label sits to the right of Refresh; left-aligned with text like `"12 records"` or `"Loading…"` or `"Connection lost"`. The action-button slot is a `QHBoxLayout` placeholder on the far right, exposed as `self._action_layout` for subclasses (slice G's Decisions panel adds a "New Decision" button there; v0.1 panels other than Decisions leave it empty).

### Refresh wiring

- `refresh()` sets the status label to "Loading…", spawns a worker calling `self.fetch_records()`, on success populates the QTableView's model and sets the status to `"{n} records"`, on error handles per the rules below.
- A new refresh while one is in flight cancels the in-flight one (or simply lets it complete and ignores its result — simplest is "ignore stale results"; mark each refresh with an incrementing counter and only honor results from the latest).
- On `StorageConnectionError`: emit `connection_lost(str(exc))`, set status label to `"Connection lost"`, leave the table populated with whatever stale data was last fetched.
- On any other `StorageClientError`: set status label to `f"Error: {exc.message}"` (truncate to 80 chars). Leave table populated. Log the full exception at WARNING level. Do NOT emit `connection_lost` — these are domain errors, not connectivity errors.

### Selection → detail

The QTableView uses `QAbstractItemView.SelectRows` and `SingleSelection`. On `currentChanged`, the base class calls `self.render_detail(self._records[row])` and swaps the detail pane to the returned widget.

### Set-enabled-state

`set_enabled_state(False)` disables the toolbar buttons, the QTableView, and the detail pane (greys them visually). Used by `MainWindow` when `lifecycle.crashed` fires. `set_enabled_state(True)` re-enables and triggers a fresh `refresh()`.

### Tests for the base panel

`tests/crmbuilder_v2/ui/test_list_detail_panel.py` (new):

1. **Construction.** Construct with a stub client, assert layout structure exists (toolbar, splitter, list, detail).
2. **Refresh populates the table.** Stub `fetch_records()` returning a fixed list; call `refresh()`; `qtbot.waitSignal` on the finished signal of the worker; assert the table has the expected row count.
3. **Connection error promotes to signal.** Stub `fetch_records()` to raise `StorageConnectionError`; call `refresh()`; assert `connection_lost` signal was emitted; assert the status label says "Connection lost".
4. **Domain error stays inline.** Stub `fetch_records()` to raise `NotFoundError`; assert status label shows the error; `connection_lost` was NOT emitted.

A small `_FakePanel(ListDetailPanel)` helper subclass in the test module supplies the abstract methods.

## Step 5 — Implement smoke-grade `panels/decisions.py`

The minimum viable Decisions panel. Slice D replaces this with the real one (full PRD-section-4.6 columns, proper detail rendering, references display). Slice C's version exercises every layer of the stack end-to-end.

```python
class DecisionsPanel(ListDetailPanel):
    def entity_title(self) -> str:
        return "Decisions"

    def fetch_records(self) -> list[dict]:
        return self._client.list_decisions()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="identifier", title="Identifier", width=120),
            ColumnSpec(field="title", title="Title"),
            ColumnSpec(field="status", title="Status", width=100),
        ]

    def render_detail(self, record: dict) -> QWidget:
        # Slice C: dump JSON. Slice D replaces with formatted detail.
        text = json.dumps(record, indent=2, default=str)
        widget = QPlainTextEdit()
        widget.setReadOnly(True)
        widget.setPlainText(text)
        return widget
```

That's the entire panel for slice C. No "New Decision" button (slice G), no inline references (slice D), no formatting (slice D). Three columns, one read-only JSON dump in the detail pane.

## Step 6 — Wire StorageClient and DecisionsPanel into `main_window.py`

### Constructor signature change

```python
def __init__(self, lifecycle: ServerLifecycle, client: StorageClient):
    ...
```

The window now requires both. Store the client on `self._client`.

### Replace the Decisions placeholder

In the existing loop that builds placeholder widgets for each sidebar entry, special-case `"Decisions"`: instead of constructing a `QLabel`, construct a `DecisionsPanel(self._client)`. All other entries continue to receive placeholders.

Connect `decisions_panel.connection_lost` to a new method `self._on_panel_connection_lost(message: str)` that:
- Logs the message at WARNING level.
- Shows the existing crash banner (`self._crash_banner.show_with_message("Storage server unreachable.")`).
- Disables sidebar and stack via `setEnabled(False)`. (The lifecycle's `crashed` slot does the same — keep both code paths idempotent.)

When the user clicks Reconnect on the banner (the existing `crash_banner.reconnect_requested` signal), the existing slice-B flow re-runs `lifecycle.start()`. On `lifecycle.ready` after a reconnect, the new behavior added in this slice is to:
- Re-enable sidebar and stack.
- Call `self._refresh_current_panel()`, which calls `refresh()` on the currently visible panel if it is a `ListDetailPanel`. (Placeholders are unaffected; only the Decisions panel is a real panel in slice C.)

### Update `app.py`

In `main()`, after constructing the lifecycle, also construct the StorageClient:

```python
client = StorageClient(base_url=base_url, request_timeout=5.0)
window = MainWindow(lifecycle=lifecycle, client=client)
```

The client is closed when the window closes — extend the existing `closeEvent` in `MainWindow` to call `self._client.close()` after `lifecycle.terminate()`.

### Initial refresh on startup

After the lifecycle emits `ready` for the first time, call the visible panel's `refresh()` so live data appears without the user having to click Refresh. Wire this in the `lifecycle.ready` slot in `app.py` (or in `main_window.py` — choose whichever yields the cleaner code; my recommendation is for `main_window.py` to expose a `on_lifecycle_ready()` method that `app.py` connects to).

## Step 7 — Tests

Beyond the per-step tests already specified above:

### `tests/crmbuilder_v2/ui/test_client.py` (new)

Comprehensive coverage of envelope parsing and exception mapping. Use `httpx.MockTransport` to fake every response shape. Test cases:

1. **Successful 200 with `data` field** → returns the data payload.
2. **400 with `validation_error` code** → raises `ValidationError`; `field_errors()` returns the right mapping.
3. **400 with multiple errors on different fields** → `ValidationError.errors` length matches; `field_errors()` returns first message per field.
4. **404** → raises `NotFoundError` with the message from the envelope.
5. **409** → raises `ConflictError` with the message from the envelope.
6. **422 from FastAPI** → raises `RequestShapeError`.
7. **500** → raises `ServerError` with status_code=500.
8. **502** → raises `ServerError` with status_code=502 (catchall for unexpected non-2xx).
9. **Unparseable JSON in non-2xx** → falls back to `ServerError`.
10. **httpx.ConnectError** → raises `StorageConnectionError` with the original exception attached.
11. **httpx.ReadTimeout** → raises `StorageConnectionError`.
12. **`get_decision` for an existing ID** → returns the dict.
13. **`get_decision` for a missing ID** → raises `NotFoundError`.

The minimum is one test per exception class; aim for the full list above for confidence.

### `tests/crmbuilder_v2/ui/test_smoke.py` (extend)

Add: construct `MainWindow(lifecycle=stub, client=stub_client)` with a stub StorageClient that returns `[]` for `list_decisions()`. Assert the window constructs without raising; assert the Decisions stack page is a `DecisionsPanel` instance. The existing tests must continue to pass — the constructor signature change means existing tests need to pass a stub client.

### `tests/crmbuilder_v2/ui/conftest.py` (extend)

Add a `client_stub` fixture and a `mock_transport` helper for httpx-based tests.

## Step 8 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 107 prior tests + new tests from steps 3, 4, 7. Estimated total around 130 passing, all green.

Manual verification (recommended):

1. Start with no API running. Launch `uv run crmbuilder-v2-ui`. The lifecycle should spawn the API, the splash should dismiss, the Decisions panel should populate with the 24 decisions currently in the database. Click rows; the detail pane should show the JSON of each.
2. Click Refresh in the toolbar. The status label briefly says "Loading…" then returns to "24 records".
3. Kill the API subprocess externally. The crash banner should appear (lifecycle's `crashed` path). Click Reconnect — the API respawns, the banner clears, and the Decisions panel re-fetches automatically.
4. With the API running, navigate to a non-Decisions sidebar entry. The placeholder text should show. Navigate back to Decisions; the panel should be unchanged (no re-fetch on tab switch — that's slice F's territory).

Commit shape: one commit covering all of slice C.

```
git commit -m "v2: ui storage client, list/detail base, smoke decisions panel

Implements the data-layer foundation for the v2 UI per implementation
plan slice C and DEC-019 (REST as the consumed interface).

- exceptions.py: six typed exceptions covering the PRD §4.11 error
  matrix (StorageConnectionError, ServerError, RequestShapeError,
  NotFoundError, ConflictError, ValidationError) plus a base
  StorageClientError. ValidationError carries per-field errors with
  a field_errors() convenience method for slice G's inline display.

- client.py: synchronous StorageClient wrapping httpx.Client. Parses
  the {data, meta, errors} envelope, raises typed exceptions on
  every non-2xx response, and exposes list_decisions/get_decision
  for slice C's smoke panel. Slices D, E, and G grow this further.

- workers.py: generic Worker QObject + run_in_thread helper.
  Off-UI-thread blocking-call execution with success/failure callbacks
  delivered as Qt signals. Auto-cleanup on finished.

- base/list_detail_panel.py: reusable master/detail base widget.
  Toolbar, splitter, QTableView, detail pane, refresh wiring, status
  label, in-flight worker tracking, connection-loss promotion to a
  signal the main window wires to the existing crash banner.

- panels/decisions.py: smoke-grade Decisions panel using the base.
  Three columns (identifier/title/status), JSON-dump detail. Slice D
  replaces this with the full PRD §4.6 column set and formatted detail.

- main_window.py: constructor now takes a StorageClient; replaces the
  Decisions placeholder with the live panel; wires panel-level
  connection_lost to the existing crash banner; auto-refreshes the
  visible panel on lifecycle.ready (initial load and post-reconnect).

- app.py: constructs the StorageClient and passes it to MainWindow.
  Closes the client on window close.

PRD §4.5 (master/detail), §4.11 (error matrix) acceptance criteria
addressed. PRD §4.10 (refresh) addressed only for the manual Refresh
button; file-watch refresh lands in slice F."
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. Navigating to the Decisions sidebar entry renders a table populated from live API data with three columns (identifier, title, status). (Partial PRD AC#4 — one entity wired.)
2. Selecting a row in the Decisions table renders the full record JSON in the detail pane.
3. Clicking the Refresh button in the toolbar refetches from the API; status label shows "Loading…" briefly, then "{n} records".
4. Killing the API mid-session surfaces the crash banner via lifecycle.crashed (slice B path) and the Decisions panel becomes disabled. Clicking Reconnect respawns the API, clears the banner, re-enables the panel, and triggers a fresh fetch.
5. Killing the API in a way that does NOT trigger lifecycle.crashed (e.g., an externally-launched API that the lifecycle does not own) — the panel's next request raises StorageConnectionError; the banner appears via the panel's `connection_lost` promotion. Reconnect re-runs lifecycle.start, which finds the API gone and re-spawns its own.
6. The full v2 test suite passes, including all new tests from steps 3, 4, and 7.
7. One commit on `origin/main` with the message shape above.

## Out of slice

The following are explicitly NOT in scope for slice C:

- The full read-only Decisions, Sessions, Risks panels — slice D. Slice C's Decisions panel is intentionally minimal.
- Charter, Status, Topics, Planning Items, References panels — slice E.
- File-watch refresh service — slice F.
- Decision create/edit/delete dialogs and write methods on the StorageClient — slice G.
- About dialog content, friction polish — slice H.
- The "stale" sidebar indicator — slice F.

Resist the urge to write the full Decisions panel here. The smoke-grade version in this slice exists to prove every layer end-to-end before slice D builds on it.

## Constraints

- **No new external dependencies.** `httpx` and `PySide6` are already deps. Tests use `pytest-qt` (already a dev dep) and `httpx.MockTransport`.
- **Do not modify the API.** Any error envelope or status code change should be raised as an open question in the report, not silently fixed in C. The API is the contract; the client mirrors it.
- **Do not modify access-layer code, schema, migrations, or vocab.**
- **Do not modify the lifecycle module.** Slice B is complete. The crash-banner integration in this slice rides on top of the existing lifecycle signals.
- **The StorageClient must have no Qt dependencies.** It is a pure Python module so it can be tested with plain pytest. Qt-coupled behavior (workers, signals) lives in `workers.py` and the panels.
- **Do not name the network exception class `ConnectionError`.** Use `StorageConnectionError` to avoid shadowing the built-in.
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, surface it rather than choosing silently.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the seven gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — short report on whichever of the four manual scenarios you ran. At minimum scenario 1 (live data render) and scenario 3 (crash banner + reconnect with auto-refresh).
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for slice D, recorded as a new DEC, or noted for slice H polish.
- **What slice D will need** — interface shapes from C that D should respect when growing the Decisions panel into the full version and adding Sessions and Risks.
