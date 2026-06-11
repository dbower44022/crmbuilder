# PI-119 — Link Panel Resizable (Drag-Resize) Columns — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-119 — *Resizable columns in link panels*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-072 (area: ui) / Workstream WSK-054 (Design)
**Builds on:** PI-116 (`pi-116-link-panel-search-filter-ui-design.md`) — debounced filter; PI-117 (`pi-117-link-panel-multicolumn-sort-grouping-ui-design.md`) — `MultiSortProxyModel` + `GroupingTreeModel` + `MultiSortHeaderView`; PI-118 (`pi-118-link-panel-inline-preview-ui-design.md`) — inline preview. All shipped.

## 1. Overview

### Purpose

Let a user **resize the columns of the relationship (link) panel by dragging
the column borders**, so wide values (long titles, full identifiers) are
readable and the panel adapts to the link content a given object carries. This
is the PI-119 enhancement Doug requested alongside the PRJ-016 candidate set; it
complements PI-117's sortable/groupable columns.

The change is **additive and minimal**: it flips one resize-mode setting on the
embedded link grid's header and seeds sensible initial widths. It must
**preserve sort, grouping, filter, and the PI-118 preview**, and it must **not
regress `test_context_menus`**.

### The scoping fact that makes this a real PI

The embedded link grid (`references_section.py`) currently sets its header to
`QHeaderView.ResizeMode.ResizeToContents` with column 4 (*Title*) on `Stretch`
(`references_section.py:354–356`). `ResizeToContents` **auto-sizes every column
and blocks user drag-resize** — a `ResizeToContents` section ignores
`resizeSection()` and shows no draggable divider grip. So the PI is *not* already
satisfied: enabling drag-resize means switching the resize mode to
`Interactive`.

### The asymmetry this design resolves

The two link surfaces are **inconsistent today**:

- **Embedded** `ReferencesSection`
  (`crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`) — flat
  `QTableView` header is `ResizeToContents` + col 4 `Stretch` ⇒ **not
  resizable** (`references_section.py:354–356`). Its grouped `QTreeView` header
  is also `ResizeToContents` + col 4 `Stretch` (`references_section.py:612–617`,
  re-applied on every `_rebuild_tree`).
- **Standalone** `ReferencesPanel`
  (`crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py`) — flat
  `QTableView` header uses Qt's **default `Interactive` mode** plus
  `setStretchLastSection(True)` (`references.py:103–104`) ⇒ **already
  user-resizable**. Its grouped `QTreeView` header is `ResizeToContents` +
  `setStretchLastSection(True)` (`references.py:516–519`).

So the standalone panel already ships exactly the behavior PI-119 wants
(interactive flat columns, auto-fit grouped tree). **This design brings the
embedded `ReferencesSection` into line with that existing precedent** rather
than inventing a new pattern.

### What this design changes (the delta)

1. Flat-table header in `ReferencesSection`: `ResizeToContents` → `Interactive`,
   keeping col 4 (*Title*) on `Stretch`; seed one-time content widths (§3.1).
2. A minimum section size so a column cannot be dragged to zero / clipped under
   the sort glyph (§3.2).
3. A settled decision to **leave the grouped tree on `ResizeToContents`** (§3.4)
   and to **defer per-user/per-panel width persistence** (§3.5).
4. Verification: drag-resize works, sort/group/filter/preview preserved,
   `test_context_menus` green (§5–6).

No change to `MultiSortHeaderView`, `MultiSortProxyModel`, `GroupingTreeModel`,
or the standalone `ReferencesPanel` is required (§3.3, §4).

## 2. Constraints (hard)

- **C1 — preserve multi-key sort.** Header clicks must still route to
  `MultiSortProxyModel.set_primary` / `cycle_secondary` via
  `MultiSortHeaderView`, and the `▲1`/`▼2` precedence glyph must still paint.
- **C2 — preserve grouping.** The group-by combo, the `QStackedWidget`
  table↔tree switch, and `_rebuild_tree` behavior are unchanged.
- **C3 — preserve filter.** The PI-116 debounced `LinkFilterInput` →
  `setFilterFixedString` path and the no-match empty state are unchanged.
- **C4 — preserve preview.** The PI-118 `PreviewController` resolves rows through
  `_row_at` independent of column width; resizing a column must not dismiss or
  break the hover/keyboard card.
- **C5 — `test_context_menus` byte-identical.** The right-click menu labels and
  build paths are untouched.
- **C6 — height-fit intact.** `_fit_height` sizes the table/tree to row count;
  it reads `horizontalHeader().sizeHint().height()`, which is width-independent,
  so it is unaffected by column resizing.

## 3. Design decisions

### 3.1 Flat table → `Interactive`, col 4 stays `Stretch`, seed from content

Replace the two lines at `references_section.py:354–356`:

```python
# before
table_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
# Title column takes the slack so long titles are readable.
table_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
```

```python
# after
table_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
# Title column absorbs the slack so long titles stay readable, and so the
# grid always fills the viewport width (no trailing empty gutter).
table_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
table_header.setMinimumSectionSize(_MIN_SECTION_WIDTH)  # see §3.2
# One-time content-fit seed: Interactive columns otherwise start at the
# generic defaultSectionSize. Runs after the model + view are wired so the
# metrics are real; the Stretch column (4) ignores this and keeps stretching.
self._table.resizeColumnsToContents()
```

**Why `Interactive` + one `Stretch` column (rather than all-`Interactive`):**

- `Interactive` is the only mode whose sections expose a draggable divider grip
  and honor `resizeSection()` — it is what "drag-resize" *means* in Qt.
- Keeping exactly one `Stretch` column (col 4, *Title*) preserves today's intent
  ("Title column takes the slack so long titles are readable") and guarantees
  the row of columns always fills the viewport with no trailing empty gutter.
  Dragging any `Interactive` column trades its width against the `Stretch`
  column, which is the natural mental model. This mirrors the standalone panel,
  which keeps its last column stretched (`setStretchLastSection(True)`).
- *Title* is the right column to stretch: it is the free-text column with the
  widest and most variable content; the others (*Direction, Relationship,
  Identifier, Type, Status, Created, Updated*) are short and bounded, so a
  one-time content fit gives each a tight, sensible starting width.

**Why `resizeColumnsToContents()` for the seed (rather than hard-coded px):**
it reuses Qt's own content metrics — the same computation `ResizeToContents`
was doing — but **once**, leaving the columns `Interactive` and therefore
draggable thereafter. `QTableView.resizeColumnsToContents()` is the idiomatic
QTableView call for this; it is a no-op on the `Stretch` column (col 4 cannot be
manually sized). It is placed after the model is set and the view is in the
layout so the font/content metrics are real.

> **Offscreen-metrics note.** Under `QT_QPA_PLATFORM=offscreen` (the test
> environment) content-width metrics are computed but may be conservative.
> That does not break the feature — columns are still `Interactive` and
> draggable; only the *seed* width may be tighter than on a real display. The
> verification (§5) asserts **mode and drag behavior**, not exact seeded pixel
> values, so it is robust offscreen. If a future tester wants deterministic
> seed widths independent of platform metrics, the fallback is an explicit
> `_SEED_WIDTHS: dict[int, int]` applied with `header.resizeSection(col, px)`
> for the non-stretch columns; this design does **not** adopt it now (extra
> constant + maintenance for no functional gain), but records it as the escape
> hatch.

### 3.2 Minimum section size

Add a module constant and apply it (shown in §3.1):

```python
# Floor for a draggable column so it cannot be hidden by an over-drag and so
# the right-aligned sort glyph (MultiSortHeaderView paints "▲1"/"▼2") is not
# clipped against the header label.
_MIN_SECTION_WIDTH = 48
```

`setMinimumSectionSize` bounds *all* interactive drags. Rationale: a user can
otherwise drag a column to 0 px, which (a) hides the column entirely with no
affordance to recover it (this widget has no header context menu to restore
columns), and (b) clips `MultiSortHeaderView`'s precedence glyph, which is
right-aligned with a 6 px margin (`multi_sort_header.py:_GLYPH_MARGIN`). 48 px
keeps the divider grabbable and leaves room for the glyph. (`48` is a starting
value; it is cosmetic and may be tuned without design rework.)

### 3.3 Cooperation with `MultiSortHeaderView` — no change needed

`MultiSortHeaderView` (PI-117) is a `QHeaderView` subclass that is installed via
`setHorizontalHeader(table_header)` *before* the resize mode is set (order in
`_build` is unchanged). Enabling `Interactive` resize is **orthogonal** to its
two responsibilities:

- **Click routing (sort).** Qt fires `sectionClicked` only for a press+release
  on the **section body**; a press that lands on the **section divider grip**
  starts a resize drag and **does not** emit `sectionClicked`. So
  `MultiSortHeaderView._on_section_clicked` → `_route_click` →
  `set_primary` / `cycle_secondary` continues to fire for clicks and stays
  silent for drags. `setSectionsClickable(True)` (set in the subclass ctor) and
  `Interactive` resize coexist by design — exactly as they already do on the
  standalone panel's interactive header.
- **Glyph painting.** `paintSection` right-aligns the `▲rank`/`▼rank` glyph
  inside the section `rect`; it is width-independent and repaints on
  `sortKeysChanged`. The only width interaction is clipping at very small
  widths, handled by the §3.2 minimum.

No edit to `multi_sort_header.py`. This is the crux of "without regressing
sort": the resize capability lives entirely in the base `QHeaderView`
resize-mode machinery the subclass inherits and does not override.

### 3.4 Grouped tree header stays `ResizeToContents` (settled)

**Decision: leave the grouped `QTreeView` header on `ResizeToContents` + col 4
`Stretch` (`references_section.py:612–617`) — out of scope for this iteration.**

Rationale:

- **Precedent.** The standalone `ReferencesPanel` already pairs an *interactive*
  flat table with a *`ResizeToContents`* grouped tree (`references.py:516–519`).
  Matching that keeps the two surfaces consistent.
- **Frequent rebuild.** `_rebuild_tree` runs on every regroup, in-group re-sort,
  and refilter (`references_section.py:601–617`) and re-applies the header modes
  each time. Making the tree `Interactive` would either (a) reset the user's
  drags on every rebuild — worse than auto-fit — or (b) require a
  width-persistence mechanism to survive rebuilds, which is precisely the
  deferred extension in §3.5. Auto-fit is the *correct* behavior for a transient
  grouped scan, where the goal is bucket overview, not column tuning.
- **Scope discipline.** This PI's user-visible ask is "drag the borders of the
  link panel." The flat table is the default, always-present view; the grouped
  tree is opt-in. Delivering resize on the flat table satisfies the ask with one
  line changed and zero new state.

If/when width persistence (§3.5) lands, the grouped tree can adopt `Interactive`
under the same width store in the same pass — recorded as the natural follow-on.

### 3.5 Per-user / per-panel width persistence — DEFERRED (settled)

**Decision: defer persistence; PI-119 ships resize-enablement only.** The PI
description and PI-119's executive summary both flag persistence as "a possible
extension to settle at decomposition" — this design settles it as **out of
scope** for the resize iteration.

Rationale:

- **No store exists in these widgets.** `ReferencesSection` is **rebuilt from
  scratch on each detail load** (the constructor calls `_build`), and it holds
  no `QSettings`/preferences handle. Persistence needs (1) a durable store and
  (2) a stable per-panel key, neither of which is present.
- **Keying is non-trivial.** "Per-panel" is ambiguous: the same
  `ReferencesSection` class renders the link panel of *every* entity type and
  every record. A useful key is per-*entity-type* (so widths learned on
  Decisions persist across Decision records) — a small design question that
  deserves its own decomposition, not a smuggled-in default.
- **Value is incremental.** Seeding sensible content widths (§3.1) delivers most
  of the readability benefit immediately; persistence is a refinement.

**Future extension path (documented, not built):** on a stable per-(entity-type)
key, save `table_header.saveState()` on `sectionResized` (debounced) into
`QSettings`, and `restoreState()` after the §3.1 seed in `_build`. `saveState()`
captures per-section widths and order in one opaque blob; restoring *after* the
content seed means a first-time user gets content-fit widths and a returning
user gets their own. The grouped tree (§3.4) would join the same store.

### 3.6 Preview, filter, height — untouched (confirmed)

- **Preview (C4).** `PreviewController` anchors to a row resolved via `_row_at`,
  which is column-width-independent; resizing changes geometry only. No
  dismiss-on-resize is wired (resize is not a reorder/regroup/refilter), which
  is correct — the card should follow its row, not vanish, while a user widens a
  column.
- **Filter (C3).** Unaffected; filtering changes row count, not column mode.
- **Height (C6).** `_fit_height` reads `horizontalHeader().sizeHint().height()`
  (vertical metric); column widths do not enter it.

## 4. Files touched

| File | Change | Why |
|---|---|---|
| `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` | Flat-table header `ResizeToContents` → `Interactive` (keep col 4 `Stretch`); add `_MIN_SECTION_WIDTH` const + `setMinimumSectionSize`; one-time `resizeColumnsToContents()` seed (§3.1–3.2). Grouped tree unchanged (§3.4). | Enable drag-resize on the embedded link grid. |
| `tests/crmbuilder_v2/ui/widgets/test_references_section.py` *(or sibling)* | New test(s): header mode is `Interactive` for non-Title columns, `Stretch` for col 4; `resizeSection` takes effect; sort routing + grouping + filter still work (§5). | Verify the feature and guard the constraints. |

No change to `multi_sort_header.py`, `multi_sort_proxy.py`,
`grouping_tree_model.py`, `linked_record_preview.py`, or `panels/references.py`.

## 5. Verification approach

Offscreen Qt (`QT_QPA_PLATFORM=offscreen`), the established pattern for these
widget tests. Build a `ReferencesSection` over a small fixed payload (the
existing test fixtures for this widget), then assert:

1. **Drag-resize is enabled (the feature).**
   - For each non-Title column `c` in `0,1,2,3,5,6,7`:
     `table.horizontalHeader().sectionResizeMode(c) == QHeaderView.ResizeMode.Interactive`.
   - `table.horizontalHeader().sectionResizeMode(4) == QHeaderView.ResizeMode.Stretch`.
   - **Behavioral proof** (the decisive check, since a `ResizeToContents`
     section silently ignores manual resize): `header.resizeSection(0, 200)` then
     `header.sectionSize(0) == 200`. This passes only when the section is
     `Interactive`.
   - `header.minimumSectionSize() == _MIN_SECTION_WIDTH`.
2. **Sort preserved (C1).** Drive `header._route_click(2, NoModifier)` (the
   tests'-exposed routing entry) and assert the proxy's `sort_keys()` reflects
   the new primary, and `header.indicator_for(2)` returns a `(rank, order)` — i.e.
   header clicks still sort and the glyph still resolves with resize enabled.
3. **Grouping preserved (C2).** Set the group combo to a grouped option; assert
   the stack switches to the tree and `_rebuild_tree` produces the grouped model
   (existing grouping assertions), confirming resize-enablement did not perturb
   the table↔tree path.
4. **Filter preserved (C3).** Apply a filter string via `_on_filter_changed`;
   assert proxy row count drops and the empty state behaves (existing filter
   assertions).
5. **Preview preserved (C4).** Reuse the existing preview composition test
   (`test_linked_record_preview.py`) unchanged — it must stay green.
6. **Context menus not regressed (C5).** Run
   `tests/crmbuilder_v2/ui/test_context_menus.py` unchanged — must stay green
   (no menu code touched).

**Commands the build session runs:**

```bash
cd crmbuilder-v2
QT_QPA_PLATFORM=offscreen uv run pytest \
  tests/crmbuilder_v2/ui/widgets/test_references_section.py \
  tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py \
  tests/crmbuilder_v2/ui/test_context_menus.py -q
uv run ruff check src/crmbuilder_v2/ui/widgets/references_section.py
```

## 6. Acceptance criteria

- **AC1** — In the embedded link panel the user can drag any non-Title column
  border to a new width; the *Title* column absorbs/yields the slack and the
  grid fills the viewport with no trailing gutter.
- **AC2** — Initial widths are content-seeded (short columns tight, *Title*
  wide), not the generic `defaultSectionSize`.
- **AC3** — A column cannot be dragged below `_MIN_SECTION_WIDTH`; the sort
  glyph is never clipped.
- **AC4** — Header clicks still set/cycle multi-key sort and paint the
  precedence glyph (no sort regression).
- **AC5** — Grouping, filtering, and the inline preview behave exactly as before.
- **AC6** — `test_context_menus` and `test_linked_record_preview` pass unchanged.
- **AC7** — Grouped-tree auto-fit and per-user width persistence are recorded as
  deliberate out-of-scope decisions (§3.4, §3.5) with a documented extension
  path, not silent omissions.

## 7. Decisions log (for governance capture at build close)

- **D1** — Embedded flat-table header: `ResizeToContents` → `Interactive`, col 4
  *Title* stays `Stretch`; brings it in line with the already-interactive
  standalone panel (§3.1).
- **D2** — Seed initial widths once via `resizeColumnsToContents()` after model
  wiring; do not hard-code pixel widths (§3.1).
- **D3** — `setMinimumSectionSize(48)` to protect recoverability and the sort
  glyph (§3.2).
- **D4** — Grouped `QTreeView` header **stays `ResizeToContents`** this iteration
  (frequent rebuild + standalone-panel precedent) (§3.4).
- **D5** — Per-user/per-panel width persistence **deferred**; future path =
  `QSettings` + `header.saveState()/restoreState()` keyed per entity-type
  (§3.5).
