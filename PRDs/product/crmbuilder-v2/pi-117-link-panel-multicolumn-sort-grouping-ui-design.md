# PI-117 — Link Panel Multi-Column Sort, Grouping, and Standalone-Panel Sort — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-117 — *Link panel sortable/groupable columns with multi-column sort*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-067 (area: ui)
**Builds on:** PI-116 (`pi-116-link-panel-search-filter-ui-design.md`) — debounced filter + single-column click-header sort, already shipped

## 1. Overview

### Purpose

Specify the UI for **multi-column sort**, **grouping**, and **standalone-panel sort**
on the relationship (link) panels, so a user can impose order on a large link set:
sort by a primary key *and* one or more secondary keys (e.g. *type then date*), and
collapse rows under a shared key. This is the **PI-117 remaining delta only** — the
parts PI-116 did **not** ship.

### Background — what PI-116 already shipped (do not re-spec)

PI-116's autonomous build delivered the foundation this PI assumed it would lay. On
the **embedded** references grid `ReferencesSection`
(`crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`):

- A `_RefsModel(QAbstractTableModel)` over flattened inbound + outbound rows, columns
  *Direction, Relationship, Identifier, Type, Title, Status, Created, Updated*
  (`_COLUMNS`), exposing `DisplayRole` strings **and** a `UserRole` sort key per cell
  (`data(...)`: ISO timestamps returned raw so they sort chronologically; text
  lowercased for case-insensitive ordering; missing values returned as `"￿"` so
  they sort last).
- A `QSortFilterProxyModel` with `setSortRole(Qt.ItemDataRole.UserRole)`,
  `setSortingEnabled(True)`, default `sortByColumn(0, AscendingOrder)`, and the
  PI-116 debounced filter (`LinkFilterInput` → `filterChanged` →
  `setFilterFixedString`, all-column `setFilterKeyColumn(-1)`).
- **Single-column** header-click sort: clicking a header sorts by that one column and
  toggles ascending/descending — Qt's stock `QHeaderView` behavior.

On the **standalone** browser `ReferencesPanel`
(`crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py`): PI-116 added the
debounced free-text filter beside the source-type / target-type combos. But this
panel is built on `ListDetailPanel`'s plain `_RecordTableModel` installed **directly**
into the master `QTableView` — **no `QSortFilterProxyModel`, no sort role, no
header-click sort at all** (columns *Source, Relationship, Target*). PI-116 left it
**list-only**.

### What this design changes (the delta)

1. **Multi-column sort** on `ReferencesSection`: a primary + one or more secondary
   sort keys with stable ordering and a per-column precedence/direction indicator.
   `QSortFilterProxyModel` is single-key; this needs a custom proxy (§4.1) reading the
   existing PI-116 `UserRole` keys in priority order.
2. **Grouping** on `ReferencesSection`: collapse rows under a shared key (relationship,
   type, status, direction, or *created-by-day*), with collapse/expand interaction,
   composed on top of the multi-column sort (§4.2).
3. **Standalone-panel sort/group** on `ReferencesPanel`: bring the same multi-column
   sort + grouping to the standalone browser, which PI-116 left list-only (§4.3) —
   composed with its existing dropdown + free-text filters.

Both surfaces share the same reusable proxy + header + group model (§4) so the sort
semantics, indicator rendering, and group interaction stay identical. **Scope is the
presentation layer only** — Qt model / proxy / widget. No access-layer, API, or
columns/navigation/add-delete changes.

## 2. Scope

### In scope

1. A reusable multi-column sort proxy (`MultiSortProxyModel`) with a composite
   `lessThan` and a stable tiebreaker, plus its add/clear/precedence API.
2. A reusable header widget (`MultiSortHeaderView`) that paints a per-column rank +
   direction indicator and translates plain-click / modifier-click into sort-key
   mutations.
3. A reusable grouping model (`GroupingTreeModel`) and the QTreeView presentation that
   replaces the flat table while a group key is active, including collapse/expand and
   expand-all / collapse-all.
4. Integrating all three into `ReferencesSection` (already proxy-backed) and into
   `ReferencesPanel` (add proxy + sort role + the group control to a list-only panel).
5. Acceptance criteria and verification (test cases) per behavior.

### Out of scope

- Re-specifying basic single-column click-header sort, the debounced filter, or the
  no-match empty state — all shipped by PI-116 and preserved unchanged.
- Server-side relationship query / sorting / paging. As in PI-116 §6/§3.6, both panels
  hold the full row set in memory; sort and grouping are complete over the loaded set.
  If a future Work Task adds server paging, the §4.4 forward-compatibility note binds.
- Changing the column set, navigation, add/delete actions, or the access-layer
  `other_summary` payload shape.
- Persisting a user's sort/group choice across sessions (a possible later polish; §7).
- Engagement-area or settings UI.

## 3. Behavior specification

### 3.1 Multi-column sort — interaction model

The header is the sole control surface; no extra toolbar is introduced for sort.

- **Plain click on a header** — *single-key sort* (PI-116 behavior, preserved exactly):
  the clicked column **replaces** the entire sort-key list and becomes the sole key,
  ascending. Clicking the same column again toggles ascending → descending. This is the
  default, unchanged path for the common case.
- **Modifier-click on a header** (`Ctrl`-click, falling back to `Shift`-click — both
  accepted) — *add/cycle a secondary key*: the clicked column is **appended** to the
  sort-key list (or, if already present, its direction cycles ascending → descending →
  **removed**), without clearing the other keys. This is how a user builds *type then
  date*: plain-click *Type*, then `Ctrl`-click *Created*.
- **Precedence** is the order keys were added: the first key is primary, the next
  secondary, and so on. A primary plain-click anywhere resets to a single key.
- **Per-column indicator** (§3.2): every active sort column shows its **rank** (1, 2,
  3…) and **direction** (▲/▼) in its header; inactive columns show nothing.
- **Clear sort:** a header context-menu item *"Clear sort"* resets to the default
  (single key on column 0, ascending) — never to "no sort", because a deterministic
  default order is required (§3.3). Modifier-cycling a key past descending also removes
  just that one key.

### 3.2 Sort indicator

Qt's stock `QHeaderView` tracks only one `sortIndicatorSection`, so multi-key
precedence cannot be shown with the default header. `MultiSortHeaderView` (§4.1)
overrides `paintSection` to draw, right-aligned in each active sort column's header
cell, a compact **`▲1` / `▼2`** glyph — the arrow is the direction, the number is the
1-based precedence rank. The primary key reads `▲1`; a secondary descending key reads
`▼2`. Inactive columns render the plain header text with no glyph. The indicator is
recomputed from the proxy's key list on every sort change (the header subscribes to a
`sortKeysChanged` signal the proxy emits), so it always reflects live precedence.

### 3.3 Stable, deterministic ordering

`QSortFilterProxyModel` does **not** guarantee a stable sort, and equal composite keys
must not reorder arbitrarily between invalidations. The composite comparator therefore
ends in a **final tiebreaker on the source-model row index** (the order the access
layer flattened inbound+outbound). Result:

- Rows equal on all active sort keys retain their original relative order (stable).
- Re-applying the same key list is idempotent (no visible churn).
- With the default single key on column 0 the output is byte-identical to PI-116's
  current grid, so the change is a strict superset.

### 3.4 Fields and sort keys

The composite comparator reuses the **existing PI-116 `UserRole` sort keys** — it does
not invent new per-cell data. For each `(column, direction)` pair in the key list, in
order, it compares `model.data(left_in_col, UserRole)` against
`model.data(right_in_col, UserRole)`; the first non-equal column decides, honoring that
column's own direction. This means *Created* still sorts chronologically (raw ISO),
text columns still sort case-insensitively, and missing values still sort last — for
free, on every key, because the keys are already defined. No column gains or loses
sortability.

### 3.5 Grouping — group-by control and key

- A **"Group by:"** control sits in the panel header:
  - `ReferencesSection`: a `QComboBox` placed to the **right of** the PI-116 filter box,
    on the same row, so filter and group read left-to-right.
  - `ReferencesPanel`: a `QComboBox` appended to the existing filter strip after the
    source/target-type combos.
- **Options** (driven by the columns actually present on each surface):
  - `ReferencesSection`: *(none)*, *Relationship*, *Type*, *Status*, *Direction*,
    *Created (by day)*. *(none)* is the default and is identical to today's flat grid.
  - `ReferencesPanel`: *(none)*, *Source type*, *Relationship*, *Target type*.
- **Group key derivation:** the group value is the row's **display** value for that
  field (the same string shown in the cell), except *Created (by day)* which buckets on
  the `YYYY-MM-DD` date prefix of the raw timestamp (reusing `_fmt_dt`'s date part).
  Missing values bucket under a single **"(none)"** group rendered last.

### 3.6 Grouping — presentation and collapse/expand

A flat `QTableView` cannot render group headers, so when a group key is active the
surface switches to a **`QTreeView`** over a `GroupingTreeModel` (§4.2):

- **Two levels:** a top-level **group node** per distinct key value, its child rows the
  matching reference rows. The group node spans the row and shows
  **`<group value>  (<n>)`** — the key and the count — in the semibold/dim treatment
  already used for section labels.
- **Collapse/expand:** native `QTreeView` expand/collapse on the group node
  (click the branch indicator / double-click the group row / keyboard). All groups
  **start expanded**. Two affordances next to the Group-by combo: **Expand all** /
  **Collapse all** (text-link buttons, matching `text_link_button` usage in
  `ReferencesSection`).
- **Switching group key off** (*(none)*) restores the flat `QTableView` exactly as it
  was — same model, same multi-sort proxy, same height-fit. The tree and table are two
  presentations of one underlying row set; only one is visible at a time
  (a `QStackedWidget`, or show/hide, owned by the section).

### 3.7 Grouping composes with multi-column sort

Grouping is layered **outside** the multi-column sort, not instead of it:

1. **Within each group**, child rows are ordered by the full active multi-column sort
   key list (§3.1) — so *type then date* still holds inside a group.
2. **Groups themselves** are ordered by the group key value: ascending by display
   value, except *Created (by day)* which orders chronologically (newest-or-oldest per
   the group key's own direction, default ascending). The **"(none)" group always sorts
   last**, mirroring the missing-value rule.
3. Effectively the group key is the **outermost** sort key, with the user's
   multi-column keys nested beneath it. Changing the multi-sort key list while grouped
   re-sorts within groups live; changing the group key rebuilds the tree.

### 3.8 Interaction with the PI-116 filter

Sort and grouping operate over the **filtered** row set, never the raw set:

- `ReferencesSection`: the `MultiSortProxyModel` sits where the plain
  `QSortFilterProxyModel` sits today, so it still filters (the PI-116 filter path is
  inherited — see §4.1) *and* multi-sorts. When grouping is on, the `GroupingTreeModel`
  is rebuilt from the proxy's **currently visible (filtered + sorted)** rows, so a
  filter that excludes everything yields zero groups and the existing no-match empty
  state (PI-116 §3.4) still shows.
- `ReferencesPanel`: its existing `_apply_filter` (dropdowns + free text) keeps
  producing the filtered record list via `set_records` on the source model; the new
  proxy sorts on top, and the group model (when active) is rebuilt from the filtered +
  sorted rows. The three compose with AND as today, with sort/group purely
  presentational on the survivors.

### 3.9 Height-fit and the empty state

- `ReferencesSection._fit_height()` is extended to size **whichever presentation is
  visible** to its content: the table to its (filtered) proxy row count as today, or
  the tree to its expanded-node count (group nodes + visible child rows) so the detail
  pane's outer scroll still handles overflow with no nested scrollbar. Collapsing a
  group re-runs the fit so the tree shrinks.
- The PI-116 no-match empty state and the "(none)" record-has-no-links case are
  unchanged and take precedence over any sort/group UI (no header controls render when
  there is nothing to sort).

## 4. Component design

Three small reusable presentation classes, plus the wiring into the two surfaces.

### 4.1 `MultiSortProxyModel` — chosen over a UserRole sort-key tuple

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/multi_sort_proxy.py`
- **Class:** `MultiSortProxyModel(QSortFilterProxyModel)`.
- **State:** `_sort_keys: list[tuple[int, Qt.SortOrder]]` — ordered `(column, order)`
  pairs; precedence is list order.
- **API:**
  - `set_primary(column: int) -> None` — replace the list with one key (toggles
    asc/desc if already primary). Backs a plain header click.
  - `cycle_secondary(column: int) -> None` — append the column asc, or cycle
    asc → desc → remove if present. Backs a modifier header click.
  - `clear_sort() -> None` — reset to `[(0, Ascending)]` (the deterministic default).
  - `sort_keys() -> list[tuple[int, Qt.SortOrder]]` — read-only, for the header.
  - **Signal** `sortKeysChanged()` — emitted on every mutation so the header repaints.
- **Comparator:** override `lessThan(left, right)` to walk `_sort_keys` in order; for
  each, fetch the **`UserRole`** value of `left`/`right` *in that key's column* (via
  `sourceModel().index(row, key_col)`), compare, and return on the first inequality
  honoring the key's direction. Equal on all keys → compare source row indices (the
  stable tiebreaker, §3.3). Keep `setSortRole(UserRole)` so single-section fallbacks
  agree.
- **Filtering:** inherits `filterAcceptsRow` from `QSortFilterProxyModel`, so the
  PI-116 `setFilterFixedString` / `setFilterKeyColumn(-1)` / case-insensitive contract
  is preserved with zero new code — the proxy is a drop-in replacement for the stock
  one in `ReferencesSection._build`.

**Decision — custom proxy subclass vs. a sort-key tuple in `UserRole`.** The Work Task
calls for evaluating both. **Chosen: the custom `QSortFilterProxyModel` subclass.**

| | Custom proxy (`lessThan`) — **chosen** | Sort-key tuple in `UserRole` |
|---|---|---|
| Where sort state lives | In the proxy (`_sort_keys`) — a view concern, cleanly separated from data | In the *model's* cell data — couples dynamic view state into the model |
| Changing key order | Mutate `_sort_keys`, `invalidate()` — O(1) state change | Rewrite every cell's tuple, `dataChanged`/reset — O(rows × cols) rebuild per change |
| Reuses PI-116 keys | Yes — reads the existing per-column `UserRole` keys in priority order | No — must *recompose* a composite tuple, duplicating the per-column key logic |
| Stable tiebreaker | Trivial (source row index in `lessThan`) | Must bake row index into the tuple, recomputed on reorder |
| Direction per key | Per-key `SortOrder` honored in the comparator | Hard — a single ascending tuple compare can't mix asc/desc keys without inverting components |
| Grouping reuse | Group model reads the same proxy order | Same tuple must also encode group key — entangled |

The tuple approach's fatal flaw is **per-key direction**: a lexicographic tuple compare
is globally ascending, so *type ascending, date descending* cannot be expressed without
inverting the date component's sort value — fragile for strings/timestamps. The custom
comparator honors each key's direction independently and reuses the keys PI-116 already
defined. The proxy subclass is the smaller, more robust change.

### 4.2 `GroupingTreeModel` — the group-by presentation

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/grouping_tree_model.py`
- **Class:** `GroupingTreeModel(QAbstractItemModel)` — a thin two-level tree built from
  an **already-ordered** list of source row dicts plus a `group_of(row) -> str` key
  function and the same `_COLUMNS` spec, so child rows render identical cells to the
  flat table.
- **Build input:** the host passes the rows **in final sorted order** (read out of the
  `MultiSortProxyModel`); the model partitions them into groups *preserving arrival
  order within a group* (so the multi-sort holds inside groups, §3.7-1) and orders the
  group nodes by key (§3.7-2). Rebuilt (`beginResetModel`/`endResetModel`) whenever the
  group key changes or the filtered/sorted set changes.
- **Rows:** group nodes carry the **`<value> (<n>)`** label in column 0 and span
  visually (the host sets the first column to stretch / uses `setFirstColumnSpanned`);
  child nodes delegate `data()` to the same per-column display strings as `_RefsModel`,
  and expose `row_dict(index)` so navigation / delete map back to the underlying edge
  exactly as the table path does.
- **Why a dedicated model, not grouping inside the proxy:** `QSortFilterProxyModel` is
  flat — it cannot synthesize parent group rows. A `QAbstractItemModel` tree is the
  Qt-idiomatic way to render group headers, and keeping it separate means the *(none)*
  path is untouched (the flat table + proxy stay exactly as PI-116 shipped).

### 4.3 `MultiSortHeaderView` — precedence indicator + click routing

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/multi_sort_header.py`
- **Class:** `MultiSortHeaderView(QHeaderView)` installed on the table via
  `setHorizontalHeader(...)`.
- **Paint:** override `paintSection` to draw the base header, then overlay the
  **`▲1` / `▼2`** rank+direction glyph for any column in the proxy's `sort_keys()`.
- **Click routing:** override `mousePressEvent` (or connect `sectionClicked` plus read
  the keyboard modifiers): plain → `proxy.set_primary(col)`; `Ctrl`/`Shift` →
  `proxy.cycle_secondary(col)`. Subscribe to `proxy.sortKeysChanged` →
  `headerDataChanged`/`viewport().update()` to repaint.
- Reused by **both** surfaces so the indicator and modifier semantics are identical.

### 4.4 Wiring — `ReferencesSection` and `ReferencesPanel`

- **`ReferencesSection`** (`references_section.py`):
  - Swap the stock `QSortFilterProxyModel` (line ~287) for `MultiSortProxyModel`
    (same filter wiring, same `setSortRole(UserRole)`, same default
    `sortByColumn(0, Ascending)` → expressed as `clear_sort()`).
  - Install `MultiSortHeaderView` on `self._table`.
  - Add the **Group-by** combo + **Expand/Collapse all** links to the filter row, and a
    `QStackedWidget` (or sibling) holding the flat `QTableView` and the grouped
    `QTreeView`; show the tree only when a group key is selected, feeding it the proxy's
    current ordered rows. Extend `_fit_height` to size the visible presentation
    (§3.9). Navigation, delete, and the context menu route through `row_dict` on
    whichever model is live, so `_on_double_clicked` / `_on_context_menu` are unchanged
    in intent.
- **`ReferencesPanel`** (`panels/references.py`):
  - It installs `_RecordTableModel` directly today. Insert a `MultiSortProxyModel`
    between that model and the master view (the panel pre-installs `model = proxy` so
    the base's "model is `None`" branch is skipped), and set the proxy's sort role.
    Because `_RecordTableModel` exposes only `DisplayRole`, set
    `setSortCaseSensitivity(Qt.CaseInsensitive)` on the proxy so the *Source /
    Relationship / Target* string columns sort case-insensitively, with missing values
    via the model's empty-string (sorts first/last consistently); a follow-on may add a
    `UserRole` to the base model for richer keys, but it is not required for these three
    text columns.
  - Install `MultiSortHeaderView` on the master view to gain header-click single- **and**
    multi-column sort (the panel has none today).
  - Append the **Group by** combo (Source type / Relationship / Target type) to the
    existing filter strip; when active, render the grouped `QTreeView` in place of the
    table, fed from the proxy's filtered+sorted rows, composing with the existing
    dropdown/free-text filters (§3.8). `_on_cell_clicked` / context menu route through
    `record_at` / `row_dict` so single-click navigation is preserved.

**Forward-compatibility (binding, mirrors PI-116 §3.6):** sort and grouping are
client-side over the **loaded** rows. If a future Work Task adds server paging, a key
list / group key would silently order only the loaded page and read as a complete
ordering — a correctness trap. A paging implementation must either keep loading the
full set for these panels, or escalate sort/group to a server query with a "ordering
loaded N of M" affordance. Until paging lands, neither is needed; this note fixes the
boundary.

### 4.5 Styling

Indicator glyphs, group-node label, and the Group-by combo inherit existing tokens
(`t("font.weight.semibold")`, `t("color.neutral.500/800")`, the global combo/input
styles). No new design tokens. The Expand/Collapse links reuse `text_link_button`.

## 5. Acceptance criteria

1. **Single-column sort preserved.** A plain header click sorts by that one column
   ascending; a second click toggles descending — identical to PI-116. The default
   render is sorted by column 0 ascending and is byte-identical to the pre-PI-117 grid.
2. **Multi-column sort.** Plain-clicking *Type* then `Ctrl`-clicking *Created* orders
   rows by Type ascending, ties broken by Created — *type then date* — and the order is
   **stable** (rows equal on both keys keep their original relative order).
3. **Per-column indicator.** Every active sort column shows its rank + direction
   (`▲1`, `▼2`, …) in the header; inactive columns show no glyph; the indicator updates
   live as keys are added, cycled, or cleared.
4. **Add / clear precedence.** Modifier-cycling a secondary key goes
   ascending → descending → removed; a plain click on any column resets to that single
   key ascending; "Clear sort" returns to the column-0 default.
5. **Grouping collapses rows.** Selecting a Group-by value renders one group node per
   distinct key value showing `<value> (<count>)`, with the matching rows as children;
   selecting *(none)* restores the exact flat table.
6. **Collapse/expand.** Group nodes start expanded; clicking a node collapses/expands
   it; Expand all / Collapse all toggle every group; the panel re-fits height to the
   visible node count with no nested scrollbar.
7. **Grouping composes with multi-sort.** With grouping on, rows **within** each group
   honor the active multi-column sort, and the groups themselves are ordered by the
   group key with the *(none)* group last.
8. **Composes with the PI-116 filter.** Sorting and grouping operate over the filtered
   set; a filter that excludes everything still shows the no-match empty state (no group
   nodes); clearing the filter restores the full sorted/grouped view.
9. **Standalone panel parity.** `ReferencesPanel` gains header-click single- and
   multi-column sort and the Group-by control, composing with its source/target-type
   dropdowns and free-text filter via AND; single-click navigation and add/delete are
   unaffected.
10. **No regression to navigation / add-delete.** Double-click (section) / single-click
    (panel) navigation, the right-click menu, and add/delete reference all act on the
    correct underlying edge whether the table or the grouped tree is visible (mapped
    through `row_dict` / `record_at`).

## 6. Verification

### 6.1 Manual (desktop)

- Open a heavily-linked record (a topic or planning item with many references) →
  confirm AC-1..AC-8 on the embedded `ReferencesSection`: build a *type then date*
  multi-sort, read the `▲1`/`▼2` indicators, group by *Relationship*, collapse a group,
  type a filter and confirm groups narrow / empty state appears.
- Open the standalone **References** panel → confirm AC-9..AC-10: header-click and
  modifier-click sort, group by *Source type*, compose with the dropdowns + free-text
  filter, click-navigate a Source/Target cell from inside a group.

### 6.2 Automated (pytest + offscreen Qt)

Tests follow the existing offscreen-Qt widget convention used for the v2 UI widgets —
`qapp` + `qtbot` fixtures, `qtbot.addWidget(...)`, reading `section._proxy` /
`section._table`, and the `_grid_cells(section)` helper pattern in
`tests/crmbuilder_v2/ui/widgets/test_references_section.py`. The implementing Work Task
adds:

- **`MultiSortProxyModel`** (model-level, no Qt event loop needed):
  - `set_primary` then `cycle_secondary` produces the expected ordered
    `sort_keys()` and a `lessThan` ordering matching a hand-sorted expectation for a
    *type then date* fixture (AC-2).
  - Equal-key rows preserve source order (stable tiebreaker) — assert the proxy row →
    source row mapping is the identity for a fixture where all keys tie (AC-2).
  - `cycle_secondary` on a present column goes asc → desc → removed; `set_primary`
    collapses to one key; `clear_sort` yields `[(0, Ascending)]` (AC-4).
  - Per-key direction: a *Type asc, Created desc* key list orders a fixture so equal
    types are date-descending (proves the §4.1 tuple-rejection rationale) (AC-2/AC-3).
- **`MultiSortHeaderView`**: after a key-list change, the painted indicator state
  (exposed via a testable `indicator_for(column) -> tuple[rank, order] | None`) matches
  the proxy's `sort_keys()`; `sortKeysChanged` triggers a repaint (AC-3).
- **`GroupingTreeModel`**: from an ordered fixture, `rowCount()` equals the distinct
  group count, each group node's label is `<value> (<n>)`, child order equals input
  order (multi-sort preserved within group), and the *(none)* group sorts last
  (AC-5/AC-7).
- **`ReferencesSection`** integration: selecting a Group-by value swaps to the tree and
  back to the identical table on *(none)* (AC-5); Expand/Collapse all toggles node
  expansion and `_fit_height` changes (AC-6); a filter that excludes all rows shows the
  empty state with zero group nodes (AC-8); a sort built while grouped orders children
  correctly (AC-7).
- **`ReferencesPanel`** integration: header click sorts the previously-unsorted list;
  modifier-click builds a two-key order; the Group-by combo groups the filtered set and
  composes with the source/target dropdowns + free-text filter; click-navigation from a
  grouped row still emits `navigate_requested` (AC-9/AC-10).

## 7. Deferred (non-goals, recorded for boundary clarity)

- **Persisting** a user's sort-key list / group choice across sessions or per entity
  type — a usability polish; this design keeps state in-widget for the session only.
- **Server-side** sort/group/paging — see §4.4; belongs to a separate Work Task if
  PRJ-016 pursues it.
- **Drag-to-reorder** sort columns or a dedicated sort-config dialog — the
  header-click + modifier-click model covers the requirement without new chrome.
- Adding a `UserRole` sort key to the base `_RecordTableModel` for richer standalone
  date/number sorting — only needed if the standalone panel later gains non-text
  columns; the three current text columns sort correctly via case-insensitive
  `DisplayRole`.
