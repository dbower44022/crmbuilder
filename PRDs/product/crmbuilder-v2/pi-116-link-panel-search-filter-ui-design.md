# PI-116 — In-Panel Search/Filter for Relationship (Link) Panels — UI Design

**Version:** 0.1
**Status:** Draft (design deliverable)
**Planning Item:** PI-116 — *Link panel in-panel search/filter for finding a specific linked record*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-059 (area: ui)
**Design input:** `styling-design-pass.md`

## 1. Overview

### Purpose

Specify the UI for an in-panel search/filter box on relationship (link) panels so
a user can type to narrow a long list of linked records down to the matches
*without scrolling*. This is the minimum scope settled at decomposition for PI-116:
a **debounced, client-side filter over the already-loaded link rows**. Server-side
relationship query filtering is an explicit non-goal here (§6).

### Background — what exists today

Two surfaces in the v2 desktop app render a record's relationships as link rows:

1. **`ReferencesSection`** — `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`.
   The per-record references grid embedded in every entity panel's detail pane. It
   already loads *all* of a record's references at once (via the panel's
   `fetch_detail_extras` worker → `StorageClient.list_references_touching`), flattens
   inbound + outbound into one `QTableView` over a `_RefsModel`/`QSortFilterProxyModel`,
   and **already has a filter box** (`self._filter`, objectName `references_section_filter`)
   whose `textChanged` drives `_on_filter_changed` → `QSortFilterProxyModel.setFilterFixedString`
   across every column (`setFilterKeyColumn(-1)`, case-insensitive). It has a native
   clear button (`setClearButtonEnabled(True)`) and re-sizes the table to the *filtered*
   row count via `_fit_height()`.

2. **`ReferencesPanel`** — `crmbuilder-v2/src/crmbuilder_v2/ui/panels/references.py`.
   The standalone all-references browser (`/references`). It caches the full list in
   `self._all_records` and filters with two `QComboBox` dropdowns (source-type,
   target-type) via `_on_filter_changed`. It has **no free-text filter**.

Neither surface has any paging or lazy-loading — both load the full set once and
render it (confirmed: no `limit`/`offset`/`page`/`load_more` in the panels or
`StorageClient`). No debounce / `QTimer`-based input throttle exists anywhere in the
v2 UI today (`QTimer` is used only for the API heartbeat and server-lifecycle polling).

### What this design changes

The gap PI-116 closes is narrow and precise:

- **`ReferencesSection`** is *95% there* — it filters immediately on every keystroke.
  This design (a) **debounces** that filtering, (b) adds an explicit **no-match empty
  state** (today an all-filtered table collapses to a 1-row-tall empty grid with no
  explanation), and (c) confirms the clear/reset contract.
- **`ReferencesPanel`** gains a free-text filter box alongside its existing dropdowns,
  built on the same debounced contract, because the standalone browser is the surface
  most exposed to "large numbers of links."

The two surfaces share one small reusable input widget (§4) so the debounce timing,
placement, clear control, and empty-state copy stay identical.

## 2. Scope

### In scope

1. A reusable debounced search/filter input widget for link panels.
2. Integrating it into `ReferencesSection` (replace the bare `QLineEdit` + immediate
   filter with the debounced widget) and into `ReferencesPanel` (add it next to the
   type dropdowns).
3. No-match empty state, clear/reset control, and the documented interaction with
   the (currently absent) paging/lazy-loading model.
4. Acceptance criteria and verification steps.

### Out of scope

- Server-side relationship query filtering (a possible future extension noted in
  PI-116; explicitly deferred — see §6).
- Introducing paging / lazy-loading / virtual scrolling. The filter operates over
  the loaded rows only; if a future Work Task adds paging, §5.5 states how the filter
  must compose with it.
- Changing the columns, sort behavior, navigation, or add/delete actions of either
  panel.

## 3. Behavior specification

### 3.1 Placement

- **`ReferencesSection`:** the filter input is the first widget below the "References"
  heading and above the `QTableView`, full panel width, exactly where the current
  `self._filter` `QLineEdit` already sits. Unchanged placement; only the widget behind
  it changes.
- **`ReferencesPanel`:** the filter input goes in the existing header filter row,
  to the **left of** the source-type / target-type combos, so free-text narrowing
  reads first and the structured dropdowns refine after. Width is constrained
  (see §4) so it does not crowd the combos — mirroring the constrained-width input
  convention already used in `CommitsPanel` (`self._sha_input.setMaximumWidth(180)`).
- Placeholder text: **`Filter links…`** (sentence case + ellipsis, matching the
  existing `Filter references…` idiom).

### 3.2 Debounce

- Filtering applies **`textChanged` → 250 ms debounce → apply**. The 250 ms value is
  the design default: long enough to coalesce a fast typist's keystrokes into one
  filter pass over the loaded rows, short enough to feel live. It is exposed as a
  module constant (`_FILTER_DEBOUNCE_MS = 250`) so it is tunable in one place.
- Mechanism: a single-shot `QTimer` (`setSingleShot(True)`) owned by the input widget.
  Each `textChanged` calls `timer.start(_FILTER_DEBOUNCE_MS)`, which *restarts* the
  pending timer; the timer's `timeout` emits a `filterChanged(str)` signal carrying
  the current text. The host panel connects `filterChanged` to its existing apply
  path (`setFilterFixedString` for `ReferencesSection`; the cached-list re-filter for
  `ReferencesPanel`). This is the first debounce in the v2 UI; the pattern is the
  standard Qt single-shot-restart idiom and is documented inline.
- **Clearing is immediate, not debounced** (§3.5): pressing the clear button or
  emptying the field restores the full list at once with no 250 ms lag.

### 3.3 Fields matched

- **`ReferencesSection`:** match across *every displayed column* — Direction,
  Relationship, Identifier, Type, **Title**, Status, Created, Updated — preserving the
  current `setFilterKeyColumn(-1)` all-column behavior. This is what lets a user type
  a partial **display title** (e.g. `postgres`) *or* a partial **identifier** (e.g.
  `PI-12`) and have it match. Matching is **case-insensitive** and **substring**
  (`setFilterCaseSensitivity(CaseInsensitive)` + `setFilterFixedString`), unchanged.
- **`ReferencesPanel`:** match the free text as a case-insensitive substring against
  the row's display fields — the source display (`{type}:{identifier}`), the
  relationship name, and the target display — so typing either endpoint's identifier
  or the relationship kind narrows the list. The free-text filter and the two
  dropdown filters compose with **AND**: a row is shown iff it satisfies the active
  dropdowns *and* contains the typed substring.
- Rationale for matching the rendered/display strings rather than raw keys: the user
  searches for what they can see on the row. Identifier (`PI-116`), display title, and
  the pretty relationship label are all on-screen, so all are matchable.

### 3.4 No-match empty state

- When the active filter yields **zero visible rows** (and the unfiltered list was
  non-empty), the panel shows a dim, centered empty-state line in place of / beneath
  the table: **`No links match "<query>".`** (the typed query echoed back, elided if
  long), styled with the existing dim-label treatment
  (`color: {t('color.neutral.500')}`, matching `ReferencesSection._dim_label`).
- The filter input itself **remains visible and focused** in the empty state so the
  user can edit or clear the query without re-locating it.
- The "no references at all" case (the record genuinely has none) is distinct and
  unchanged: those panels show `(none)` and never render the filter box (the filter
  only appears when there is something to filter). The no-match copy is therefore
  unambiguous — it can only mean "your filter excluded everything," never "this record
  has no links."

### 3.5 Clear / reset control

- The input keeps the native Qt clear affordance: `setClearButtonEnabled(True)` — the
  inline "✕" that appears once the field is non-empty (already used by
  `references_section_filter`).
- Clearing (the ✕, select-all-delete, or `Esc` while the field has focus and text)
  empties the field, **immediately** (bypassing debounce) re-applies an empty filter,
  restores the **full loaded list**, dismisses the no-match empty state, and re-runs
  `_fit_height()` so the table grows back to its full row count.
- `Esc` on an already-empty field is a no-op (does not steal the key from the panel).

### 3.6 Interaction with paging / lazy-loading

- There is **no paging or lazy-loading today**: both surfaces hold the entire row set
  in memory (`ReferencesSection._model` rows; `ReferencesPanel._all_records`). The
  filter is therefore complete and correct over the full set with no fetch.
- **Forward-compatibility rule (binding on any future paging Work Task):** because the
  filter is client-side over loaded rows, if a future change introduces server paging,
  the filter as specified here would silently narrow only the *loaded page* and read
  as a complete result — a correctness trap. So this design states the contract: a
  paging implementation must either (a) keep loading the full set for these link
  panels (filter stays complete), or (b) escalate the filter to a server-side query
  (the deferred §6 extension) and surface a "filtering loaded N of M — load all to
  filter everything" affordance. Until paging lands, neither is needed; this note
  exists so the client-side filter is not mistaken for a whole-relationship search.

## 4. Component design — `LinkFilterInput`

A small reusable widget so both surfaces share one debounce/clear/placeholder contract.

- **File:** `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/link_filter_input.py`
- **Class:** `LinkFilterInput(QWidget)` (thin composition over a `QLineEdit`), or, if
  the host already owns its `QLineEdit`, a `QObject` debounce helper
  `attach_debounced_filter(line_edit, on_filter, *, delay_ms=_FILTER_DEBOUNCE_MS) -> None`.
  The implementing Work Task may choose whichever fits the two call sites with the
  least code; the *contract* below is what is fixed.
- **Signal:** `filterChanged(str)` — emitted after the debounce settles, or
  immediately on clear/empty.
- **Configuration honored:**
  - `setPlaceholderText("Filter links…")`
  - `setClearButtonEnabled(True)`
  - `setObjectName(...)` per call site for testability — `references_section_filter`
    (preserve the existing name on the embedded grid) and a new
    `references_panel_filter` on the standalone panel.
  - Optional `setMaximumWidth(...)` for the standalone panel's header row
    (≈ `220px`), unset (full width) for the embedded grid.
- **Styling:** inherits the global input style from `styling.py` (text-input padding
  `space.1 space.2`, body font, focused-border treatment). No new tokens required.
- **Constant:** `_FILTER_DEBOUNCE_MS = 250` lives next to the widget.

This keeps the change minimal: `ReferencesSection` swaps its bare `QLineEdit` +
`_on_filter_changed` wiring for the debounced contract (its `_on_filter_changed`
body — `setFilterFixedString` + `_fit_height` — is unchanged, just driven by
`filterChanged` instead of `textChanged`); `ReferencesPanel` adds the input to its
header row and connects `filterChanged` to a small extension of its existing
`_on_filter_changed` cached-list re-filter.

## 5. Acceptance criteria

1. **Typing narrows without scrolling.** With a record/list of ≥ 20 link rows, typing
   a substring that matches a subset reduces the visible rows to exactly the matching
   set; in `ReferencesSection` the table re-fits to the filtered count so no scroll is
   needed to see all matches.
2. **Matches title and key.** Typing a partial display **title** matches; typing a
   partial **identifier** matches; both are case-insensitive substring matches.
3. **Debounce.** Rapid typing of N characters applies the filter **once**, ~250 ms
   after the last keystroke — not once per character.
4. **No-match empty state.** A query matching nothing shows `No links match "<query>".`
   in the dim empty-state style, with the filter input still visible and focused; the
   "record has no links at all" case still shows `(none)` and renders no filter box.
5. **Clear restores the full list.** Pressing the ✕ clear button (or emptying the
   field, or `Esc`) immediately restores every loaded row, dismisses the empty state,
   and re-fits the table — with no debounce delay.
6. **Composes with existing dropdowns (standalone panel).** On `ReferencesPanel`, the
   free-text filter and the source/target-type combos combine with AND; changing a
   dropdown re-applies against the current text and vice-versa.
7. **No regression to navigation / sort / add-delete.** Double-click navigation,
   header-click sorting, and the add/delete reference actions behave exactly as before
   on the filtered view (operating on the row under the cursor, mapped through the
   proxy).

## 6. Deferred — server-side relationship query (non-goal for PI-116)

Filtering the relationship *on the server* (so a record with thousands of links never
ships them all to the client) is the natural follow-on and is explicitly **out of
scope** here, consistent with PI-116's "client-side filter over loaded rows is the
minimum." It would require `StorageClient.list_references_touching` /
`list_references` to accept a query + `limit`/`offset`, a debounced *fetch* (not just
a proxy re-filter) on a worker thread, and the "load all to filter everything"
affordance described in §3.6(b). Recorded here so the boundary is unambiguous; it
belongs to a separate Work Task if PRJ-016 chooses to pursue it.

## 7. Verification (manual + automated)

- **Manual (desktop):** open an entity with many references (e.g. a heavily-linked
  topic or planning item) → confirm AC-1 through AC-5 against the embedded grid; open
  the standalone References panel → confirm AC-1..AC-6 there.
- **Automated (pytest + offscreen Qt):** the implementing Work Task adds widget tests
  asserting (a) `filterChanged` fires once after a burst of `setText` calls within the
  debounce window — driven by advancing/forcing the single-shot timer, (b) a matching
  query reduces `proxy.rowCount()` to the expected subset, (c) a non-matching query
  produces `rowCount() == 0` and the empty-state label is visible, (d) clearing
  restores the original `rowCount()` and hides the empty state. Tests follow the
  existing offscreen-Qt widget-test convention used for the v2 UI widgets.
