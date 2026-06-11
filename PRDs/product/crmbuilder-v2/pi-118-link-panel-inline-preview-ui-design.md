# PI-118 — Link Panel Inline Linked-Record Preview — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-118 — *Inline preview of a linked record from the link panel*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-070 (area: ui)
**Builds on:** PI-116 (`pi-116-link-panel-search-filter-ui-design.md`) — debounced filter; and PI-117 (`pi-117-link-panel-multicolumn-sort-grouping-ui-design.md`) — `MultiSortProxyModel` + `GroupingTreeModel` + `MultiSortHeaderView`, both already shipped.

## 1. Overview

### Purpose

Specify an **inline preview** of a linked record, reachable from within the
relationship (link) panels, so a user can inspect a link's key fields —
*what is `PI-048`, what's its status, when was it touched* — **without
navigating away** to the linked record and losing their place on the parent.
This is Candidate G of the PRJ-016 enhancement set.

The preview is **additive**: it layers on top of the panels rebuilt by PI-116
(debounced filter) and PI-117 (multi-column sort, grouping, standalone-panel
sort). It must **compose** with active sort, grouping, and the filter; it must
**not restructure the model**; and it must **not regress the row context menu**
(`test_context_menus`).

### The open decomposition question — settled here

PI-118's description leaves the preview *surface* open: **hover card vs.
expand-in-place row vs. side peek**, "to be settled at decomposition." This
design settles it.

**Recommendation: a floating *preview card* (the hover-card form), activated by
*either* mouse hover *or* keyboard, anchored to the row (embedded section) or
the hovered endpoint cell (standalone panel).** Expand-in-place is rejected on a
hard constraint; side peek is the runner-up and is recorded as the natural
future option. Rationale in §3.1.

### Background — what PI-116/PI-117 already shipped (do not re-spec)

Both link surfaces are already rebuilt and share the PI-117 widgets:

- **Embedded** `ReferencesSection`
  (`crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`): a
  `_RefsModel(QAbstractTableModel)` over flattened inbound + outbound rows
  (columns *Direction, Relationship, Identifier, Type, Title, Status, Created,
  Updated*), behind a `MultiSortProxyModel` (filter + multi-key sort) shown in a
  `QTableView`, **and** a sibling `GroupingTreeModel`/`QTreeView` shown when a
  group key is active — the two held in a `QStackedWidget`. Crucially, the
  section already exposes **`_row_at(index) -> dict | None`**, which maps an
  index from *whichever* view is live (proxy-backed table **or** grouped tree)
  back to the same underlying edge dict. Each row dict already carries the
  far-side `other_type` / `other_id` **and** an `other_summary` block (title,
  status, created_at, updated_at) attached by `references.list_touching`.
- **Standalone** `ReferencesPanel`
  (`crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py`): columns *Source,
  Relationship, Target*; a `MultiSortProxyModel` over the base
  `_RecordTableModel`, a sibling grouped `QTreeView`, and the PI-116 free-text +
  source/target-type filters. It exposes **`_record_at_index(index) -> dict |
  None`**, mapping proxy / grouped-tree / source indices back to the reference
  record (which carries `source_type`/`source_id` and `target_type`/`target_id`,
  but **no** `other_summary`). Column 0 = Source, column 2 = Target are
  click-navigable; column 1 (Relationship) is not.

Both already have a per-row right-click menu whose labels are **pinned by
`tests/crmbuilder_v2/ui/test_context_menus.py`** (standalone panel row menu:
`["Go to source", "Go to target", "Delete reference"]`). The preview must leave
those labels byte-identical (§3.6).

### What this design adds (the delta)

1. A reusable **`LinkedRecordPreviewCard`** floating widget that renders a
   linked record's key fields (§4.1).
2. A reusable **`PreviewController`** that wires hover + keyboard activation,
   anchoring, dwell/dismiss timing, and the background enrichment read into a
   host view, reusing each surface's existing index→record resolver (§4.2).
3. Integration into `ReferencesSection` (row-targeted) and `ReferencesPanel`
   (endpoint-cell-targeted), composing with sort/group/filter (§4.3).
4. Acceptance criteria + verification, including a **context-menu regression
   guard** and **composition-with-sort/group/filter** tests (§5–6).

**Scope is the presentation layer only.** The card consumes the row data
already present plus, optionally, the **existing** per-type read
`StorageClient.get_<type>(identifier)` on a background worker. No access-layer,
API, model, or storage change.

## 2. Scope

### In scope

1. The `LinkedRecordPreviewCard` widget — chrome, key-field layout, and the
   loading / empty / error / not-found states.
2. The `PreviewController` — hover dwell, keyboard activation (Space to open,
   Esc to dismiss), anchoring, and dismiss-on-sort/group/filter-change wiring.
3. A presentation-layer **per-type key-field map** that selects which fields a
   given linked-record type shows (no storage change; pure UI config).
4. Integration into both surfaces, reusing `_row_at` / `_record_at_index` so the
   preview targets the correct underlying edge under any sort/group/filter.
5. Acceptance criteria and verification (offscreen-Qt tests), including the
   context-menu regression guard and the composition tests.

### Out of scope

- **Expand-in-place** as the chosen surface (rejected, §3.1) — and any change
  that would turn the flat table into a tree or inject synthetic child rows.
- Any new storage / API / access work. Reference rows **already** carry
  `target_type`/`target_id` (and the embedded section already carries
  `other_summary`); enrichment uses only the existing `get_<type>` read.
- Re-specifying the PI-116 filter / empty state or the PI-117 sort / grouping /
  standalone-panel sort — all shipped and preserved unchanged.
- Adding, removing, or relabelling any **context-menu** action on either surface
  (would break `test_context_menus`); the preview is reached by hover/keyboard,
  not a new menu item (§3.6).
- Editing the linked record from the preview (read-only inspector), pinning
  multiple cards, or persisting a "preview on/off" preference.
- A docked **side-peek** inspector — recorded as the natural future surface
  (§7), not built here.

## 3. Behavior specification

### 3.1 The decision — preview card, not expand-in-place, not side peek

| | **Preview card (hover/keyboard)** — *chosen* | Expand-in-place row | Side peek (docked) |
|---|---|---|---|
| Model impact | **None** — a floating sibling widget; reads the row under cursor/selection via the existing resolver | **Restructures the model** — a flat `QTableView` cannot host a child detail row; needs a tree or synthetic rows | None (a sibling pane fed by selection) |
| Composes with PI-117 multi-sort | Trivially — reads post-sort row | A `QSortFilterProxyModel` **cannot synthesize child rows**; multi-sort and an injected detail row fight | Yes |
| Composes with PI-117 grouping | Trivially — reads the grouped-tree row via `_row_at` | Entangles the 2-level `GroupingTreeModel` with a 3rd "detail" level | Yes |
| Composes with PI-116 filter | Trivially — only previews visible rows | A filtered-out parent orphans its detail row | Yes |
| Context-menu regression | None | None | None |
| "Don't lose your place" | **Met** — overlay, parent stays put | Met, but shifts every row below | Met |
| Embedded-section fit | **Good** — overlay costs no layout space in the height-fit detail pane | Forces re-fit on every expand | **Poor** — the embedded section is narrow and already height-fit; a side pane has nowhere to go |
| Cost / risk | Low — one widget + a controller, zero model change | **High** — violates "must NOT restructure the model" | Medium — layout rework on the embedded surface |

**Expand-in-place is disqualified by the hard constraint** *"must NOT restructure
the model."* The embedded table is `_RefsModel` behind a `MultiSortProxyModel`; a
proxy is flat and cannot grow a child row, and the grouped path is already a
two-level tree whose levels are *group → row*. Adding an in-place detail level
means a new model shape on both presentations — exactly what the constraint
forbids, and it fights multi-sort and grouping besides.

**Side peek is viable but loses on the embedded surface.** `ReferencesSection`
lives *inside* a detail pane, is height-fit to its content, and is narrow; a
docked inspector has no comfortable home there and would force a layout rework.
It remains the right answer **if** a future Work Task wants a persistent,
multi-field inspector (§7).

**The preview card wins because it is model-agnostic by construction.** It is a
floating overlay fed by the row the user points at or selects, resolved through
the *already-shipped* `_row_at` / `_record_at_index` helpers — so it works
identically on the flat table, the grouped tree, any sort order, and the
filtered set, with **zero** model change and no context-menu impact. It directly
delivers "inspect without losing your place."

### 3.2 Trigger and dismiss — timing

**Mouse (enhancement):**

- **Open:** hovering a row (section) / an endpoint cell (panel) starts a
  **400 ms dwell** timer; on expiry the card opens anchored to that row/cell.
  400 ms is deliberately longer than PI-116's 250 ms filter debounce — a preview
  is a stronger commitment than a keystroke and must not flicker during ordinary
  mouse travel across a long link list. Moving to a different row/cell restarts
  the dwell (and re-targets an already-open card).
- **Dismiss:** the pointer leaves both the row/cell **and** the card, after a
  **200 ms grace** (so the user can move the pointer onto the card without it
  vanishing); or any of the global dismissers in §3.7 fires. The card never
  steals pointer focus while hover-driven.

**Keyboard (accessible equal — §3.5):**

- **Open:** with a row selected/focused, **Space** opens the card pinned to the
  selection (no dwell).
- **Dismiss:** **Esc**, or moving the selection with the arrow keys re-targets
  the pinned card to the new row, or any §3.7 dismisser.

The preview is **never** reached through the right-click menu (§3.6), so no
context-menu label changes.

### 3.3 What the card shows — key fields and layout

The card is a compact, read-only inspector. Layout, top to bottom:

1. **Header line** — `<Type label> · <Identifier>` (e.g. *Planning Item ·
   PI-118*), the type in the dim/semibold treatment, the identifier prominent.
2. **Title** — the linked record's title/name, one line, elided on overflow.
3. **Key-field grid** — a 2-column label/value grid of a small, mostly
   type-agnostic set, drawn from the data the card has:
   - Always available: **Status**, **Created**, **Updated** (the embedded
     section already carries these via `other_summary`; dates rendered with the
     same `_fmt_dt` `YYYY-MM-DD HH:MM` shape as the grid).
   - **Relationship context** (embedded section): the `kind_label` +
     direction (e.g. *Blocked by · inbound*), so the card explains *how* this
     record relates to the parent.
   - Up to **three type-specific fields** from the per-type key-field map
     (§4.1) — e.g. a planning item's *item_type* + *status*, a decision's
     *status* + rationale snippet — populated only after the optional enrichment
     read (§3.4) resolves.
4. **Footer hint** — a dim *"Double-click / Enter to open"* affordance, matching
   the existing navigation gesture (the card does not replace navigation).

Missing values render the existing `—` dash sentinel. The card never grows
unbounded: long values elide; the card has a fixed comfortable width
(~`360 px`) and sizes its height to content.

**Standalone panel, column-aware target.** Mirroring the existing
click-navigation (col 0 = Source, col 2 = Target, col 1 = not navigable), the
preview targets **the endpoint under the cursor**: hovering a **Source** cell
previews the source record; a **Target** cell previews the target record; the
**Relationship** cell shows **no** card (consistent with it not being
navigable). Keyboard activation previews the column-0/Source endpoint of the
selected row by default.

### 3.4 Instant render, then enrich (the existing read)

The card opens **instantly** with whatever the row already holds — for the
embedded section that is identifier, type, title, status, created, updated +
relationship (a complete card with **no** read at all); for the standalone panel
that is only the endpoint tuple `type:identifier`, so the panel's card opens
showing the header + a **Loading…** body.

It then **optionally enriches** by calling the **existing** per-type read
`StorageClient.get_<type>(identifier)` on a **background worker**
(`run_in_thread(..., parent=host)` — the same helper `ListDetailPanel.refresh`
uses), routing the result back on the main thread to fill the type-specific
grid fields. This is an *existing* read, not new storage work. A stale-token
guard (the controller stamps each open with a monotonically increasing token and
ignores results whose token is no longer current) prevents a slow read from
painting into a card that has since re-targeted or closed — the same pattern as
`_refresh_counter` in the base panel.

### 3.5 States — loading / empty / error / not-found

The card always renders its header (type + identifier) — that much is known with
zero read — and varies its body:

- **Loading** — enrichment read in flight: the always-available fields render
  immediately (section) or a single dim *"Loading…"* line (panel), with the
  type-specific rows shown as muted placeholders. No spinner chrome beyond a
  text placeholder (matches the panel's existing *"Loading…"* status idiom).
- **Loaded** — the grid fills; placeholders replaced.
- **Empty** — the record resolves but exposes no fields beyond
  identifier/type/title: the grid shows a single dim *"No additional details."*
- **Error** (`StorageConnectionError` / `ServerError` from the read): the header
  stays; the body shows a dim *"Couldn't load details."* The card never raises;
  navigation and the rest of the panel are unaffected. The connection-loss
  signal path the panels already own is **not** triggered by a preview read
  failure (a preview is best-effort, not a panel load).
- **Not found** (`NotFoundError` — the far record was deleted but a stale edge
  remains; the section docstring already notes version-keyed singletons / catalog
  rows with no summary): the body shows a dim *"Record not found (it may have
  been deleted)."* This is a real case for orphaned edges and must not look like
  an error.

### 3.6 Context menu — unchanged (regression guard)

The preview is **not** a context-menu action. Both surfaces keep their existing
menus byte-identical:

- `ReferencesPanel._build_context_menu`: row menu stays
  `["Go to source", "Go to target", "Delete reference"]`; whitespace stays
  `["New reference"]` — exactly as `test_context_menus` asserts.
- `ReferencesSection._show_row_menu`: stays *Delete reference* (when a client is
  present) + *Go to {identifier}*.

Opening the right-click menu is itself a **dismisser** of any open card (§3.7),
so the menu and the preview never overlap. A new regression-guard test (§6) pins
the menu labels *with the preview feature present*, so a later change that adds a
"Preview" item is caught. (Adding such an item is explicitly deferred, §7, to
keep the no-regression guarantee.)

### 3.7 Composition with sort, grouping, and filter — the core rule

The card is a floating sibling fed by the *already-shipped* index→record
resolvers, so it composes for free:

- **Target resolution** goes through `ReferencesSection._row_at(index)` /
  `ReferencesPanel._record_at_index(index)`, which already map *any* live view —
  the proxy-backed flat table, the grouped `QTreeView`, or the raw source model
  — back to the same underlying edge dict. The card therefore previews the
  **correct** record whether the table or the grouped tree is showing, under any
  multi-column sort order, and only ever for rows that survive the filter.
- **A sort-key change** (`MultiSortProxyModel.sortKeysChanged`), a **group-key
  change** (`_on_group_changed`), or a **filter change**
  (`LinkFilterInput.filterChanged` / the dropdowns) **dismisses** an open card.
  Each can move or remove the anchored row, so the safe, predictable rule is:
  any reorder/regroup/refilter closes the card; the user re-points to reopen.
- **A filter that hides the previewed row** closes the card by the same rule;
  the PI-116 no-match empty state is untouched (no card renders when there are
  no rows).
- **Switching the grouped tree on/off** (the `QStackedWidget` swap in the
  section; the show/hide in the panel) dismisses the card.

Net: the preview **observes** the panel's post-filter/sort/group state and never
**mutates** it. There is no path by which opening, enriching, or closing the
card calls `set_records`, `beginResetModel`, `invalidate`, or any sort/group
mutator — asserted by a test (§6).

### 3.8 No model restructuring — explicit invariants

- The card and controller hold **no** model; they read through the resolvers.
- `_RefsModel`, `MultiSortProxyModel`, `GroupingTreeModel`, and the base
  `_RecordTableModel` are **unchanged**. Their `rowCount` / `columnCount`,
  `_COLUMNS`, and the proxy→source mapping are identical before and after a
  preview opens.
- The per-type key-field map and the card are **UI config**; no new entity
  field, no `other_summary` shape change, no API field.

## 4. Component design

Two small reusable presentation classes plus the wiring into the two surfaces.

### 4.1 `LinkedRecordPreviewCard` — the floating inspector

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/linked_record_preview.py`
- **Class:** `LinkedRecordPreviewCard(QWidget)`, constructed with
  `Qt.WindowType.ToolTip` (hover, non-focus-stealing) or, when keyboard-pinned,
  `Qt.WindowType.Popup` (focusable so Esc/Tab and screen readers work) — the
  controller picks the flag per activation. Frameless card chrome reuses the
  `EngagementPicker` popup precedent (1 px `color.neutral.200` border, white
  fill) and the `t(...)` styling tokens; **no new design tokens**.
- **Public API:**
  - `show_for(record: dict, *, entity_type: str, identifier: str,
    relationship: str | None, anchor_global: QPoint, focusable: bool) -> None`
    — render the header + always-available fields from `record` immediately and
    position near `anchor_global` (flipping above/left when it would clip the
    screen edge).
  - `set_enriched(fields: list[tuple[str, str]]) -> None` — replace the
    type-specific placeholder rows once the read resolves.
  - `set_state(state: Literal["loading","loaded","empty","error","not_found"])`
    — drive the §3.5 body text.
  - `dismiss() -> None` — hide and `deleteLater()` (per the v2 transient-widget
    GC rule: a card that outlives its host while a worker is pending must be torn
    down deterministically).
- **Accessibility:** sets `accessibleName` = `<type> <identifier>` and
  `accessibleDescription` = the rendered key fields, so a screen reader announces
  the preview when it is keyboard-pinned.
- **Per-type key-field map:** a module-level
  `_PREVIEW_FIELDS: dict[str, list[tuple[str, str]]]` — `entity_type` → ordered
  `(label, record_key)` pairs — with a generic fallback (Status / Created /
  Updated). Presentation config only; adding a type extends this dict, no
  storage change.

### 4.2 `PreviewController` — activation, anchoring, dismissal, enrichment

- **File:** same module (or `linked_record_preview.py` sibling
  `preview_controller.py`).
- **Class:** `PreviewController(QObject)`, installed on a host view by the
  surface. Constructed with the host view, the host's **index→record resolver**
  (a `Callable[[QModelIndex], dict | None]` — `_row_at` or `_record_at_index`),
  the `StorageClient`, and a **field extractor** `Callable[[dict], tuple[str,
  str, str, str | None]]` returning `(entity_type, identifier, title,
  relationship)` for the resolved record (so the section's `other_type`/`other_id`
  vs. the panel's column-aware source/target endpoint selection both fit one
  controller).
- **Responsibilities:**
  - Install an event filter on the view's `viewport()` to catch `MouseMove`
    (start/restart the **400 ms** dwell `QTimer` for the row/cell under the
    cursor), `Leave` (start the **200 ms** grace dismiss), and the keyboard
    `Space`/`Esc` keys; map the cursor position to an index via
    `indexAt(pos)` and resolve the record via the supplied resolver.
  - On open: stamp a monotonic **token**, build the card, `show_for(...)`, then
    fire the enrichment read `run_in_thread(lambda:
    client.get_<type>(identifier), on_success=…, on_error=…, parent=host)`;
    map outcomes to `set_enriched` / `set_state("error")` /
    `set_state("not_found")`, dropping any result whose token is stale (§3.4).
  - Track in-flight workers and `wait()` on host teardown (mirrors
    `ListDetailPanel.closeEvent`), and `deleteLater()` the card on dismiss.
  - Expose `dismiss()` and connect it to the host's reorder/regroup/refilter
    signals (§3.7); the surfaces wire these in §4.3.
- **Why a controller, not logic inside each panel:** both surfaces need identical
  dwell/dismiss/anchor/enrich behavior; only *which index resolves to which
  record* differs, and that is injected. One controller keeps the timing and the
  worker lifecycle in one place.

### 4.3 Wiring — `ReferencesSection` and `ReferencesPanel`

- **`ReferencesSection`** (`references_section.py`):
  - Construct one `PreviewController` over the section, sharing it across the
    flat `QTableView` and the grouped `QTreeView` (both already route through
    `_row_at`). The field extractor returns
    `(row["other_type"], row["other_id"], row["title"], row["kind_label"])`.
  - Connect `dismiss()` to `self._proxy.sortKeysChanged`,
    `self._group_combo.currentIndexChanged`, and `self._filter.filterChanged`
    (the existing PI-116/PI-117 signals) so any reorder/regroup/refilter closes
    the card.
  - **No** change to `_show_row_menu`, `_on_double_clicked`, `_fit_height`, or
    any model. The card overlays; it costs no layout height.
- **`ReferencesPanel`** (`panels/references.py`):
  - Construct one `PreviewController` over the panel, shared by the table and the
    grouped tree (both route through `_record_at_index`). The field extractor is
    **column-aware**: for the hovered column it picks the source endpoint (col 0)
    or target endpoint (col 2), and returns `None` (no card) for col 1.
  - Connect `dismiss()` to `self._proxy.sortKeysChanged`,
    `self._group_combo.currentIndexChanged`, `self._text_filter.filterChanged`,
    and the source/target dropdowns' `currentIndexChanged`.
  - **No** change to `_build_context_menu`, `_on_cell_clicked`, or any model.

### 4.4 Styling

Card chrome, header, grid labels, and the dim state lines reuse existing tokens
(`t("color.neutral.200/500/800")`, `t("font.weight.semibold")`,
`t("font.size.*")`) and the `EngagementPicker` popup pattern. No new tokens, no
new icons.

## 5. Acceptance criteria

1. **Preview opens on hover.** Hovering a section row (or a Source/Target cell on
   the standalone panel) for the dwell interval opens a card anchored to it
   showing the linked record's type, identifier, title, status, and dates;
   hovering the Relationship cell on the standalone panel opens **no** card.
2. **Preview opens by keyboard.** With a row selected, Space opens the card
   pinned; Esc dismisses it; arrow-key selection moves the pinned card to the new
   row. Hover never steals focus.
3. **Instant render then enrich.** The card renders immediately from row data;
   type-specific fields populate after the existing `get_<type>` read resolves on
   a background worker, without blocking the UI thread.
4. **All four non-happy states.** Loading shows placeholders; a deleted far
   record shows *"Record not found …"*; a read failure shows *"Couldn't load
   details."* without raising or tripping the panel's connection-loss path; a
   record with no extra fields shows *"No additional details."*
5. **Composes with multi-column sort.** With a *type-then-date* multi-sort
   active, the card previews the **correct** underlying record for the hovered
   visual row.
6. **Composes with grouping.** With a group key active (grouped `QTreeView`
   showing), hovering/selecting a child row previews the correct record;
   hovering a **group node** opens no card.
7. **Composes with the filter.** Only visible (filtered) rows preview; a filter
   that excludes everything yields the existing no-match empty state and no card.
8. **Dismiss on reorder/regroup/refilter.** Changing the sort keys, the group
   key, or any filter dismisses an open card.
9. **Context menu unchanged.** The standalone row menu remains
   `["Go to source", "Go to target", "Delete reference"]`, whitespace remains
   `["New reference"]`, and the section menu remains *Delete reference* + *Go
   to …* — with the preview feature present. Right-clicking dismisses an open
   card.
10. **No model restructuring.** Opening, enriching, or dismissing a card calls no
    model mutator (`set_records` / `beginResetModel` / `invalidate` / sort/group
    mutators); `_RefsModel` / `_RecordTableModel` / `MultiSortProxyModel` /
    `GroupingTreeModel` shape and the proxy→source mapping are identical before
    and after.

## 6. Verification

### 6.1 Manual (desktop)

- Open a heavily-linked record's embedded References section → hover a row,
  confirm the card and its fields (AC-1, AC-3); build a *type-then-date*
  multi-sort and confirm the card tracks the right row (AC-5); group by
  *Relationship*, hover a child and a group node (AC-6); type a filter and
  confirm only visible rows preview and reorder dismisses the card (AC-7, AC-8);
  Space/Esc/arrow keyboard path (AC-2).
- Open the standalone **References** panel → hover Source vs. Target vs.
  Relationship cells (AC-1); confirm enrichment loads the endpoint record;
  confirm a stale/deleted endpoint shows *"Record not found"* (AC-4); confirm the
  right-click menu is unchanged and dismisses the card (AC-9).

### 6.2 Automated (pytest + offscreen Qt)

Tests follow the existing offscreen-Qt widget convention (`qtbot.addWidget`,
reading `section._proxy` / `section._table` / `panel._model`, the
`_grid_cells`/`client_stub` helpers in
`tests/crmbuilder_v2/ui/widgets/test_references_section.py` and
`tests/crmbuilder_v2/ui/test_context_menus.py`). The implementing Work Task adds:

- **`LinkedRecordPreviewCard`** (widget-level): `show_for(...)` renders the
  header + always-available fields; `set_state("not_found"/"error"/"empty")`
  renders the documented body text; `set_enriched(...)` replaces placeholders;
  `accessibleName`/`accessibleDescription` are set (AC-1/AC-3/AC-4).
- **`PreviewController`** (logic-level, resolver injected): given a fake resolver
  and `client_stub`, an open targeting a row resolves the expected record; a
  stale token is dropped (a late `on_success` after re-target does not repaint);
  a `NotFoundError`/`StorageConnectionError` maps to the right state (AC-3/AC-4).
- **Composition — `ReferencesSection`:** with a *type-then-date* multi-sort, the
  record the controller resolves for visual row *r* equals the hand-sorted
  expected edge (AC-5); with grouping on, a child index resolves correctly and a
  group-node index resolves to `None` → no card (AC-6); a filter excluding all
  rows shows the empty state and the controller opens no card (AC-7);
  `sortKeysChanged` / group-combo change / `filterChanged` each call `dismiss()`
  (AC-8).
- **Composition — `ReferencesPanel`:** column-aware target — a col-0 hover
  resolves the source endpoint, col-2 the target endpoint, col-1 `None` (AC-1);
  composition with the source/target dropdowns + free-text filter (AC-7); the
  grouped tree resolves child records (AC-6).
- **Context-menu regression guard (extends `test_context_menus`):** after a
  `PreviewController` is installed, `panel._build_context_menu(row_index)` still
  yields `["Go to source", "Go to target", "Delete reference"]` and the
  whitespace menu `["New reference"]`; the section menu still yields *Delete
  reference* + *Go to …* (AC-9).
- **No-mutation guard:** spy/patch the model mutators (`set_records`,
  `beginResetModel`, the proxy `invalidate`/sort mutators); assert none is called
  across an open→enrich→dismiss cycle, and that proxy→source mapping is unchanged
  (AC-10).

## 7. Deferred (non-goals, recorded for boundary clarity)

- **Side-peek inspector** — a persistent, docked, multi-field panel. The natural
  next surface if richer, always-on inspection is wanted; rejected here only
  because it costs layout space on the height-fit embedded section (§3.1).
- **A "Preview" context-menu / toolbar item** — would change the pinned menu
  label set (§3.6); deferred to keep the no-regression guarantee. If added later,
  the §6 regression guard is the test to update intentionally.
- **Editing from the preview** — the card is a read-only inspector; mutation
  stays in the existing create/delete dialogs.
- **Pinning multiple cards / a preview-on-off preference** — session-only,
  single transient card here.
- **Server-side enrichment / batched prefetch** — the card reads one record
  lazily via the existing `get_<type>` call; a prefetch or a combined endpoint is
  a separate Work Task if the lazy read ever proves too slow on a cold panel.
