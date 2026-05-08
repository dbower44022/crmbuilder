# CLAUDE-CODE-PROMPT-v2-ui-D-readonly-views-round-1

**Last Updated:** 05-08-26 14:00
**Series:** v2-ui
**Slice:** D (4 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-C (commit `a356e74`)

## Purpose

Slice D delivers the first round of full read-only entity views: Decisions (replacing slice C's smoke-grade panel), Sessions, and Risks. It also fixes a defect surfaced during slice C verification — the lifecycle's `_on_process_error` always emits `spawn_failed`, but `QProcess.errorOccurred` fires for runtime crashes too, which incorrectly routes a kill-the-API-mid-session scenario to the modal "Storage server failed to start" dialog instead of the in-window crash banner.

After this slice:

- The Decisions panel renders all five PRD section 4.6 columns and a structured detail pane with field labels, scrollable long-text fields, inbound `decided_in` references rendered as clickable session links, and clickable supersedes/superseded_by links between decisions.
- The Sessions panel renders all four PRD section 4.6 columns and a structured detail pane with field labels and scrollable text for `topics_covered`, `summary`, `artifacts_produced`, and `in_flight_at_end`.
- The Risks panel renders all five PRD section 4.6 columns and a structured detail pane.
- Cross-panel navigation works: clicking a "Decided in: SES-XXX" link on a decision detail switches to Sessions and selects that row.
- The lifecycle correctly distinguishes runtime crashes from startup failures: post-ready `errorOccurred` routes to `crashed` (banner + Reconnect), pre-ready `errorOccurred` continues to route to `spawn_failed` (modal + exit).
- The base panel infrastructure grows two capabilities used here and reusable in slices E and G: a `fetch_detail_extras` hook for off-thread fetching of additional records needed for the detail pane (used here for inbound references), and a `select_record_by_identifier` method that supports cross-panel navigation.

This slice does not implement Charter, Status, Topics, Planning Items, or References panels — those are slice E. It does not implement file-watch refresh (slice F), decision dialogs (slice G), or polish (slice H).

## Project context

Slice C landed at commit `a356e74`. The data layer is solid: typed exceptions, the `StorageClient`, the `Worker` (now a `QThread` subclass per slice C's deviation), and the `ListDetailPanel` base. The smoke-grade `DecisionsPanel` exercises every layer end-to-end. Slice D replaces it and adds two siblings.

The lifecycle defect surfaced in slice C's report is unambiguous: `server_lifecycle.py:_on_process_error` always emits `spawn_failed`. Slice C's manual scenario 3 confirmed that killing an owned API mid-session manifests as a modal failure dialog and exits the app, when it should manifest as the in-window crash banner with a Reconnect button.

The implementation plan section 4 / Step D specifies the deliverables. PRD section 4.6 defines the per-entity columns. PRD section 4.5 describes the master/detail layout that slice C's base class already implements.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`. If not, configure.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice C is on `main`: `git log --oneline -5` should show `a356e74` (slice C) at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 134 tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.5 (master/detail), 4.6 (per-entity columns).
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step D in section 4.
4. Slice C's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/server_lifecycle.py` (Step 0 modifies this)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/client.py` (Step 1 extends this)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` (Step 2 extends this)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py` (Step 3 replaces this)
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` (Step 6 modifies this)
5. Storage system surface (read-only — do not modify):
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/decisions.py` — note `_enrich` adds `supersedes_identifier` and `superseded_by_identifier` to API output. Use these.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py` and `risks.py` — endpoints the new panels consume.
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/references.py` — for `GET /references/touching/{entity_type}/{entity_id}`.
6. **Tier 2 orientation** (per DEC-011): current charter, current status, SES-004, DEC-021 (sidebar + master/detail).

## Step 0 — Lifecycle fix (runtime crash → banner, not modal)

The defect: `server_lifecycle.py:_on_process_error` always emits `spawn_failed`, regardless of whether the error happens before or after the lifecycle has reached ready state. This routes runtime crashes to the modal "Storage server failed to start" dialog and exits the app.

The fix: track a `_post_ready` flag on the lifecycle. Pre-ready `errorOccurred` continues to emit `spawn_failed`. Post-ready `errorOccurred` emits `crashed` instead.

### Changes to `server_lifecycle.py`

Add an instance attribute and update three methods.

```python
def __init__(self, base_url: str, parent: QObject | None = None):
    super().__init__(parent)
    ...
    self._post_ready = False  # NEW

def _reset_for_start(self) -> None:
    ...
    self._post_ready = False  # NEW — reset on Reconnect

def start(self) -> None:
    self._reset_for_start()
    if self._probe():
        self._ownership = "external"
        _log.info("API already running at %s; using external instance", self._base_url)
        self._post_ready = True   # NEW — mark ready before emitting
        self.ready.emit()
        return
    _log.info("API not reachable at %s; spawning subprocess", self._base_url)
    self._spawn()

def _on_poll_tick(self) -> None:
    try:
        response = httpx.get(f"{self._base_url}/health", timeout=_POLL_TIMEOUT_SECONDS)
        if response.status_code == 200:
            elapsed = time.monotonic() - (self._poll_started_at or time.monotonic())
            self._stop_polling()
            _log.info("Spawned API ready after %.2fs", elapsed)
            self._post_ready = True   # NEW — mark ready before emitting
            self.ready.emit()
            return
    except Exception as exc:
        _log.debug("Readiness probe failed: %s", exc)
    ...

def _on_process_error(self, error) -> None:
    message = ""
    if self._process is not None and hasattr(self._process, "errorString"):
        try:
            message = self._process.errorString()
        except Exception:
            message = str(error)
    else:
        message = str(error)
    _log.error("QProcess error: %s", message)
    self._stop_polling()
    if self._post_ready and not self._intentional_terminate:
        # Runtime crash, not startup failure — surface to banner, not modal.
        self.crashed.emit(message)
    else:
        # Pre-ready: this is a startup failure.
        self.spawn_failed.emit(message)
```

### Tests for the lifecycle fix

In `tests/crmbuilder_v2/ui/test_server_lifecycle.py`:

1. **Pre-ready errorOccurred → spawn_failed.** New or existing test: with the lifecycle in starting state (probe failed, spawn invoked, polling not yet at ready), simulate `QProcess.errorOccurred`. Assert `spawn_failed` is emitted, NOT `crashed`. (Existing test should already cover this; verify the assertion is present.)

2. **Post-ready errorOccurred → crashed.** New test: drive the lifecycle through probe-fail → spawn → ready (set `_post_ready` to True via the normal flow). Then simulate `QProcess.errorOccurred`. Assert `crashed` is emitted, NOT `spawn_failed`.

3. **Reconnect resets `_post_ready`.** New test: drive through ready, then call `start()` again (the Reconnect path). Before the new start succeeds, simulate `errorOccurred`. Assert `spawn_failed` is emitted (we're in starting state again, not post-ready).

### Verify the fix in app.py wiring

`app.py` already wires both signals:
- `lifecycle.spawn_failed.connect(on_spawn_failed)` → modal dialog + exit
- `lifecycle.crashed.connect(window.handle_crash)` → banner

No app.py changes needed for the fix. The lifecycle change alone routes the signals correctly.

### Commit shape for the fix

This is one of two commits in slice D. The first commit is the lifecycle fix in isolation:

```
v2: ui lifecycle — runtime crash routes to banner not modal

Fixes a defect surfaced during slice C verification: QProcess.errorOccurred
fires for both startup failures and runtime crashes, but the lifecycle
always emitted spawn_failed (which app.py wires to a modal dialog +
app.quit()). Killing an owned API subprocess mid-session therefore
showed the "Storage server failed to start" dialog and exited the
application, instead of surfacing the in-window crash banner.

Adds a _post_ready flag tracking whether the lifecycle has reached
ready state. Pre-ready errorOccurred continues to emit spawn_failed
(correct for startup). Post-ready errorOccurred emits crashed
(correct for runtime crashes — routes to the banner with Reconnect).

Three new tests covering pre-ready, post-ready, and Reconnect-resets-
post-ready.
```

## Step 1 — Extend `StorageClient` with sessions, risks, and references-touching

Add the methods needed by the three panels in this slice. Keep the existing methods unchanged.

### New methods on `StorageClient`

```python
# --- sessions (read) ---
def list_sessions(self) -> list[dict]:
    return self._request("GET", "/sessions")

def get_session(self, identifier: str) -> dict:
    return self._request("GET", f"/sessions/{identifier}")

# --- risks (read) ---
def list_risks(self) -> list[dict]:
    return self._request("GET", "/risks")

def get_risk(self, identifier: str) -> dict:
    return self._request("GET", f"/risks/{identifier}")

# --- references (read) ---
def list_references_touching(self, entity_type: str, entity_id: str) -> list[dict]:
    """Return all references where the entity is either source or target.

    entity_type is one of: charter, status, decision, session, risk,
    planning_item, topic. entity_id is the identifier (e.g., "DEC-018").
    Each reference dict has keys: source_type, source_id, target_type,
    target_id, relationship_kind.
    """
    return self._request(
        "GET",
        f"/references/touching/{entity_type}/{entity_id}",
    )
```

### Tests for the new client methods

Extend `tests/crmbuilder_v2/ui/test_client.py` with at least:

- `list_sessions()` returns a list (envelope-parsed).
- `get_session("SES-X")` returns a dict; raises `NotFoundError` for missing.
- `list_risks()` returns a list.
- `get_risk("RSK-X")` returns a dict; raises `NotFoundError` for missing.
- `list_references_touching("decision", "DEC-018")` returns a list of reference dicts with the documented keys.

Each test uses `httpx.MockTransport` per the slice C pattern.

## Step 2 — Extend `ListDetailPanel` with detail-extras and navigation

Two additions to the base class.

### `fetch_detail_extras` hook

Some entity panels need additional data in the detail pane beyond the record itself — references being the canonical example. That data must be fetched off the UI thread.

```python
class ListDetailPanel(QWidget):
    ...
    def fetch_detail_extras(self, record: dict) -> dict:
        """Return extra data needed for the detail pane.

        Called from a worker thread (off the UI thread). Default returns
        {}. Subclasses override to fetch additional records.
        """
        return {}

    def render_detail(self, record: dict, extras: dict) -> QWidget:
        """Render the detail pane.

        ``extras`` is the result of fetch_detail_extras(record). Subclasses
        that don't override fetch_detail_extras receive extras={}.
        """
        ...
```

### Updated detail-rendering flow in the base class

When the user selects a row in the master list:

1. Capture the selected record.
2. Show a transient "Loading detail…" placeholder in the detail pane (a small QLabel is sufficient).
3. Spawn a worker calling `self.fetch_detail_extras(record)`.
4. On worker success: call `self.render_detail(record, extras)`; swap the detail pane to the returned widget.
5. On worker failure with `StorageConnectionError`: emit `connection_lost(str(exc))`; the panel disables (matching the existing behavior).
6. On other `StorageClientError`: log at WARNING level; render the detail pane with `extras={}` so the user still sees the basic record fields. Show a small inline error indicator (a tiny `QLabel` at the top of the detail pane saying "Detail extras unavailable: {message}") so the user knows something didn't come back.
7. Use the same stale-result protection from slice C — if the user clicks another row before the worker finishes, the result of the older worker is dropped silently.

### `navigate_requested` signal

```python
class ListDetailPanel(QWidget):
    ...
    navigate_requested = Signal(str, str)  # entity_type, identifier
```

Subclasses emit this from their `render_detail` widget when a user clicks a cross-entity link. The standard pattern: render links as `QLabel` with rich text and an `<a href="entity:identifier">…</a>` anchor; connect the label's `linkActivated` signal to a small handler on the panel that parses the href and emits `navigate_requested`.

Add a helper on the base class:

```python
def _emit_link_navigation(self, href: str) -> None:
    """Parse an "entity_type:identifier" href and emit navigate_requested."""
    if ":" not in href:
        return
    entity_type, _, identifier = href.partition(":")
    self.navigate_requested.emit(entity_type, identifier)
```

Subclasses just connect their `QLabel.linkActivated` to `self._emit_link_navigation` and emit naturally formatted hrefs.

### `select_record_by_identifier` method

```python
def select_record_by_identifier(self, identifier: str) -> bool:
    """Select the row whose record has this identifier.

    If the panel hasn't been refreshed yet (records empty), schedule
    a select-on-next-refresh and trigger a refresh. Return True if the
    row was found and selected immediately, False otherwise.
    """
```

Implementation: search `self._records`. If found, select the row. If not found and the panel hasn't been refreshed (records is empty), set `self._pending_select_identifier = identifier` and call `self.refresh()`. The base class's refresh-success handler checks `_pending_select_identifier` and selects the matching row if present.

### Tests for the base-class additions

Extend `tests/crmbuilder_v2/ui/test_list_detail_panel.py`:

- **fetch_detail_extras runs in a worker.** Stub `fetch_detail_extras` returning a fixed dict; assert `render_detail` is called with that dict on row selection.
- **fetch_detail_extras failure with ConnectionError emits connection_lost.** Stub it to raise; assert `connection_lost` was emitted.
- **fetch_detail_extras failure with NotFoundError still renders detail.** Stub it to raise NotFoundError; assert `render_detail` is called with `extras={}` and the detail pane shows the inline error indicator.
- **navigate_requested emits on link click.** Construct a panel that renders a detail with a link; simulate `linkActivated`; assert `navigate_requested` fires with the parsed entity_type and identifier.
- **select_record_by_identifier finds and selects an existing row.** Populate records; call the method; assert the table's selected row matches.
- **select_record_by_identifier on empty records triggers refresh and selects.** Mock fetch_records to return a list including the target identifier; call select_record_by_identifier before any refresh; assert the row is selected after the refresh worker completes.

## Step 3 — Full Decisions panel

Replace the smoke-grade `panels/decisions.py` with the full version per PRD section 4.6.

### Columns

Per PRD section 4.6:

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="identifier", title="Identifier", width=120),
        ColumnSpec(field="title", title="Title"),                            # stretch
        ColumnSpec(field="decision_date", title="Decision Date", width=120),
        ColumnSpec(field="status", title="Status", width=100),
        ColumnSpec(field="superseded_by_identifier", title="Superseded By", width=140),
    ]
```

`superseded_by_identifier` comes from the API enrichment in `decisions._enrich` — it's already in the response. Empty string when the decision isn't superseded.

### Detail pane fields

Use `QFormLayout` with field labels on the left and value widgets on the right. Long-text fields (`context`, `decision`, `rationale`, `alternatives_considered`, `consequences`) get a `QPlainTextEdit` set to read-only with adjusted minimum height. Short fields use `QLabel`. The whole detail pane is wrapped in a `QScrollArea` so long content scrolls within the detail pane rather than expanding the window.

Field order in the detail pane:
1. Identifier (label)
2. Title (label, larger font)
3. Decision Date (label)
4. Status (label)
5. Supersedes (clickable link if non-empty, else "—")
6. Superseded By (clickable link if non-empty, else "—")
7. Context (read-only text, multi-line)
8. Decision (read-only text, multi-line)
9. Rationale (read-only text, multi-line)
10. Alternatives Considered (read-only text, multi-line)
11. Consequences (read-only text, multi-line)
12. References — separator, then a list of references rendered from `extras["references"]`:
    - Inbound `decided_in` from a session: render as `Decided in: <a href="session:SES-002">SES-002</a>` (clickable to session)
    - Other reference kinds: render generically as `{relationship_kind} ({direction}): <link>` where direction is "from" if this decision is the target, "to" if source

### `fetch_detail_extras`

```python
def fetch_detail_extras(self, record: dict) -> dict:
    return {
        "references": self._client.list_references_touching(
            "decision", record["identifier"]
        ),
    }
```

### Navigation wiring

Connect `linkActivated` on every clickable QLabel in the detail to `self._emit_link_navigation` (from the base class).

### Don't add a "New Decision" button

That's slice G. The toolbar's `_action_layout` slot stays empty for slice D.

## Step 4 — Sessions panel

`panels/sessions.py` — new file (replace the empty stub).

### Columns

Per PRD section 4.6:

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="identifier", title="Identifier", width=120),
        ColumnSpec(field="title", title="Title"),                          # stretch
        ColumnSpec(field="session_date", title="Session Date", width=120),
        ColumnSpec(field="status", title="Status", width=120),
    ]
```

### Detail pane fields

Same `QFormLayout` + `QScrollArea` pattern. Field order:
1. Identifier
2. Title (label, larger font)
3. Session Date
4. Status
5. Topics Covered (read-only text, multi-line)
6. Summary (read-only text, multi-line)
7. Artifacts Produced (read-only text, multi-line)
8. In-Flight at End (read-only text, multi-line)
9. Conversation Reference (label — short string field)

### No `fetch_detail_extras` in slice D

The Sessions panel doesn't fetch references in slice D. The default `fetch_detail_extras` returning `{}` is fine. A future slice can add the inbound-decisions display ("Decisions decided in this session: DEC-018, DEC-019, …"), but that's not required here.

## Step 5 — Risks panel

`panels/risks.py` — new file (replace the empty stub).

### Columns

Per PRD section 4.6:

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="identifier", title="Identifier", width=120),
        ColumnSpec(field="title", title="Title"),                       # stretch
        ColumnSpec(field="probability", title="Probability", width=100),
        ColumnSpec(field="impact", title="Impact", width=100),
        ColumnSpec(field="status", title="Status", width=120),
    ]
```

### Detail pane fields

Same `QFormLayout` + `QScrollArea` pattern. Field order:
1. Identifier
2. Title (label, larger font)
3. Probability
4. Impact
5. Status
6. Description (read-only text, multi-line) — if present in API response
7. Mitigation (read-only text, multi-line) — if present in API response

The exact field set comes from the risks repository's `to_dict`/`_enrich` output. Inspect `crmbuilder-v2/src/crmbuilder_v2/access/repositories/risks.py` (or fetch a sample record at runtime) to confirm the shape. Render whatever fields are present; gracefully handle absent ones.

### Empty data is the default state

There are zero risk records in the database at the start of slice D. The panel must render correctly with an empty table — toolbar and column headers visible, detail pane shows a "Select a record to view detail" placeholder, status label shows "0 records". Verify this manually.

### No `fetch_detail_extras` in slice D

Same as Sessions — not in scope.

## Step 6 — MainWindow integration

### Replace placeholders

In `main_window.py`, the existing loop that builds placeholders for each sidebar entry currently special-cases "Decisions" with `DecisionsPanel`. Extend that to also special-case "Sessions" → `SessionsPanel` and "Risks" → `RisksPanel`. Charter, Status, Topics, Planning Items, References continue to receive placeholders (slice E replaces those).

### Wire `navigate_requested` to a router

```python
# In MainWindow.__init__:
for label, page in self._pages_by_entry.items():
    if isinstance(page, ListDetailPanel):
        page.navigate_requested.connect(self._on_navigate_requested)
        page.connection_lost.connect(self._on_panel_connection_lost)

# Method:
def _on_navigate_requested(self, entity_type: str, identifier: str) -> None:
    label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type)
    if label is None or label not in self._pages_by_entry:
        _log.warning("Navigation requested for unknown entity_type=%s", entity_type)
        return
    self._sidebar.set_selected(label)
    target = self._stack.widget(self._pages_by_entry[label])
    if isinstance(target, ListDetailPanel):
        target.select_record_by_identifier(identifier)
```

`ENTITY_TYPE_TO_SIDEBAR_LABEL` is a module-level constant:

```python
ENTITY_TYPE_TO_SIDEBAR_LABEL = {
    "charter": "Charter",
    "status": "Status",
    "decision": "Decisions",
    "session": "Sessions",
    "risk": "Risks",
    "planning_item": "Planning Items",
    "topic": "Topics",
}
```

References don't appear here — references are not first-class navigable entities in the same way; they're rendered inline.

### Auto-refresh on lifecycle.ready

This already works for the Decisions panel from slice C. Extend the existing `on_lifecycle_ready` (or equivalent) method in MainWindow to refresh whichever panel is currently visible — works automatically for the new Sessions and Risks panels since they're `ListDetailPanel` instances.

## Step 7 — Tests

Beyond the per-step tests listed above, extend `tests/crmbuilder_v2/ui/test_smoke.py`:

- Construct `MainWindow` with a stub StorageClient that returns empty lists for all read methods. Assert it constructs without raising.
- Assert the Sessions stack page is a `SessionsPanel` instance.
- Assert the Risks stack page is a `RisksPanel` instance.

Add `tests/crmbuilder_v2/ui/test_navigation.py` (new):

- **End-to-end navigate_requested.** Construct a MainWindow with stub data including a session SES-X. From the Decisions panel (with at least one decision selected and that decision's references including a `decided_in` to SES-X), simulate the link click. Assert the sidebar selection switches to "Sessions" and the SES-X row is selected in the SessionsPanel.

Existing tests must continue to pass. The constructor signatures for `MainWindow` haven't changed in this slice (lifecycle and client both already required); the new panels are additive.

## Step 8 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: all prior tests + new tests from steps 0, 1, 2, 7. Estimated ~155 passing, all green.

Manual verification (recommended):

1. **Live data render — all three panels.** Launch the UI. Navigate to Decisions; confirm five columns and ~24 rows; click a row; confirm the detail pane shows all fields and the inbound `decided_in` reference for SES-004. Click that reference; sidebar should switch to Sessions and SES-004 should be selected. Click "Decisions" in the sidebar to return; the previously-selected decision should still be selected.
2. **Sessions detail.** From the Sessions panel, select SES-004; confirm topics_covered, summary, artifacts_produced, in_flight_at_end render in the detail pane.
3. **Risks empty state.** From the Risks panel, confirm "0 records" and a placeholder in the detail pane.
4. **Lifecycle fix verification.** Launch the UI with no API running. Lifecycle spawns the API, panels populate. Externally kill the spawned API process (`pkill -f 'crmbuilder_v2.cli'`). The crash banner should appear (NOT the modal failure dialog). Click Reconnect — the API respawns, banner clears, panels re-fetch.
5. **Cross-panel navigation.** From a decision detail with a "Decided in: SES-XXX" link, click the link. Sidebar switches; row is selected; detail pane on SessionsPanel updates.

Commit shape: two commits in slice D — one for the lifecycle fix (already specified in step 0), one for the rest of the slice.

```
v2: ui read-only panels round 1 — full decisions, sessions, risks

Implements slice D of the v2-ui series per the implementation plan.

- Decisions panel: full PRD §4.6 columns (identifier, title,
  decision_date, status, superseded_by_identifier). Structured detail
  pane with field labels, scrollable long-text fields, inbound
  decided_in references rendered as clickable session links, clickable
  supersedes/superseded_by links between decisions.

- Sessions panel: PRD §4.6 columns (identifier, title, session_date,
  status). Structured detail pane with topics_covered, summary,
  artifacts_produced, in_flight_at_end, conversation_reference.

- Risks panel: PRD §4.6 columns (identifier, title, probability,
  impact, status). Structured detail pane. Empty state handled.

- ListDetailPanel base extended with fetch_detail_extras hook for
  off-thread fetching of additional records (used by decisions for
  inbound references), navigate_requested signal for cross-panel
  navigation, and select_record_by_identifier with refresh fallback.

- StorageClient extended with list_sessions, get_session, list_risks,
  get_risk, list_references_touching.

- MainWindow routes navigate_requested to a sidebar-and-row-select
  router. Decisions inbound-reference link → switch to Sessions and
  select the referenced row.

PRD §4.5 (master/detail) and §4.6 (per-entity columns) acceptance
criteria addressed.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. Decisions, Sessions, Risks sidebar entries all navigate to functional panels rendering live data with PRD §4.6 columns. (Partial PRD AC#4 — three of eight.)
2. Selecting a row in any of the three panels updates the detail pane with the full record content.
3. Inbound `decided_in` references on a decision detail are rendered as clickable session links. Clicking switches to Sessions and selects the referenced row.
4. Supersedes/superseded_by on a decision detail render as clickable links between decisions when populated.
5. Risks panel renders correctly with zero records (empty state).
6. Killing an owned API mid-session surfaces the crash banner (NOT the modal failure dialog). Reconnect respawns and refreshes panels. (PRD AC#3, fully verified.)
7. The full v2 test suite passes, including new tests from steps 0, 1, 2, and 7.
8. Two commits on `origin/main`: lifecycle fix first, then the panels work.

## Out of slice

The following are explicitly NOT in scope for slice D:

- Charter, Status, Topics, Planning Items, References panels — slice E.
- File-watch refresh service — slice F.
- Sidebar staleness indicator — slice F.
- "New Decision" button or any decision write surface — slice G.
- About dialog content, friction polish — slice H.
- Reference rendering on Sessions or Risks detail panes — defer to slice E (or a future slice).

Resist the urge to wire reference displays on Sessions and Risks. The plan keeps slice D focused on the three highest-priority entities and the cross-cutting infrastructure (`fetch_detail_extras`, `navigate_requested`, `select_record_by_identifier`). Slice E uses that infrastructure for the next four entities.

## Constraints

- **No new external dependencies.**
- **Do not modify the API or access-layer code.** The repositories already enrich decisions with `supersedes_identifier` and `superseded_by_identifier`; use them. If a needed field is missing, raise it as an open question — do not modify the API.
- **Do not modify schema, migrations, or vocab.**
- **Do not introduce session state into the StorageClient.** Methods take inputs, return outputs, raise typed exceptions. No caching layers in slice D — that's a future optimization decision.
- **Keep slice C's QThread-subclass Worker pattern.** Don't switch back to moveToThread.
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, surface it.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the eight gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum scenarios 1, 4, and 5 above. Scenarios 2 and 3 are recommended.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for slice E, recorded as a new DEC, or noted for slice H polish.
- **What slice E will need** — interface shapes from D that E should respect when adding the remaining four panels (Charter, Status, Topics, Planning Items, References).
