# PI-148 — Make the Link-Panel Inline Preview Discoverable — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-148 — *Make the link-panel inline preview discoverable — visible per-row affordance, not just timed hover*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-150 (area: ui); ratified for the WSK-138 re-decomposition by WTK-152 — see `pi-148-discoverable-preview-affordance-design-verification-wtk152.md`
**Builds on:** PI-118 (`pi-118-link-panel-inline-preview-ui-design.md`) — the `LinkedRecordPreviewCard` + `PreviewController`, already shipped; and the PI-116 filter / PI-117 sort+grouping / PI-119 drag-resize / PI-120 generalized grid rebuilds beneath it, all shipped.

## 1. Overview

### Purpose

The PI-118 inline preview works, but it is **undiscoverable**. It opens only on
a **400 ms hover dwell** or the **Space** key, with **no visible cue that a
preview exists** — which is why it read as "not working" until the hover-tracking
bug was fixed (commit `0e9606b`) and the trigger had to be *documented* for
anyone to find it. A feature a user must be told about is, for usability
purposes, not shipped.

This design specifies a **discoverable affordance**: a visible, operable cue on
each row that opens the *same* `LinkedRecordPreviewCard`, so users find the
feature without being told. It is the discoverability half of Candidate G in the
PRJ-016 enhancement set; PI-118 built the inspector, PI-148 makes it findable.

The affordance is **purely additive**. The existing **400 ms hover-dwell** and
**Space-key** triggers are preserved unchanged as *accelerators*; the row
right-click menu (`test_context_menus`), the *Go to* / *Open* actions, and
double-click navigation are untouched. No storage, API, access-layer, or model
change.

### The open decomposition question — settled here

PI-148's description leaves the affordance *form* open: **hover-reveal peek icon
vs. always-visible icon vs. info-column**, "to be settled at decomposition."
This design settles it.

**Recommendation: a single hover/focus-reveal *peek-icon button*, owned by the
existing `PreviewController`, that appears the instant the pointer enters a row
(or a row gains keyboard focus/selection), pinned to the trailing edge of the
row — or, on the standalone panel, the hovered endpoint cell. Clicking (or
Enter/Space on it) opens the same preview card.** Always-visible-per-row is
rejected on visual noise + per-row-widget cost on the very large link lists this
PI targets; the info-column is rejected because it restructures the shared column
model and fights sort/group/resize. Rationale in §3.1.

### Background — the seam this design reuses (do not re-spec)

Both link surfaces already host a `PreviewController`
(`crmbuilder-v2/src/crmbuilder_v2/ui/widgets/linked_record_preview.py`), and the
controller already owns exactly the machinery a discoverable affordance needs:

- **One controller serves all three target surfaces.** The embedded
  `ReferencesSection` grid, the **generalized Work-Task grid** (the
  `WorkTaskGridSection` / `_WORK_TASK_CONTRACT` parameterization of the *same*
  `ReferencesSection` widget, PI-120 / WTK-076), and the entity-fields grid all
  install one `PreviewController` in `ReferencesSection._install_preview`; the
  standalone `ReferencesPanel` installs one in
  `ReferencesPanel._install_preview`. So an affordance built **into the
  controller** lands on all three surfaces from two call sites that already
  exist — no per-surface duplication.
- **`PreviewController.attach_view(view)`** already installs an event filter on
  each view's `viewport()` with mouse-tracking on, tracking the hovered index
  (`_on_mouse_move`), the selection (`_on_current_changed`), and the dwell/grace
  timers. The affordance reuses this exact hover/selection bookkeeping; it does
  **not** add a second event-tracking path.
- **`PreviewController._open(view, index, *, focusable)`** is the single open
  path. It resolves the row via the injected `resolver` (`_row_at` /
  `_record_at_index`), the previewable endpoint via the injected `extractor`
  (column-aware on the standalone panel), guards against group-node / invalid /
  non-previewable targets, builds the card, and fires the enrichment read. The
  affordance opens by calling this same path — so it cannot show a card the
  hover/Space paths could not.
- **`PreviewController.dismiss()`** is already connected by every surface to its
  reorder / regroup / refilter signals (`sortKeysChanged`, the group combo, the
  filter inputs, the source/target dropdowns). The affordance hides on the same
  dismissers for free.

### What this design adds (the delta)

1. A **`PreviewAffordance`** — one reusable, repositioned overlay peek-icon
   button owned by the `PreviewController` (§4.1).
2. A small **public open method** on `PreviewController` —
   `open_for_index(view, index, *, focusable=True)` — that the affordance click
   calls, reusing the existing `_open` (§4.2).
3. Reveal / placement / hide wiring inside the controller's existing hover and
   selection handlers, and a column-aware placement on the standalone panel
   (§4.2–§4.3).
4. One bundled Lucide **`eye.svg`** asset (the only new file beyond the module
   edit and tests) (§4.4).
5. Acceptance criteria + verification, including a **context-menu regression
   guard**, an **accelerators-intact** guard, an **accessibility** check
   (focusable + labeled + keyboard-operable), and a **no-model-mutation** guard
   (§5–6).

**Scope is the presentation layer only**, inside the already-shipped preview
module and the two `_install_preview` call sites. No new entity field, no API
field, no model shape change.

## 2. Scope

### In scope

1. The `PreviewAffordance` overlay button — chrome, reveal/hide behavior,
   placement (row-trailing on the grids; endpoint-cell-trailing and column-aware
   on the standalone panel), and accessibility (focusable, labeled,
   keyboard-operable).
2. The `PreviewController.open_for_index` public method and the controller-side
   wiring that shows/hides/repositions the affordance from the existing hover +
   selection handlers and the existing dismissers.
3. The one bundled `eye.svg` icon asset.
4. Coverage of all three target surfaces — the embedded `ReferencesSection`
   grid, the generalized Work-Task grid (`WorkTaskGridSection`), and the
   standalone `ReferencesPanel` — **consistently**, by virtue of building into
   the shared controller.
5. Acceptance criteria and verification (offscreen-Qt tests), including the
   context-menu, accelerators, accessibility, and no-mutation guards.

### Out of scope

- **Always-visible-per-row icons** and an **info-column** as the chosen form
  (both rejected, §3.1).
- Re-specifying the `LinkedRecordPreviewCard` itself — its layout, states,
  enrichment read, and styling are PI-118 and reused **unchanged**. The
  affordance only changes *how the card is triggered*, never *what it shows*.
- Re-specifying the PI-116 filter, PI-117 sort/grouping, PI-119 drag-resize, or
  PI-120 generalized-grid contracts — all shipped and preserved.
- Adding, removing, or relabelling any **context-menu** action on any surface
  (would break `test_context_menus`); the affordance is a row overlay, **not** a
  new menu item.
- Changing the **400 ms hover-dwell** or **Space** triggers; they remain exactly
  as PI-118 shipped them, as accelerators.
- Editing the linked record from the affordance, persisting a "preview on/off"
  preference, or pinning multiple cards.
- A standing toolbar "Preview" button or a docked side-peek inspector (the
  latter recorded by PI-118 §7 as the future surface).

## 3. Behavior specification

### 3.1 The decision — hover/focus-reveal peek button, not always-visible, not info-column

| | **Reveal peek button (one overlay)** — *chosen* | Always-visible per-row icon | Info-column |
|---|---|---|---|
| Discoverable | **Yes** — appears the instant the pointer enters any row (0 ms, not 400 ms) as an unmistakable clickable glyph; users hover rows constantly (to read, right-click, double-click), so it is found in normal use | Yes — visible at rest on every row | Yes — a labeled column header advertises it |
| Visual noise | **Low** — nothing at rest; one glyph on the active row only | **High** — a glyph on every row of a long link list competes with the data | High — a permanent column of identical glyphs |
| Cost on large link lists (this PI's target) | **Low** — one overlay widget repositioned, no per-row widgets | **High** — a persistent per-row widget (`setIndexWidget` × N) or a paint+hit-test delegate on every visible row | Medium — a real column the model/proxy must carry |
| Touches the shared column model | **No** — pure overlay; `_COLUMNS` / `_WORK_TASK_COLUMNS` / `_ENTITY_FIELDS_COLUMNS` unchanged | No (if overlaid) / High (if a real cell) | **Yes** — adds a column to *every* contract; shifts each contract's `stretch_column` index and the proxy column count |
| Composes with PI-117 multi-sort / grouping | **Trivially** — overlays the resolved visual row via the existing resolver | Trivially | Fights sort (a glyph column is non-sortable) and the grouped-tree column layout |
| Composes with PI-119 drag-resize | **Trivially** — not a column | Trivially | A new fixed/interactive column to integrate with the resize model |
| Keyboard / accessibility | **Met** — appears on row focus/selection too; a focusable, labeled `QPushButton` in tab order | Hard — N focusable per-row buttons inflate the tab order | Met, but a column of buttons inflates the tab order |
| Context-menu / Go-to / Open regression | None | None | None (but more surface to keep stable) |
| Cost / risk | **Low** — one widget + one public method on an existing controller | Medium–High | **High** — column-model change across three contracts |

**The info-column is disqualified by the additive / no-restructure constraint.**
The three grids share one `GridContract`-parameterized widget; an info-column
means editing `_COLUMNS`, `_WORK_TASK_COLUMNS`, and `_ENTITY_FIELDS_COLUMNS`,
re-indexing each contract's `stretch_column`, and growing the proxy/grouping
column count — a model-shape change on every surface, exactly what the PI says to
avoid, and it fights multi-sort, grouping, and drag-resize besides.

**Always-visible-per-row loses on this PI's own premise.** PRJ-016 exists for
*objects that carry large numbers of links*; a persistent per-row glyph is either
N focusable widgets (tab-order and memory cost) or a paint+hit-test delegate on
every visible row, and it adds steady visual noise to precisely the long lists
the project is trying to make *more* legible.

**The reveal peek button wins because it is the standard discoverable
row-action pattern** (GitHub/Gmail/VS Code reveal row actions on hover/focus for
exactly this reason) **and because it is model-agnostic by construction.** It is
one overlay widget the controller repositions to the active row, fed by the
*already-shipped* resolver, so it works identically on the flat table, the
grouped tree, any sort order, the filtered set, and all three contracts — with
**zero** column or model change and no context-menu impact. It fixes the exact
failure mode (hovering produced no visible cue) by replacing "nothing for 400 ms"
with "an obvious peek glyph, immediately."

### 3.2 Reveal and hide — timing and placement

**Reveal (the discoverability win):**

- **On pointer hover:** when the pointer enters a row (grids) or a *previewable*
  endpoint cell — Source (col 0) or Target (col 2) on the standalone panel — the
  peek button appears **immediately** (no dwell), pinned to the **trailing edge**
  of that row/cell. This is the cue the current build lacks: the user sees a
  clickable affordance the moment they touch a row, long before the 400 ms dwell
  would have opened a card.
- **On keyboard focus/selection:** when a row becomes the current index via
  arrow-key navigation or Tab into the view, the button repositions to that row
  and is reachable in the tab order — so keyboard-only users discover it too.
- **Non-previewable targets show no button:** a group node (grouped tree), an
  empty/invalid row, or the standalone panel's **Relationship** cell (col 1)
  reveals **no** button — identical to the rule that those targets open no card.

**Hide:**

- The pointer leaves both the row/cell **and** the button, after the **same
  200 ms grace** the card already uses (so the user can travel from the row onto
  the button without it vanishing).
- Any of the existing §3.7 dismissers fires (reorder / regroup / refilter /
  group-tree swap / right-click menu) — the button hides with the card.
- A scroll or column drag-resize that would move the anchored row hides the
  button (it re-reveals on the next hover/focus); no stale floating glyph.

**Placement detail.** The button is a small (`28×28`, the existing
`icon_button` square) overlay child of the **view's `viewport()`**, moved to the
right edge of `view.visualRect(index)` and vertically centered, with a few px of
inset so it never overlaps the scrollbar or the `MultiSortHeaderView`
precedence glyphs. On the standalone panel the anchor is the hovered *cell* rect
(so the glyph sits on the Source or Target cell the user is pointing at),
matching the column-aware card.

### 3.3 What clicking does — opens the same card, pinned

Activating the button (mouse click, or Enter/Space when it holds keyboard focus)
calls `PreviewController.open_for_index(view, index, focusable=True)`, which
delegates to the existing `_open(view, index, focusable=True)`:

- The card opens **pinned** (the `Qt.WindowType.Popup`, focusable variant), so
  Esc/Tab and screen readers work — identical to the Space-key path, **not** the
  transient hover tooltip. A discoverable, deliberate click deserves a card that
  stays put.
- It shows **exactly the same content** as the hover/Space card for that row:
  the same header, title, always-available Status/Created/Updated, the same
  per-type enriched fields via the same `get_<type>` read, and the same
  loading/empty/error/not-found states. The affordance changes the *trigger*,
  never the *card*.
- On the standalone panel the endpoint previewed matches the cell the button is
  anchored to (Source for col 0, Target for col 2) — the same column-aware
  `_preview_target` extractor decides, so there is no second endpoint-selection
  rule to keep in sync.

Esc, the §3.7 dismissers, and the 200 ms hover-grace dismiss the card as before.

### 3.4 Accelerators preserved — hover-dwell and Space unchanged

The button is **additive**. The PI-118 triggers are left byte-for-byte:

- **400 ms hover-dwell** (`PreviewController.DWELL_MS`) still opens a transient
  (non-focusable, tooltip) card on dwell expiry. The button revealing at 0 ms and
  the dwell card opening at 400 ms over the *same* row are consistent: the glyph
  is the discoverability cue; the dwell remains the no-click accelerator for users
  who already know the gesture. If the user clicks the button before the dwell
  fires, the click's pinned card supersedes (a fresh `_open` stamps a new token
  and tears down any prior card) — no double card.
- **Space** still opens a pinned card for the selected row; **Esc** dismisses.
  Arrow-key selection still re-targets a pinned card *and* repositions the button.

A test pins both accelerators as still-present after the affordance lands (§6).

### 3.5 Accessibility — the affordance is the *accessible* path, not a regression of it

PI-118 made the keyboard path (Space/Esc/arrows) the accessible equal of hover.
The visible button strengthens that:

- It is a real **focusable** `QPushButton` (the `icon_button` Icon-only
  category), reachable by Tab when revealed on the focused row, and activatable by
  **Enter/Space** while focused.
- It carries an **`accessibleName`** of `"Preview <identifier>"` (e.g. *"Preview
  PI-118"*) and a visible **tooltip** *"Preview"*, so a screen reader announces a
  named, purposeful control rather than an unlabeled glyph. (`icon_button`
  already requires a tooltip for exactly this reason.)
- Only **one** button exists at a time (the active row's), so the tab order is not
  inflated by N per-row buttons — a concrete advantage over always-visible.
- The card it opens is the focusable `Popup` variant, so focus moves into the card
  and Esc returns it — unchanged from the Space path.

### 3.6 Context menu, Go-to, Open, double-click — all unchanged (regression guard)

The affordance is **not** a menu item and changes **no** existing action:

- The standalone panel row menu stays `["Go to source", "Go to target", "Delete
  reference"]`; whitespace stays `["New reference"]` — exactly as
  `test_context_menus` asserts.
- The grid row menus stay as their contracts define them (References: *Delete
  reference* + *Go to …* + *Open …*; Work Tasks / entity-fields: *Go to …* +
  *Open …* + *Copy identifier*). Untouched.
- Double-click still emits `navigate_requested`; the *Open …* action still emits
  `open_requested`. The button does **neither** — it only opens the preview card.
- Opening a context menu remains a **dismisser**: it hides the card **and** the
  peek button so menu and overlay never collide.

A regression-guard test pins all of the above *with the affordance installed*, so
a later change that turns the affordance into a menu/toolbar item is caught
intentionally (§6).

### 3.7 Composition with sort, grouping, filter, resize — inherited, not re-built

The button rides the controller's existing composition guarantees:

- **Target resolution** is the same injected `resolver` (`_row_at` /
  `_record_at_index`), so the button previews the **correct** underlying record
  whether the flat table or the grouped tree is showing, under any multi-sort
  order, and only for rows that survive the filter.
- **Reorder / regroup / refilter** already call `dismiss()`; the button hides on
  the same signal — no new wiring beyond hiding the overlay inside `dismiss()`.
- **A filtered-out or scrolled-away row** simply stops being hovered/focused, so
  no button shows for it; the PI-116 no-match empty state is untouched.
- **Group-node rows** resolve to `None` → no button, mirroring "no card."

### 3.8 No model restructuring — explicit invariants (carried over)

- The affordance and controller hold **no** model; they read through the
  resolvers and overlay the viewport.
- `_RefsModel`, `MultiSortProxyModel`, `GroupingTreeModel`, the base
  `_RecordTableModel`, and all three `GridContract` column lists are
  **unchanged** — same `rowCount`/`columnCount`, same `_COLUMNS`, same
  `stretch_column`, same proxy→source mapping before and after a button shows.
- No new entity field, no `other_summary`/record shape change, no API field.

## 4. Component design

One small overlay widget, one public method on the existing controller, the
reveal/hide/placement wiring inside the controller's existing handlers, and one
bundled icon.

### 4.1 `PreviewAffordance` — the reveal peek button

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/linked_record_preview.py`
  (same module as the card + controller; the affordance is part of the preview
  feature, not a standalone widget).
- **Form:** a single `QPushButton` built via the existing
  `form_helpers.icon_button("eye", tooltip="Preview")` — the Icon-only `28×28`
  category, tinted `color.neutral.700`, so it reuses the established button chrome
  and needs **no new design token**. Parented to the active view's `viewport()`
  so it overlays the cells (not the header / scrollbar).
- **Owned by the controller, one instance.** The controller lazily creates a
  single `PreviewAffordance` and reuses it, repositioning and reparenting it to
  whichever attached view is active. There is never more than one on screen.
- **Public surface (called by the controller):**
  - `show_at(view, index, *, viewport_rect) -> None` — reparent to `view`'s
    viewport if needed, set `accessibleName` = `"Preview <identifier>"`, move to
    the trailing edge of `viewport_rect`, and `show()`/`raise_()`.
  - `hide_affordance() -> None` — `hide()` (kept around for reuse; not deleted
    per open).
  - its `clicked` signal is connected by the controller to
    `open_for_index(...)`.
- **Why a widget, not a delegate-painted glyph:** a real `QPushButton` is
  natively focusable, tab-reachable, tooltip-bearing, and keyboard-activatable —
  every accessibility requirement (§3.5) for free — whereas a painted glyph would
  need bespoke focus/hit-test/AT plumbing. One reused button costs nothing on long
  lists, unlike a per-row delegate.

### 4.2 `PreviewController` — reveal/hide wiring + the public open method

Reuses the controller's existing hover (`_on_mouse_move`), leave/grace, and
selection (`_on_current_changed`) machinery; the delta is small and local.

- **New public method:**
  - `open_for_index(self, view, index, *, focusable: bool = True) -> None` —
    thin public wrapper over the existing private `_open(view, index,
    focusable=focusable)`. Exists so the affordance (and tests) open a card for a
    specific index without reaching into a private method, and so the open path
    stays single-sourced (the affordance cannot diverge from hover/Space).
- **Reveal:** in `_on_mouse_move`, after the existing dwell bookkeeping, if the
  hovered index resolves to a previewable target (reuse `resolver` + `extractor`,
  the same guards as `_open`), call `affordance.show_at(view, index,
  viewport_rect=view.visualRect(index))`; otherwise `hide_affordance()`. In
  `_on_current_changed`, reposition the button to the newly-current row the same
  way (keyboard reveal). Group-node / non-previewable / invalid → hidden.
- **Hide:** in the existing `Leave` branch, start the existing grace timer and, on
  expiry, hide the button alongside the card. Add `affordance.hide_affordance()`
  to `dismiss()` so every reorder/regroup/refilter/right-click already wired to
  `dismiss()` hides the button with no new connections. Hide on the view's
  `verticalScrollBar().valueChanged` and the header's `sectionResized` (cheap,
  per-view connections in `attach_view`) so the glyph never floats over the wrong
  row.
- **Click:** connect `affordance.clicked` to a small slot that opens
  `open_for_index(active_view, current_affordance_index, focusable=True)`. The
  controller records the `(view, index)` the button is currently shown for, so the
  click targets exactly the row the glyph sits on (and, on the standalone panel,
  the cell column, so the column-aware extractor picks the right endpoint).
- **Teardown:** the button is a child of a viewport (hence of the host) and is
  hidden in `dismiss()`/`shutdown()`; it needs no separate worker lifecycle (it
  spawns none). `shutdown()` already waits on enrichment workers.

### 4.3 The two install sites — no per-surface affordance code

Because the affordance lives in the controller, the two existing
`_install_preview` methods need **no affordance-specific code** beyond what they
already do (construct the controller, `attach_view` each view, connect
`dismiss()` to the surface's reorder/regroup/refilter signals):

- **`ReferencesSection._install_preview`** (covers the embedded references grid,
  the **Work-Task grid** via `WorkTaskGridSection` / `_WORK_TASK_CONTRACT`, and
  the entity-fields grid via `EntityFieldsGridSection`): the row-trailing button
  appears on table and tree rows; the extractor already returns the far-side
  `(other_type, other_id, title, <contract>.preview_subtitle_key)`, so the button
  previews the far-side record consistently across all three contracts. **All
  three grid surfaces get the affordance from this one method.**
- **`ReferencesPanel._install_preview`**: the cell-trailing, column-aware button
  appears on Source (col 0) and Target (col 2) cells and **not** on the
  Relationship cell (col 1), because the existing `_preview_target` extractor
  already returns `None` for col 1 — the affordance's reveal check uses the same
  extractor, so the rule is shared, not re-encoded.

This is the same "build it in the controller, both surfaces inherit it" rationale
PI-118 used for the card.

### 4.4 Styling and the one new asset

- The button reuses `form_helpers.icon_button` (Icon-only `28×28`,
  `color.neutral.700`, required tooltip) — **no new design token**.
- The **one new file** the build adds is the bundled Lucide **`eye.svg`** under
  `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/lucide/` (the codebase bundles
  Lucide icons per-name and `lucide()` raises `FileNotFoundError` for an
  un-bundled name, so the asset must ship with the change). The "eye" glyph is the
  conventional peek/preview affordance and is unused elsewhere, so it does not
  collide with `external-link` (the *Open* action) or any existing icon.

## 5. Acceptance criteria

1. **A visible affordance is present per row.** Hovering any grid row (embedded
   references, Work-Task, or entity-fields) or a Source/Target cell on the
   standalone panel immediately reveals a peek-icon button anchored to that
   row/cell; the standalone Relationship cell and grouped-tree group nodes reveal
   **no** button.
2. **Operable by pointer.** Clicking the button opens a **pinned**
   `LinkedRecordPreviewCard` for that row's (or that cell's endpoint's) record.
3. **Operable by keyboard, and accessible.** The button appears on a row gaining
   keyboard focus/selection, is reachable by Tab, activates on Enter/Space, and
   exposes `accessibleName == "Preview <identifier>"` + tooltip *"Preview"*.
4. **Opens the same content as hover/Space.** The card opened by the button is
   byte-for-byte the card the 400 ms dwell / Space key opens for the same row —
   same header, title, always-available fields, enriched fields, and states.
5. **Accelerators intact.** The 400 ms hover-dwell still opens a transient card;
   Space still opens a pinned card; Esc dismisses; arrow-key selection re-targets
   a pinned card and repositions the button. None is removed or retimed.
6. **Consistent across all three surfaces.** The affordance behaves identically
   on the embedded references grid, the generalized Work-Task grid, and the
   standalone References panel (column-aware on the latter).
7. **Hides correctly.** The button hides after the 200 ms grace when the pointer
   leaves both row and button, on any reorder/regroup/refilter, on opening the
   context menu, and on scroll/column-resize that would move its row.
8. **Context menu / Go-to / Open / double-click unchanged.** The standalone row
   menu remains `["Go to source", "Go to target", "Delete reference"]`,
   whitespace `["New reference"]`; the grid menus and the `navigate_requested` /
   `open_requested` signals are unchanged — with the affordance installed.
9. **No model restructuring.** Revealing, clicking, or hiding the button calls no
   model mutator and no column-model change; `_COLUMNS` / `_WORK_TASK_COLUMNS` /
   `_ENTITY_FIELDS_COLUMNS`, the proxy column count, and the proxy→source mapping
   are identical before and after.

## 6. Verification

### 6.1 Manual (desktop)

- Open a heavily-linked record's embedded **References** section → hover a row,
  confirm the eye button appears immediately and click it opens the pinned card
  (AC-1/AC-2); confirm the 400 ms dwell card and Space still work (AC-5); Tab to
  the button and press Enter (AC-3); build a multi-sort and group, confirm the
  button tracks the right row and group nodes show no button (AC-6/AC-9); confirm
  scroll/resize and right-click hide it (AC-7/AC-8).
- Open a **Workstream**'s Work-Task grid and an **Entity**'s fields grid → same
  hover/click/keyboard checks (AC-6).
- Open the standalone **References** panel → hover Source vs. Target vs.
  Relationship cells, confirm the button on cols 0/2 only and that it previews the
  matching endpoint (AC-1/AC-6); confirm the row menu is unchanged and dismisses
  the button (AC-8).

### 6.2 Automated (pytest + offscreen Qt)

Following the existing offscreen-Qt convention (`qtbot.addWidget`, the
`client_stub` helper, reading `section._table`/`section._tree`/`panel._table`,
and `panel._build_context_menu` / `section._build_row_menu`). The implementing
Work Task adds:

- **`PreviewAffordance`** (widget-level): `show_at(...)` sets `accessibleName` to
  `"Preview <identifier>"`, the tooltip to *"Preview"*, and shows; the button is
  a focusable Icon-only `QPushButton` (AC-1/AC-3).
- **`PreviewController` reveal/hide** (logic-level, resolver+extractor injected):
  a `MouseMove` over a previewable row shows the affordance for the resolved
  index; a group-node / col-1 / invalid index hides it (AC-1); `Leave` + grace
  hides it; `dismiss()` hides it (AC-7); a `currentChanged` repositions it
  (AC-3).
- **Click opens the same card** (logic-level): `affordance.clicked` →
  `open_for_index(view, index, focusable=True)` opens a pinned card whose
  rendered header/fields equal the card opened by the existing Space path for the
  same index — asserting the affordance and the accelerators share one open path
  (AC-2/AC-4).
- **Accelerators-intact guard:** after the affordance is installed, a 400 ms-dwell
  `MouseMove` still opens a (non-focusable) card and `Space` still opens a
  focusable one (AC-5).
- **All-three-surfaces:** the affordance reveals on a `WorkTaskGridSection` row,
  an `EntityFieldsGridSection` row, an embedded `ReferencesSection` row, and a
  standalone-panel Source/Target cell, and not on a Relationship cell (AC-6).
- **Context-menu regression guard (extends `test_context_menus`):** with the
  affordance installed, `panel._build_context_menu(row_index)` still yields
  `["Go to source", "Go to target", "Delete reference"]`, the whitespace menu
  `["New reference"]`, and the grid `_build_row_menu` label sets are unchanged;
  `navigate_requested` / `open_requested` still fire from their existing triggers
  (AC-8).
- **No-mutation / no-column-change guard:** spy the model mutators (`set_records`,
  `beginResetModel`, the proxy `invalidate`/sort mutators) across a
  reveal→click→hide cycle and assert none is called; assert `columnCount`,
  each contract's column list, and the proxy→source mapping are unchanged (AC-9).

## 7. Deferred (non-goals, recorded for boundary clarity)

- **Always-visible-per-row icon and info-column** — rejected forms (§3.1); not
  built. If a future need for at-rest, scannable affordances on short lists
  emerges, the always-visible form is the lighter of the two to revisit.
- **A standing toolbar "Preview" button** — would not be row-targeted and adds a
  control to maintain; the row-anchored reveal button is the discoverable surface.
- **A side-peek docked inspector** — still the natural future surface for rich,
  always-on inspection (PI-118 §7); orthogonal to this discoverability work.
- **A one-time onboarding hint / coachmark** — a persistent or first-run textual
  hint ("hover a row to preview") was considered as a secondary aid; deferred as
  unnecessary once the always-immediate eye glyph is the cue. Recorded so the
  option is on the record if telemetry later shows the glyph alone is missed.
- **Editing from the affordance / preview** — the card stays a read-only
  inspector; mutation stays in the create/delete dialogs.
