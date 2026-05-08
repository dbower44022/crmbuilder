# CLAUDE-CODE-PROMPT-v2-ui-E-readonly-views-round-2

**Last Updated:** 05-08-26 17:00
**Series:** v2-ui
**Slice:** E (5 of 8)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-implementation-plan.md`
**Predecessor slice:** v2-ui-D (commit `b4f128e`)

## Purpose

Slice E delivers the second round of full read-only entity views, completing PRD acceptance criterion AC#4 ("all eight sidebar entries navigate to functional read-only panels"). After this slice:

- The Charter panel renders all charter versions, marks the current version visually, and displays the selected version's payload as a structured key/value view.
- The Status panel renders all status versions with the same versioned-list pattern.
- The Topics panel renders topics with hierarchical indentation in the Name column (parent topics first, children indented under them).
- The Planning Items panel renders all planning items with PRD section 4.6 columns.
- The References panel is list-only (no detail pane), with filter dropdowns above the table for source type and target type, and clickable Source/Target cells that navigate to the referenced record.
- A new `VersionedPanel` base class lives at `base/versioned_panel.py`, used by Charter and Status. It is a variant of `ListDetailPanel` whose list shows version + created_at + current marker.
- The base `ListDetailPanel` gains a `_has_detail_pane` flag (default `True`) so subclasses like References can render list-only without the detail splitter.

This slice does not implement file-watch refresh (slice F), decision dialogs (slice G), or polish (slice H). It does not add reference rendering to Sessions, Risks, Charter, Status, or Topics — that is deferred consistently with slice D's scope discipline.

## Project context

Slice D landed two commits: `78ad698` (lifecycle fix) and `b4f128e` (full Decisions/Sessions/Risks panels with cross-panel navigation infrastructure). The base `ListDetailPanel` already supports `fetch_detail_extras`, `navigate_requested`, and `select_record_by_identifier`. The MainWindow router (`ENTITY_TYPE_TO_SIDEBAR_LABEL` plus `_on_navigate_requested`) handles all eight entity types — adding slice E's panels just registers them; the router needs no changes.

The implementation plan section 4 / Step E specifies the deliverables. PRD section 4.6 defines the per-entity columns, including the versioned variant for Charter and Status.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report.
3. Confirm git identity is set: `Doug <doug@dougbower.com>`. If not, configure.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice D is on `main`: `git log --oneline -5` should show `b4f128e` (panels) and `78ad698` (lifecycle fix) at or near the top.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v` should show 154 tests passing.

## Reading order

1. `crmbuilder/CLAUDE.md` — universal entry.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.1.md` — re-read sections 4.5 (master/detail), 4.6 (per-entity columns including the Charter/Status versioned variant).
3. `PRDs/product/crmbuilder-v2/ui-implementation-plan.md` — re-read Step E in section 4.
4. Slice D's actual code:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — slice E extends this with the `_has_detail_pane` flag.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/decisions.py`, `sessions.py`, `risks.py` — patterns to mirror.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` — slice E adds branches for Charter, Status, Topics, Planning Items, References.
5. Storage system surface (read-only — do not modify):
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/charter.py`, `status.py` (versioned routes)
   - `crmbuilder-v2/src/crmbuilder_v2/api/routers/topics.py`, `planning_items.py`, `references.py`
   - `crmbuilder-v2/src/crmbuilder_v2/access/repositories/topics.py` — note `_enrich` adds `parent_topic_identifier`.
6. **Tier 2 orientation** (per DEC-011): current charter, current status (now v5), SES-004, DEC-021 (sidebar + master/detail).

## Step 1 — Extend `StorageClient`

Add the methods needed by the five new panels.

```python
# --- charter (read) ---
def list_charter_versions(self) -> list[dict]:
    return self._request("GET", "/charter/versions")

def get_charter_version(self, version: int) -> dict:
    return self._request("GET", f"/charter/versions/{version}")

# --- status (read) ---
def list_status_versions(self) -> list[dict]:
    return self._request("GET", "/status/versions")

def get_status_version(self, version: int) -> dict:
    return self._request("GET", f"/status/versions/{version}")

# --- topics (read) ---
def list_topics(self) -> list[dict]:
    return self._request("GET", "/topics")

def get_topic(self, identifier: str) -> dict:
    return self._request("GET", f"/topics/{identifier}")

# --- planning items (read) ---
def list_planning_items(self) -> list[dict]:
    return self._request("GET", "/planning-items")

def get_planning_item(self, identifier: str) -> dict:
    return self._request("GET", f"/planning-items/{identifier}")

# --- references (full list, read) ---
def list_references(self) -> list[dict]:
    return self._request("GET", "/references")
```

Note: `list_references_touching` is already in place from slice D and uses the dict-shape return (`{as_source, as_target}`). The new `list_references` returns a flat list of all references, used by the References panel.

### Tests

Extend `tests/crmbuilder_v2/ui/test_client.py`:

- `list_charter_versions()` returns a list (envelope-parsed).
- `get_charter_version(2)` returns a dict; raises `NotFoundError` for missing.
- Same for `list_status_versions` / `get_status_version`.
- `list_topics()` returns a list (empty list is valid — the database currently has zero topics).
- `get_topic("TOP-X")` raises `NotFoundError` (no topic data exists).
- `list_planning_items()` returns a list (empty list valid).
- `list_references()` returns a list with the expected shape (each record has `source_type`, `source_id`, `target_type`, `target_id`, `relationship`).

## Step 2 — Extend `ListDetailPanel` with the `_has_detail_pane` flag

A small base-class change so the References panel can render list-only without the detail splitter.

### Changes to `base/list_detail_panel.py`

Add a class-level attribute (overridable per subclass):

```python
class ListDetailPanel(QWidget):
    # Subclasses can set False to render list-only with no detail pane.
    # The toolbar and master list still appear; the detail-pane workflow
    # (loading state, fetch_detail_extras, render_detail) is skipped.
    _has_detail_pane: ClassVar[bool] = True

    def __init__(self, client: StorageClient, parent: QWidget | None = None):
        ...
        if self._has_detail_pane:
            # existing splitter + detail pane construction
            ...
        else:
            # list-only layout: toolbar on top, table below, no splitter
            ...
```

Behavior changes when `_has_detail_pane` is `False`:

- Layout uses a `QVBoxLayout` containing the toolbar widget and the table directly (no `QSplitter`, no detail container).
- The `currentChanged` selection handler does not spawn a `fetch_detail_extras` worker and does not call `render_detail`.
- `fetch_detail_extras` and `render_detail` remain on the class (subclasses can still define them harmlessly), but the base does not call them when `_has_detail_pane` is `False`.

### Tests

Extend `tests/crmbuilder_v2/ui/test_list_detail_panel.py`:

- **List-only panel renders without a detail pane.** Construct a `_FakePanel` subclass that sets `_has_detail_pane = False`. Assert the widget has no `QSplitter` child and no detail-loading flow runs on row selection.

## Step 3 — Implement `VersionedPanel` base class

`base/versioned_panel.py` — new file (replace the docstring stub).

### Class shape

```python
class VersionedPanel(ListDetailPanel):
    """Variant of ListDetailPanel for singletons-with-history.

    Charter and Status are the v2 entities that fit this pattern: a
    single logical record with a full version history kept on every
    write. The list shows version + created_at + current marker; the
    detail pane shows the selected version's payload as a structured
    key/value view.

    Subclasses implement:
    * entity_title() -> str
    * fetch_records() -> list[dict]   (returns version dicts in newest-first order)
    """

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="version", title="Version", width=80),
            ColumnSpec(field="created_at", title="Created", width=200),
            ColumnSpec(field="_current_marker", title="Current", width=80),
        ]

    def fetch_detail_extras(self, record: dict) -> dict:
        # Versioned records carry their payload inline; no extra fetch needed.
        return {}

    def render_detail(self, record: dict, extras: dict) -> QWidget:
        return self._render_payload(record.get("payload") or {})

    def _render_payload(self, payload: dict) -> QWidget:
        """Render an arbitrary payload dict as a structured key/value view.

        Top-level keys become QFormLayout rows. String values render as
        QLabel (short) or QPlainTextEdit read-only (long, threshold ~80
        chars). Dict and list values render as QPlainTextEdit read-only
        with json.dumps(value, indent=2). Other types render as str().

        The whole thing is wrapped in a QScrollArea so long content
        scrolls within the detail pane.
        """
```

### Synthetic `_current_marker` field

Override `fetch_records` in the base `VersionedPanel.fetch_records` is abstract — subclasses provide raw records. The base class's refresh path then post-processes records to add the synthetic `_current_marker` field:

- For records where `is_current` is True (or version equals the maximum), `_current_marker = "✓"`.
- Otherwise, `_current_marker = ""`.

The post-processing happens in `VersionedPanel.refresh()` — override the base's `refresh()` to fetch records, augment with the marker, then continue the normal table-population flow.

A simpler implementation: make `fetch_records` a hook that returns raw records, and add a `_post_process_records(records) -> records` hook on the base that defaults to identity. `VersionedPanel` overrides `_post_process_records` to add `_current_marker`. The base panel's refresh flow calls `_post_process_records` between fetch and table update.

Either approach works; choose the cleaner one.

### Default selection on first load

After the first refresh completes, `VersionedPanel` should auto-select the current version row (the one with `is_current=True`). This way the user sees the current version's payload immediately when they navigate to Charter or Status.

### Tests

Add `tests/crmbuilder_v2/ui/test_versioned_panel.py` (new):

- **`_current_marker` is set correctly.** Mock fetch_records returning two records, one with `is_current=True`. Assert the panel renders with `_current_marker="✓"` for the current row and `""` for the other.
- **`render_detail` renders payload as form rows.** With a payload dict like `{"name": "test", "long_text": "x" * 200, "items": [1, 2, 3]}`, assert the resulting widget has a QFormLayout with one row per top-level key, and that the long string and the list render as QPlainTextEdit while the short string renders as QLabel.
- **Default selection on first load is the current version.** After refresh completes, assert the table's selected row is the one with `_current_marker="✓"`.

## Step 4 — Implement `panels/charter.py`

`panels/charter.py` — new content (replace the docstring stub).

```python
class CharterPanel(VersionedPanel):
    def entity_title(self) -> str:
        return "Charter"

    def fetch_records(self) -> list[dict]:
        return self._client.list_charter_versions()
```

That's the entire panel. The list shows all charter versions newest-first (the API already orders them descending by version), the current version is marked, and the detail pane renders each version's payload via the inherited `render_detail`.

## Step 5 — Implement `panels/status.py`

`panels/status.py` — new content (replace the docstring stub). Identical pattern to Charter.

```python
class StatusPanel(VersionedPanel):
    def entity_title(self) -> str:
        return "Status"

    def fetch_records(self) -> list[dict]:
        return self._client.list_status_versions()
```

## Step 6 — Implement `panels/topics.py` with hierarchical indentation

`panels/topics.py` — new content (replace the docstring stub).

### Columns per PRD section 4.6

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="identifier", title="Identifier", width=120),
        ColumnSpec(field="_display_name", title="Name"),                     # stretch, indented
        ColumnSpec(field="parent_topic_identifier", title="Parent Topic", width=160),
    ]
```

The `_display_name` field is a synthetic column showing the topic's name with leading whitespace based on its depth in the parent hierarchy.

### Hierarchy build in `fetch_records`

```python
def fetch_records(self) -> list[dict]:
    raw = self._client.list_topics()
    return self._build_hierarchical_view(raw)

def _build_hierarchical_view(self, topics: list[dict]) -> list[dict]:
    """Sort topics so parents precede children, indent the Name column.

    Topics with parent_topic_identifier=None are roots (depth 0).
    Each root is followed by its children (depth 1), recursively.
    The synthetic `_display_name` field is `"    " * depth + name`.
    Cycles (a topic that is its own ancestor) are tolerated by not
    re-visiting an already-visited topic; if the data is cyclic, the
    resulting display will skip the cycle's tail rather than recurse.
    """
```

The build algorithm:

1. Build a mapping from identifier → topic dict.
2. Build a mapping from parent_identifier → list of children (using `parent_topic_identifier`).
3. Recursively walk from each root, emitting topics in depth-first order with depth tracking.
4. For each emitted topic, set `_display_name = "    " * depth + topic["name"]` (four spaces per level — visually distinct without being too aggressive).
5. Handle orphans (topics whose `parent_topic_identifier` is set but the parent isn't in the records): append at the end at depth 0 with a small indicator (e.g., `name + " (orphan)"`).

### Detail pane

Use the same `QFormLayout` + `QScrollArea` pattern from the slice D panels. Field order:
1. Identifier
2. Name (label, larger font)
3. Parent Topic (clickable link if `parent_topic_identifier` is non-null and present in the records, else "—")
4. Description (read-only multi-line text)

The Parent Topic link (when populated) emits `navigate_requested("topic", parent_topic_identifier)`, which routes via `select_record_by_identifier` on the same panel — the user clicks and the table jumps to that row.

### Empty data

Topics has zero records currently. The panel must render correctly with an empty table. Status label shows "0 records"; detail pane shows the standard placeholder.

## Step 7 — Implement `panels/planning_items.py`

`panels/planning_items.py` — new content (replace the docstring stub).

### Columns per PRD section 4.6

```python
def list_columns(self) -> list[ColumnSpec]:
    return [
        ColumnSpec(field="identifier", title="Identifier", width=120),
        ColumnSpec(field="title", title="Title"),                  # stretch
        ColumnSpec(field="item_type", title="Type", width=140),
        ColumnSpec(field="status", title="Status", width=100),
    ]
```

### Detail pane fields

`QFormLayout` + `QScrollArea`. Field order:
1. Identifier
2. Title (label, larger font)
3. Type (`item_type`)
4. Status
5. Resolution Reference (if non-null and non-empty; else "—")
6. Description (read-only multi-line text)

### Empty data

Planning items has zero records currently. Same empty-state behavior as Topics.

### No `fetch_detail_extras` in slice E

Default `{}`. Reference rendering on planning items defers to a future slice.

## Step 8 — Implement `panels/references.py` (list-only with filters)

`panels/references.py` — new content (replace the docstring stub).

This panel is structurally different from the others: list-only (uses the new `_has_detail_pane = False` flag from Step 2), with filter dropdowns above the table, and clickable Source/Target cells that navigate.

### Class shape

```python
class ReferencesPanel(ListDetailPanel):
    _has_detail_pane = False

    def entity_title(self) -> str:
        return "References"

    def fetch_records(self) -> list[dict]:
        return self._client.list_references()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="_source_display", title="Source", width=180),
            ColumnSpec(field="relationship", title="Relationship", width=160),
            ColumnSpec(field="_target_display", title="Target", width=180),
        ]
```

The synthetic display fields are computed in `_post_process_records` (same hook the VersionedPanel uses, lifted to the base class):

```python
def _post_process_records(self, records: list[dict]) -> list[dict]:
    for r in records:
        r["_source_display"] = f'{r["source_type"]}:{r["source_id"]}'
        r["_target_display"] = f'{r["target_type"]}:{r["target_id"]}'
    return records
```

### Filter strip above the table

A `QHBoxLayout` widget added between the toolbar and the table. Two `QComboBox` widgets:

- **Source type:** populated dynamically from the unique source types present in the loaded records, plus an "All" entry at the top. Default "All".
- **Target type:** same pattern.

When either dropdown changes, re-filter the displayed records. The full record list is cached on the panel; filtering happens client-side via a `QSortFilterProxyModel` set on the QTableView, or by maintaining a `_filtered_records` list and updating the table model directly.

The filter strip is part of the panel's main widget layout, sitting above the table, only when `_has_detail_pane = False`. The base class's list-only layout from Step 2 should expose a hook (`_filter_strip_widget(self) -> QWidget | None`, defaults to None) that subclasses can override to insert a widget between the toolbar and the table.

### Clickable Source and Target cells

Cells in the Source and Target columns navigate when clicked. Implementation: connect the QTableView's `clicked(index)` signal to a slot that:

1. Identifies which column was clicked (Source or Target).
2. Reads the corresponding record's source_type/source_id or target_type/target_id.
3. Maps source_type/target_type to a sidebar entity_type (skip if it doesn't map — e.g., a `relationship` field doesn't navigate).
4. Emits `navigate_requested(entity_type, identifier)`.

Single-click navigation is appropriate here because there's no detail pane to interact with — the click would otherwise do nothing useful.

### Empty data

The references table is non-empty (24 records currently). The empty-state behavior still needs to be correct — verify by setting both filters to types that yield zero matches and confirming "0 records" status.

## Step 9 — MainWindow integration

Extend the if/elif ladder in `main_window.py` that constructs panels for sidebar entries. Add branches for:

- "Charter" → `CharterPanel(self._client)`
- "Status" → `StatusPanel(self._client)`
- "Topics" → `TopicsPanel(self._client)`
- "Planning Items" → `PlanningItemsPanel(self._client)`
- "References" → `ReferencesPanel(self._client)`

All five new panels are `ListDetailPanel` subclasses (Charter and Status via `VersionedPanel`), so the existing wiring for `connection_lost` and `navigate_requested` applies automatically.

The `ENTITY_TYPE_TO_SIDEBAR_LABEL` map already covers all entity types — no changes needed.

After this step, every sidebar entry routes to a real panel. No placeholders remain.

## Step 10 — Tests

Beyond the per-step tests, extend `tests/crmbuilder_v2/ui/test_smoke.py`:

- Construct `MainWindow` with a stub `StorageClient` returning empty lists for all read methods. Assert it constructs without raising.
- Assert each of the five new panel types is instantiated for the corresponding sidebar entry: `CharterPanel`, `StatusPanel`, `TopicsPanel`, `PlanningItemsPanel`, `ReferencesPanel`.

Add `tests/crmbuilder_v2/ui/test_topics_hierarchy.py` (new):

- **Hierarchy build orders parents before children with correct indentation.** Mock topics: TOP-1 (root), TOP-2 (child of TOP-1), TOP-3 (root), TOP-4 (child of TOP-3). Assert the order is TOP-1, TOP-2, TOP-3, TOP-4 with `_display_name` indented by 4 spaces for children.
- **Orphans are tolerated.** Mock topics where one has `parent_topic_identifier="MISSING"`. Assert the orphan appears with the "(orphan)" indicator.
- **No infinite recursion on cycles.** Mock topics where TOP-A points to TOP-B and TOP-B points to TOP-A. Assert the build completes without recursion error and emits each topic at most once.

Add `tests/crmbuilder_v2/ui/test_references_panel.py` (new):

- **Filters narrow the visible rows.** Set both filters to "All", assert all records visible; set source filter to "session", assert only session-source rows visible.
- **Clicking a Source cell emits navigate_requested.** Construct the panel with mock records; simulate a click on a Source cell; assert `navigate_requested` was emitted with the correct entity_type and identifier.
- **Clicking a Target cell emits navigate_requested.** Same but on the Target column.

Existing tests must continue to pass.

## Step 11 — Verify and commit

Run:

```
uv run pytest tests/crmbuilder_v2/ -v
```

Expected: 154 prior tests + new tests from steps 1, 2, 3, 10. Estimated ~180 passing, all green.

Manual verification (recommended):

1. **All eight panels render.** Launch the UI. Click through every sidebar entry. Each renders without errors.
2. **Charter and Status versioned views.** Both panels show all versions newest-first, the current version is marked, the detail pane shows the payload as a structured form. Click an older version; detail updates.
3. **Topics empty state.** Topics shows "0 records" with no rows visible.
4. **Planning Items empty state.** Same.
5. **References panel.** Loads with all 24 references. Source-type filter dropdown shows the unique source types (session, decision, etc.). Set source-type filter to "session"; assert only session-source rows visible. Click a Source cell on a "session:SES-004" row; sidebar switches to Sessions and SES-004 is selected. Click a Target cell on a "decision:DEC-018" row; sidebar switches to Decisions and DEC-018 is selected.
6. **Cross-cutting: lifecycle still routes correctly.** Kill the API mid-session; banner appears (not modal). Reconnect; all panels re-fetch.

Commit shape: single commit covering all of slice E.

```
v2: ui read-only panels round 2 — charter, status, topics, planning items, references

Implements slice E of the v2-ui series per the implementation plan,
completing PRD AC#4 (all eight sidebar entries route to functional
read-only panels).

- VersionedPanel (base/versioned_panel.py): variant of ListDetailPanel
  for singletons-with-history. List shows version + created_at +
  current marker; detail renders the version's payload as a structured
  key/value form. Auto-selects the current version on first load.

- CharterPanel and StatusPanel: identical use of VersionedPanel,
  fetching from /charter/versions and /status/versions respectively.

- TopicsPanel: hierarchical display with parent topics preceding
  children and indented Name column based on depth. Orphans tolerated.
  Cycle-safe.

- PlanningItemsPanel: PRD §4.6 columns (identifier, title, item_type,
  status). Structured detail pane.

- ReferencesPanel: list-only (no detail pane), with filter dropdowns
  for source type and target type above the table, and clickable
  Source/Target cells that navigate to the referenced record.
  ListDetailPanel base extended with _has_detail_pane class flag and
  a filter-strip hook to support this.

- StorageClient extended with list_charter_versions /
  get_charter_version, list_status_versions / get_status_version,
  list_topics / get_topic, list_planning_items / get_planning_item,
  list_references.

- MainWindow registers all five new panels; ENTITY_TYPE_TO_SIDEBAR_LABEL
  map already covered all entity types from slice D.

PRD AC#4 (all eight panels) and AC#5 (versioned current marker)
addressed.
```

Push:

```
git push origin main
```

## Acceptance gates

This slice is complete when all of the following are true:

1. All eight sidebar entries navigate to functional panels rendering live data with PRD §4.6 columns. (PRD AC#4 complete.)
2. Charter and Status panels show all versions newest-first with the current version visually marked (e.g., `✓` in the Current column). The detail pane renders the selected version's payload as a structured form. (PRD AC#5.)
3. Topics panel renders correctly with zero records (empty state) and would render hierarchically when records exist (covered by the unit test for hierarchy build).
4. Planning Items panel renders correctly with zero records.
5. References panel renders all 24 references with three columns (Source, Relationship, Target). Filter dropdowns work. Source/Target cell clicks navigate to the referenced record.
6. The full v2 test suite passes, including all new tests from steps 1, 2, 3, and 10.
7. One commit on `origin/main` with the message shape above.

## Out of slice

The following are explicitly NOT in scope for slice E:

- Reference rendering on Sessions, Risks, Charter, Status, Topics, or Planning Items detail panes — defers to a future slice or v0.2.
- File-watch refresh service — slice F.
- Sidebar staleness indicator — slice F.
- Decision create/edit/delete dialogs — slice G.
- About dialog content, friction polish — slice H.
- True tree-control display for Topics — slice E uses indentation in the Name column, not a `QTreeView`. Tree control is a v0.2 conversation.
- Charter/Status replace flows (versioned write) — explicitly v0.2 per PRD section 2.

Resist the urge to build references display on the new panels. The pattern (`fetch_detail_extras` + reference rendering in `render_detail`) is established and would generalize cleanly, but slice E's scope is the panels themselves; references on these is its own slice.

## Constraints

- **No new external dependencies.**
- **Do not modify the API or access-layer code.** If a needed field is missing from an API response, raise it as an open question — do not modify the API.
- **Do not modify schema, migrations, or vocab.**
- **Do not modify the `lifecycle` module.** Slice D's fix is final for v0.1.
- **Keep slice C's QThread-subclass Worker pattern.**
- **Stop and ask if uncertain.** If the PRD or plan leaves a substantive question unresolved, surface it.

## Reporting

After execution, produce a completion report covering:

- **Acceptance gates** — pass/fail for each of the seven gates above.
- **Files created or modified** — full list, organized by step.
- **Test results** — output summary from `uv run pytest tests/crmbuilder_v2/ -v`.
- **Manual verification** — at minimum scenarios 1, 2, and 5 above. Scenarios 3, 4, 6 are recommended.
- **Deviations from this prompt** — anything that diverged, with reason.
- **Open questions or surprises** — anything that came up that should be flagged for slice F (refresh), slice G (decisions write), or slice H (polish).
- **What slice F will need** — the file-watch refresh path is straightforward integration with the existing `refresh()` method on every `ListDetailPanel`. Note any panel-specific concerns that affect F's implementation.
