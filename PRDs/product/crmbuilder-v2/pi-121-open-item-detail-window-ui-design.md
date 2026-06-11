# PI-121 — Per-row "Open <item type>" action + standalone non-modal detail-window manager — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-121 — *Per-row "Open <item type>" action: open a related record's full view in a separate non-modal window*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-078 (area: ui) / Workstream WSK-060 (Design)
**Builds on:** PI-116…PI-120 — the generalized link/relation grid in `references_section.py` (filter + multi-column sort/grouping + inline preview + drag-resize + the `GridContract` seam that drives References *and* Work Tasks from one widget). All shipped.

## 1. Overview

### Purpose

On the v2 desktop related-record grids — the generalized `ReferencesSection`
grid that renders **References** (PI-116…119) **and** child **Work Tasks**
(PI-120 `WorkTaskGridSection`), plus the child Work Tasks / Planning Items /
other-relation grids that ride the same widget — add a per-row **"Open
&lt;item type&gt;"** action that opens the related record's *full detail view*
in a **separate, non-modal, persistent window**, leaving the originating view
exactly where it was. This is the PI-121 readability item in the PRJ-016
candidate set: when you are reading record A and its grid lists a related
record B, you can pull B up *beside* A — compare two records side by side, or
fan several out — instead of navigating away from A and losing your place.

### The behavior fact that makes this a real PI

The grid already has a way to reach a related record: the per-row **"Go to
{identifier}"** action (and double-click) emits
`navigate_requested(entity_type, identifier)`
(`references_section.py:176–180`, `:192–196`, `:850–853`), which
`MainWindow._on_navigate_requested` (`main_window.py:511–531`) handles by
**switching the sidebar selection** to the target entity's panel and calling
`select_record_by_identifier`. That is *replace-in-place* navigation: the main
window swaps to a different panel, and the record you were reading is no longer
on screen. There is **no** affordance today that opens a second view *without*
abandoning the first. PI-121 adds exactly that, **alongside** "Go to," not in
place of it (the WTK is explicit: additive).

### The reuse fact that shapes the whole design

Every entity panel is a `ListDetailPanel` subclass that already knows how to
render one record's full detail: `render_detail(record, extras)` driven by an
off-thread `fetch_detail_extras(record)`, with `select_record_by_identifier`
to load and select a record by id (`list_detail_panel.py:241–243`, `:231–239`,
`:314–329`). The panels are constructed by a single label→class chain in
`MainWindow._build_*` (`main_window.py:204–265`), each taking only
`self._client`. So "the full view of a `work_task`" is already a thing the
system can build — it is a `WorkTasksPanel(client)` selected to that row. The
decisive design consequence (§3.3): **the standalone window reuses an existing
`ListDetailPanel` rather than introducing per-type detail windows.** One generic
window host + one panel factory covers all ~26 entity types; adding a 27th entity
type needs zero new window code.

### What this design changes (the delta)

1. **A second grid signal, `open_requested(entity_type, identifier)`**, emitted
   by a new per-row **"Open &lt;Pretty Type&gt;"** action placed *next to* the
   existing "Go to" action in the contract row menus — `navigate_requested` is
   untouched (§3.1, §3.2).
2. **Signal propagation** mirroring the existing `navigate_requested` path: the
   grid bubbles `open_requested` up through its host `ListDetailPanel` to the
   `MainWindow`, where the window manager lives (§3.4).
3. **A `DetailWindowManager` + `StandaloneDetailWindow`** (new module): a
   lightweight QMainWindow-based host that spawns one non-modal, independently
   positioned, GC-safe detail window per invocation, reusing a `ListDetailPanel`
   built from a shared panel factory (§3.3, §3.5).
4. **A panel factory extracted** from the inline `_build_*` chain so the manager
   and the main window construct panels through one path — no duplicated
   label→class table (§3.6).
5. **Strictly additive** — "Go to"/double-click/`navigate_requested` behave
   byte-for-byte as today, so the existing tests (including `test_context_menus`)
   do not regress (§3.7, §5, §6).

Deliverable is **the spec/design only, not code.**

## 2. Constraints (hard)

- **C1 — additive, never a replacement.** The existing per-row "Go to
  {identifier}" action, the double-click handler, and the
  `navigate_requested(entity_type, identifier)` signal/router are unchanged. The
  "Open" action is a *new* menu entry and a *new* signal sitting beside them.
- **C2 — label derived from the row's item type.** The action reads "Open Work
  Task" on a `work_task` row, "Open Planning Item" on a `planning_item` row, etc.
  — derived from the row's `other_type`, never hardcoded per contract.
- **C3 — non-modal, persistent, independently positioned, no concurrency limit.**
  Each invocation spawns a separate top-level window shown with `show()` (not
  `exec()`); the originating view stays open and interactive; multiple detail
  windows coexist; windows are positioned so they do not stack exactly on top of
  each other; there is no artificial cap on how many can be open.
- **C4 — reuse existing detail rendering; no per-type windows.** The window
  content is an existing `ListDetailPanel` (its `render_detail`/`fetch_detail_extras`
  path) selected to the target record — one generic window host, not one window
  class per entity type.
- **C5 — one grid implementation, both contracts.** The action is added to the
  `GridContract` row-menu path (References *and* Work Task contracts) in the
  single `references_section.py` grid — no fork, consistent with PI-120's C1.
- **C6 — `test_context_menus` and the grid row-menu tests stay green.** The
  master-pane panel context menus (`_build_context_menu`, asserted in
  `test_context_menus.py`) are **not** touched — the "Open" action lives only on
  the *grid* row menu. The grid row-menu tests that assert exact label sets
  (`test_references_section.py:652–656`) are updated to include the new "Open"
  entry as an expected, scoped change, not a regression.
- **C7 — graceful on unknown/unopenable types.** If a row's `other_type` has no
  panel (catalog/version singletons, unmapped types), opening logs and no-ops —
  exactly as `_on_navigate_requested` already warns on an unknown `entity_type`
  (`main_window.py:514–520`). A row never crashes the app.
- **C8 — GC-safe windows.** Spawned windows must not be garbage-collected while
  visible (the v2 transient-modal GC hazard — see the memory note on
  `deleteLater()` for worker-thread crashes), and must not leak after close. The
  manager holds a strong reference for each window's lifetime and drops it on
  close.

## 3. Design decisions

### 3.1 The "Open" action lives in the contract row menus, beside "Go to" (settled)

The grid's per-row right-click menu is built by the active `GridContract`'s
`row_menu` factory (`references_section.py:245–247`, `:873–883`). Two factories
exist today:

| Factory | Menu today | Where "Open" goes |
|---|---|---|
| `_references_row_menu` (`:159–181`) | Delete reference *(writable)* + "Go to {id}" | append "Open &lt;Pretty Type&gt;" after "Go to" |
| `_work_task_row_menu` (`:184–201`) | "Go to {id}" + "Copy identifier" | append "Open &lt;Pretty Type&gt;" after "Go to" |

**Decision: add a single shared helper `_append_open_action(menu, section, row)`
and call it from both factories, right after the "Go to" entry.** Because both
contracts route through the same helper, the action is identical everywhere the
grid is used (References, Work Tasks, and any future relation grid that supplies
a contract), and the label is derived uniformly from `row["other_type"]`.

**Label derivation (C2).** The helper reads the row's far-side type and renders
the label with the existing `_pretty_entity_type` (`references_section.py:282–283`,
`"work_task" → "Work Task"`): `f"Open {_pretty_entity_type(row['other_type'])}"`.
No per-contract label literal; a `planning_item` row reads "Open Planning Item"
for free.

**Visibility.** The "Open" entry appears on any row that already has a "Go to"
entry — i.e. any row with a non-empty `other_type` + `other_id`. The grid does
**not** consult the entity_type→panel map (it has no business knowing it); a
type with no openable panel is handled gracefully downstream (§3.5, C7), mirroring
how "Go to" already emits `navigate_requested` for any type and lets the router
decide.

### 3.2 A distinct signal, `open_requested`, not an overload of `navigate_requested`

The grid already declares `navigate_requested = Signal(str, str)`
(`references_section.py:373`). "Open" has *different* semantics — spawn a new
window vs. switch the current one — so it gets its own signal:

```text
open_requested = Signal(str, str)   # (entity_type, identifier)
```

The "Open" action's `triggered` connects to
`section.open_requested.emit(row["other_type"], row["other_id"])`, exactly
paralleling the "Go to" action's `navigate_requested.emit(...)`
(`references_section.py:176–180`). Keeping them as two signals means the
double-click path (`_on_double_clicked`, `:850–853`) stays bound to
`navigate_requested` only — double-click remains "Go to," and "Open" is an
explicit, deliberate menu choice. (A double-click that *opened* a window would
surprise users accustomed to double-click = navigate; out of scope, noted in §3.8.)

### 3.3 Reuse an existing `ListDetailPanel` as the window content — no per-type windows (settled)

**Decision: a `StandaloneDetailWindow` is a `QMainWindow` whose central widget is
a freshly-built `ListDetailPanel` of the target entity's type, pre-selected to the
target record.** The panel does all the rendering — its own `fetch_records`,
`fetch_detail_extras`, and `render_detail` — so the standalone window shows the
*identical* full detail the user would see in the main window, including the
record's own link grids, with zero per-type window code (C4).

Mechanically: given `(entity_type, identifier)`, the manager (a) maps
`entity_type → sidebar label` via the existing `ENTITY_TYPE_TO_SIDEBAR_LABEL`
(`main_window.py:96–136`), (b) builds the matching `ListDetailPanel` via the
shared factory (§3.6), (c) sets it as the window's central widget, and (d) calls
`panel.select_record_by_identifier(identifier)` (`list_detail_panel.py:314–329`),
which loads the records off-thread and selects the row, triggering the panel's
own detail load. The window title is `f"{Pretty Type} {identifier}"` (e.g.
"Work Task WTK-001").

**Why a full panel rather than just calling `render_detail` standalone.**
`render_detail(record, extras)` needs *both* a fetched `record` dict and the
`extras` produced by `fetch_detail_extras` on a worker thread — there is no
public "give me the rendered detail for identifier X" entry point; the
master/detail panel *is* that orchestration (worker tracking, stale-token
guarding, connection-loss promotion, the loading placeholder). Rebuilding that
per-type would duplicate `ListDetailPanel` for no gain. Reusing the panel whole
is the smallest correct reuse. The cost — the standalone window also shows the
master list, not only the detail pane — is acceptable (the window is a fully
functional, self-contained view of that entity type, scrolled to the record) and
is called out as a deliberate trade in §3.8, with a "detail-only host" recorded
as a possible follow-on.

**Explicitly rejected:** a per-entity-type window class (`WorkTaskDetailWindow`,
`PlanningItemDetailWindow`, …). That is ~26 near-identical classes, diverges as
panels evolve, and violates C4. One generic host + the existing factory is the
whole point.

### 3.4 Signal propagation — mirror the `navigate_requested` path exactly (settled)

The grid is embedded inside panels' detail rendering; the window manager lives at
`MainWindow` (it needs the client + the panel factory). So `open_requested` must
bubble grid → host panel → main window, exactly as `navigate_requested` does
today. The existing path:

```text
grid.navigate_requested  --(connected at each of 26 panel call sites)-->
  ListDetailPanel.navigate_requested  --(connected in _build_*)-->
    MainWindow._on_navigate_requested
```

**Decision: add `open_requested = Signal(str, str)` to `ListDetailPanel`
(`list_detail_panel.py`, beside `navigate_requested` at `:174`), and connect each
grid's `open_requested` to its host panel's `open_requested` at the same 26 call
sites that already connect `navigate_requested`** (the sites enumerated by
`grep -rn "navigate_requested.connect" src/crmbuilder_v2/ui/panels`:
charter, status, decisions, sessions, risks, planning_items, topics,
conversations, reference_books, work_tickets, deposit_events, commits, projects,
work_tasks, workstreams ×2, persona, processes, requirements, test_spec, field,
entities, domains, crm_candidates, manual_config, close_out_payloads). The
`MainWindow` then connects every `ListDetailPanel.open_requested` to a new
`_on_open_requested` slot in the same loop that already wires
`navigate_requested` (`main_window.py:275–277`).

**Reducing the 26-site cost — recommended.** Rather than add a bare second
`.connect(...)` line at each site, introduce a one-line helper on
`ListDetailPanel`, `_wire_link_section(section)`, that connects *both*
`navigate_requested` and `open_requested` (and is the natural home for any future
grid signal). Each call site's existing
`section.navigate_requested.connect(self.navigate_requested)` becomes
`self._wire_link_section(section)` — same edit count, but DRY and future-proof.
The build session may take either form; the helper is the suggested default.

`_on_open_requested(entity_type, identifier)` delegates to
`self._detail_window_manager.open(entity_type, identifier)` (§3.5).

### 3.5 The `DetailWindowManager` (new `ui/detail_window_manager.py`)

A small, testable, Qt-aware coordinator owned by `MainWindow`.

```text
class StandaloneDetailWindow(QMainWindow):
    # central widget is a ListDetailPanel built by the factory, pre-selected.
    closed = Signal(object)            # emits self on close so the manager drops its ref
    # Qt.WA_DeleteOnClose set; closeEvent emits `closed` then super()

class DetailWindowManager(QObject):
    def __init__(self, client, panel_factory, navigate_router, parent_window): ...
    def open(self, entity_type, identifier) -> StandaloneDetailWindow | None:
        # 1. label = ENTITY_TYPE_TO_SIDEBAR_LABEL.get(entity_type); if None -> log + return None (C7)
        # 2. panel = panel_factory(label); if not a ListDetailPanel -> log + return None (C7)
        # 3. window = StandaloneDetailWindow(panel, title=f"{pretty} {identifier}")
        # 4. wire panel.connection_lost / .navigate_requested / .open_requested (see below)
        # 5. position the window (cascade offset off the parent), show() non-modally
        # 6. self._windows.append(window); window.closed -> self._windows.remove(...)
        # 7. panel.select_record_by_identifier(identifier); return window
```

- **Non-modal + persistent (C3):** `window.show()`, never `exec()`. The manager
  keeps a strong ref in `self._windows` for the window's whole lifetime (C8); the
  `closed` signal removes it so a closed window is collected and does not leak. No
  cap on `len(self._windows)`.
- **Independent positioning (C3):** each new window is offset from the parent (or
  from the most-recently-opened window) by a fixed cascade delta (e.g. +32,+32 px)
  and given a sensible default size, so windows do not land exactly on top of each
  other. Cosmetic and tunable.
- **GC safety (C8):** `Qt.WA_DeleteOnClose` + the manager's ref list + the spawned
  panel's own `closeEvent` (which already waits on in-flight workers,
  `list_detail_panel.py:345–352`) means worker threads are drained before the
  panel is destroyed — the same discipline the memory note on transient sub-dialog
  GC requires.
- **Re-use vs. focus (optional refinement):** opening the *same* `(entity_type,
  identifier)` twice may either spawn a second window (literal "no concurrency
  limit") or raise/focus the existing one. The WTK says "no artificial concurrency
  limit," so the **default is spawn-every-time**; an optional "raise if already
  open for this id" refinement is noted as out-of-scope polish (§3.8).

**Routing the spawned panel's own signals.** The standalone panel is a real
`ListDetailPanel`; it can itself emit `connection_lost`, `navigate_requested`, and
`open_requested`:

- `connection_lost` → the manager forwards to the parent window's existing
  connection-loss handler (`MainWindow._on_panel_connection_lost`) so a dead API
  is handled uniformly whether the failing panel is in the main window or a
  standalone one.
- `open_requested` → back to `manager.open(...)` (opening a related record from a
  standalone window spawns *another* standalone window — the windows are
  self-similar).
- `navigate_requested` ("Go to") → routed to the **main window's**
  `_on_navigate_requested` (passed in as `navigate_router`), preserving the global
  meaning of "Go to" = *navigate in the main window* from every surface. (A
  standalone window's "Go to" therefore brings the main window to that record; its
  "Open" spawns a sibling window. This keeps the two verbs' meanings stable
  everywhere.)

### 3.6 Extract a shared panel factory (settled)

`MainWindow._build_*` constructs panels with an inline `if entry == "...":
page = XPanel(self._client)` chain (`main_window.py:204–265`). The manager needs
the *same* construction. **Decision: extract a module-level (or static)
`build_panel(label, client) -> QWidget` that contains the label→class mapping;
`_build_*` calls it, and `DetailWindowManager` calls it.** One table, two callers
— no duplication, and a new entity type's panel is registered once.

The factory returns the same `QWidget` the chain returns today (a `ListDetailPanel`
for entity panels, or the `ChatPanel`/placeholder for non-entity entries). The
manager guards on `isinstance(page, ListDetailPanel)` (C7) — Chat / placeholders
are not openable as detail windows and fall to the graceful no-op.

> **Scope note.** Extracting the factory is a small, mechanical refactor of the
> existing chain with no behavior change for the main window (it builds the same
> panels). It is justified by DRY (two callers of one mapping); if the build
> session judges the extraction too broad for this WTK, the fallback is a *private*
> `entity_type → panel class` dict inside the manager seeded from the same classes
> — functionally equivalent, at the cost of a second list to keep in sync. The
> extraction is the recommended form.

### 3.7 Why this is strictly additive (C1) and the existing tests hold (C6)

- `navigate_requested`, the "Go to" action, and `_on_double_clicked` are
  **unchanged** — "Open" is a new signal and a new menu entry appended after them.
- `MainWindow._on_navigate_requested` is unchanged; `_on_open_requested` is a new
  slot.
- The **master-pane** panel context menus (`_build_context_menu`) — the surface
  `test_context_menus.py` asserts (e.g. `:270`
  `["Go to source", "Go to target", "Delete reference"]`) — are **not touched**.
  The "Open" action is on the *grid* row menu only, so that whole suite is
  unaffected (C6).
- The **grid row-menu** tests that pin exact label lists do change in a scoped,
  expected way: `test_work_task_grid_section_row_menu_is_read_only`
  (`test_references_section.py:652–656`) currently asserts
  `["Go to WTK-001", "Copy identifier"]`; with the new entry it asserts
  `["Go to WTK-001", "Open Work Task", "Copy identifier"]`. The build session
  updates this (and the equivalent References row-menu assertion, if any) and adds
  positive tests for the new path (§5). This is the redesigned surface's own test
  moving with it — distinct from C6's "do not regress the *unrelated* menus."

### 3.8 Follow-ons (documented, not built)

- **Detail-only window host.** §3.3 reuses the whole `ListDetailPanel` (master
  list + detail). A future refinement could host *only* the detail pane (a
  thinner window) by giving `ListDetailPanel` a "detail-only" mode or a small
  detail-render orchestrator. Recorded as the natural end-state; out of scope here
  because it would touch `ListDetailPanel`'s structure for all 26 panels.
- **Raise-if-already-open.** De-duplicating windows per `(entity_type, identifier)`
  (focus the existing window instead of spawning a sibling) is a usability polish;
  the WTK's "no artificial concurrency limit" makes spawn-every-time the correct
  default, so de-dup is explicitly deferred.
- **Double-click = Open modifier.** A Ctrl/Shift-double-click that opens a window
  (vs. plain double-click = navigate) is a possible accelerator; out of scope to
  keep double-click semantics stable.
- **Window-state persistence.** Remembering size/position of detail windows across
  sessions is not in scope.

## 4. Files touched

| File | Change | Why |
|---|---|---|
| `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` | Add `open_requested = Signal(str, str)`; add shared `_append_open_action(menu, section, row)` helper that derives the label via `_pretty_entity_type(row["other_type"])` and connects to `open_requested.emit(...)`; call it from `_references_row_menu` and `_work_task_row_menu` right after the "Go to" entry. (§3.1, §3.2) | The new per-row action + signal, one grid, both contracts (C5), label per row type (C2), additive to "Go to" (C1). |
| `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` | Add `open_requested = Signal(str, str)` beside `navigate_requested`; add `_wire_link_section(section)` helper that connects both `navigate_requested` and `open_requested`. (§3.4) | The bubble-up seam mirroring the existing navigate path; DRY wiring for the 26 sites. |
| `crmbuilder-v2/src/crmbuilder_v2/ui/panels/*.py` (the 26 grid call sites) | Connect each grid's `open_requested` to the host panel's `open_requested` — via `_wire_link_section(section)` replacing the existing single `navigate_requested.connect` line. (§3.4) | Propagate the new signal at exactly the sites that already propagate navigate. |
| `crmbuilder-v2/src/crmbuilder_v2/ui/detail_window_manager.py` *(new)* | `StandaloneDetailWindow(QMainWindow)` + `DetailWindowManager(QObject)`: spawn/track/position non-modal detail windows hosting a factory-built `ListDetailPanel`, pre-selected; route the spawned panel's `connection_lost`/`navigate`/`open` signals. (§3.5) | The window manager (C3, C4, C7, C8). |
| `crmbuilder-v2/src/crmbuilder_v2/ui/main_window.py` | Extract `build_panel(label, client)` from the `_build_*` chain; instantiate `DetailWindowManager`; in the panel-wiring loop connect each `ListDetailPanel.open_requested → _on_open_requested`; add `_on_open_requested` delegating to the manager. (§3.4, §3.6) | One panel factory (DRY), the manager owner, the open router. |
| `tests/crmbuilder_v2/ui/widgets/test_references_section.py` | Update the Work Task (and References) row-menu label assertions to include "Open …"; add a test that the action label is derived per row type and that triggering it emits `open_requested(other_type, other_id)`. (§3.7, §5) | Prove C1/C2/C5 at the grid. |
| `tests/crmbuilder_v2/ui/test_detail_window_manager.py` *(new)* | Manager spawns a non-modal window per call hosting the right panel pre-selected; multiple windows coexist; closing drops the ref; unknown/unopenable type no-ops; spawned panel's navigate routes to the main router, open spawns a sibling. (§5) | Prove C3/C4/C7/C8. |

No change to `multi_sort_header.py`, `multi_sort_proxy.py`, `grouping_tree_model.py`,
`linked_record_preview.py`, `link_filter_input.py`, or the access layer. The
double-click path, the master-pane `_build_context_menu` menus, and
`navigate_requested`/`_on_navigate_requested` are untouched.

## 5. Verification approach

Offscreen Qt (`QT_QPA_PLATFORM=offscreen`), the established pattern for these
widget/panel/window tests. The build session asserts:

1. **Action appears, correctly labeled per row type (C2).** Build a
   `ReferencesSection`/`WorkTaskGridSection` over a fixture; `_build_row_menu` on a
   `work_task` row contains "Open Work Task"; on a `planning_item` row contains
   "Open Planning Item"; the entry sits **after** "Go to {id}" and "Go to" is
   still present (C1).
2. **Open emits the new signal.** Triggering the "Open" action emits
   `open_requested("work_task", "WTK-001")`; `navigate_requested` is **not**
   emitted by it. Double-click still emits `navigate_requested` only.
3. **Spawns an independent non-modal window with the full record view (C3, C4).**
   With a stub client + stub panel factory, `DetailWindowManager.open("work_task",
   "WTK-001")` returns a visible `StandaloneDetailWindow` whose central widget is a
   `ListDetailPanel` of the Work Tasks type, on which `select_record_by_identifier`
   was called with `"WTK-001"`; the window is non-modal (`isModal()` False); the
   originating window is unaffected.
4. **Multiple windows coexist (C3).** Two `open(...)` calls yield two distinct
   live windows tracked by the manager, at offset positions; neither closes the
   other.
5. **Close drops the ref (C8).** Closing a window emits `closed`, the manager
   removes it from `self._windows`, and `WA_DeleteOnClose` schedules deletion; no
   leak.
6. **Graceful on unknown/unopenable type (C7).** `open("nonsense", "X-1")` and
   `open` for a non-`ListDetailPanel` entry (e.g. Chat) return `None`, log a
   warning, and spawn nothing.
7. **"Go to" / `navigate_requested` not regressed (C1).** The existing
   `test_double_click_emits_navigate_requested` and the navigate-router behavior
   pass unchanged.
8. **Context menus not regressed (C6).** `tests/crmbuilder_v2/ui/test_context_menus.py`
   passes unchanged; the grid row-menu suite passes with the updated (expected)
   label assertions.

**Commands the build session runs:**

```bash
cd crmbuilder-v2
QT_QPA_PLATFORM=offscreen uv run pytest \
  ../tests/crmbuilder_v2/ui/widgets/test_references_section.py \
  ../tests/crmbuilder_v2/ui/test_detail_window_manager.py \
  ../tests/crmbuilder_v2/ui/test_context_menus.py \
  ../tests/crmbuilder_v2/ui/test_workstreams_panel.py -q
uv run ruff check \
  src/crmbuilder_v2/ui/widgets/references_section.py \
  src/crmbuilder_v2/ui/base/list_detail_panel.py \
  src/crmbuilder_v2/ui/detail_window_manager.py \
  src/crmbuilder_v2/ui/main_window.py \
  src/crmbuilder_v2/ui/panels/
```

## 6. Acceptance criteria

- **AC1** — Each related-record grid row carries an **"Open &lt;item type&gt;"**
  action whose label is derived from the row's type ("Open Work Task", "Open
  Planning Item", …), placed **alongside** the existing "Go to {identifier}"
  action, which is unchanged (C1, C2).
- **AC2** — Triggering "Open" spawns a **separate, non-modal** window showing the
  related record's **full detail view**, reusing an existing `ListDetailPanel`
  pre-selected to that record — no per-type window class (C3, C4).
- **AC3** — Windows are independently positioned, the originating view stays open
  and interactive, and **multiple detail windows coexist** with no artificial
  concurrency limit (C3).
- **AC4** — Opening is driven by a **new** `open_requested(entity_type,
  identifier)` signal bubbling grid → panel → main window; `navigate_requested`
  and "Go to"/double-click in-main-window navigation are byte-for-byte unchanged
  (C1).
- **AC5** — Unknown or unopenable `other_type` values log and no-op; no crash (C7).
- **AC6** — Windows are GC-safe: held while visible, collected on close, with
  in-flight workers drained before destruction (C8).
- **AC7** — `test_context_menus` and the unrelated grid/navigate tests pass
  unchanged; the grid row-menu label assertions are updated as a scoped,
  expected change for the redesigned menu (C6).
- **AC8** — The detail-only window host, raise-if-already-open de-dup, a
  double-click-open accelerator, and window-state persistence are recorded as
  deliberate out-of-scope follow-ons (§3.8), not silent omissions.

## 7. Decisions log (for governance capture at build close)

- **D1** — Per-row **"Open &lt;Pretty Type&gt;"** action added to the contract
  row menus (References + Work Task) via a shared `_append_open_action` helper,
  **beside** "Go to," label derived from `row["other_type"]` (§3.1, C1, C2, C5).
- **D2** — A **distinct** `open_requested(str, str)` signal — not an overload of
  `navigate_requested`; double-click stays bound to navigate only (§3.2).
- **D3** — The standalone window **reuses an existing `ListDetailPanel`**
  pre-selected to the record; **reject** per-entity-type detail window classes
  (§3.3, C4).
- **D4** — Signal propagation **mirrors the `navigate_requested` path**: add
  `open_requested` to `ListDetailPanel`, wire it at the same 26 grid call sites
  (preferably via a `_wire_link_section` helper), route it to `MainWindow`
  (§3.4, C1).
- **D5** — A new `DetailWindowManager` + `StandaloneDetailWindow`: spawn/track/
  position non-modal windows, no concurrency cap, GC-safe via a ref list +
  `WA_DeleteOnClose` + `closed` signal (§3.5, C3, C8).
- **D6** — Route the spawned panel's own signals: `connection_lost` →
  parent-window handler; `open_requested` → manager (sibling window);
  `navigate_requested` → the **main window** router (keeps "Go to" = navigate in
  the main window everywhere) (§3.5).
- **D7** — Extract a shared `build_panel(label, client)` factory used by both
  `MainWindow._build_*` and the manager — one label→class table (§3.6); private
  dict in the manager is the documented fallback.
- **D8** — Out of scope, recorded: detail-only window host, raise-if-already-open
  de-dup, double-click-open accelerator, window-state persistence (§3.8).
