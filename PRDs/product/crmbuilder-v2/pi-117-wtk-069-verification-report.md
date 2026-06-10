# PI-117 / WTK-069 — Verification Report

**Verifier Work Task:** WTK-069 (area: ui)
**Under test:** WTK-068 build (commit `458d3fa`) of the PI-117 delta
**Against:** WTK-067 Design spec (`pi-117-link-panel-multicolumn-sort-grouping-ui-design.md` v0.1) §5 acceptance criteria
**Scope:** the three delta behaviors only — multi-column sort, grouping, standalone-panel sort. The PI-116 single-column click-header foundation was **not** re-verified (already shipped/verified, per the Work Task).
**Method:** source read of the five WTK-068 files against the spec; execution of the build's own 40 automated tests; one independent verification suite (2 tests) authored to close an untested spec path.

## Verdict

**9 of 10 acceptance criteria PASS. AC-4 is PASS-WITH-DEFECT** — the functional sort-clearing capability is present and tested, but the spec's user-facing **"Clear sort" header context-menu affordance is not implemented** (DEF-1, minor). No other deviations found. The three delta behaviors are correctly built and composed; ordering is stable and deterministic; grouping composes with both multi-sort and the PI-116 filter; the previously list-only standalone panel gains sort + grouping.

## Evidence base

- Build suite (re-run, green): 40 passed —
  `test_multi_sort_proxy.py` (12), `test_grouping_tree_model.py` (8),
  `test_multi_sort_header.py` (5), `test_references_section_sort_group.py` (8),
  `test_references_panel_sort_group.py` (8).
- Independent verifier suite (new, green): 2 passed —
  `test_references_section_group_by_day_wtk069.py` (closes the untested
  *Created (by day)* bucketing + group-ordering path, §3.5 / §3.7-2).

## Acceptance criteria

### AC-1 — Single-column sort preserved · PASS
`MultiSortProxyModel.set_primary` replaces the key list with one key and toggles
asc→desc on a repeat plain-click (`multi_sort_proxy.py:53`); `sort(col, order)`
collapses to a single key, preserving `sortByColumn`/plain-header semantics
(`:96`). `ReferencesSection._build` establishes the deterministic default via
`self._proxy.clear_sort()` → `[(0, Ascending)]` (`references_section.py:349`), so
the initial render is column-0 ascending as before.
Evidence: `test_set_primary_single_key`, `test_set_primary_toggles_direction`,
`test_sortbycolumn_collapses_to_single_key`, `test_clear_sort_returns_default`.

### AC-2 — Multi-column sort, stable · PASS
`lessThan` walks `_sort_keys` in precedence order, returning on the first unequal
column honoring that key's direction, and falls back to the **source row index**
as a stable tiebreaker (`multi_sort_proxy.py:120-145`). *Type then Created*
ordering and the stable tiebreaker are asserted directly.
Evidence: `test_multi_column_type_then_date`,
`test_stable_tiebreaker_preserves_source_order`.

### AC-3 — Per-column indicator · PASS
`MultiSortHeaderView.indicator_for` returns `(rank, order)` from the proxy's
`sort_keys()`; `paintSection` overlays a right-aligned `▲<rank>` / `▼<rank>`
glyph for active columns and nothing for inactive ones
(`multi_sort_header.py:56-70, 116-132`). The header subscribes to
`sortKeysChanged` and repaints live (`:50-54, 111-114`).
Evidence: `test_indicator_reflects_sort_keys`, `test_indicator_updates_on_clear`,
`test_sort_keys_changed_drives_indicator_refresh`.

### AC-4 — Add / clear precedence · **PASS-WITH-DEFECT (DEF-1)**
- **Met:** `cycle_secondary` appends ascending then cycles asc→desc→removed
  (`multi_sort_proxy.py:68-85`); a plain click resets to a single ascending key
  (`set_primary`); `clear_sort()` returns `[(0, Ascending)]`.
  Evidence: `test_cycle_secondary_asc_desc_remove`,
  `test_set_primary_collapses_to_one_key`, `test_clear_sort_returns_default`.
- **Defect:** §3.1 specifies *"Clear sort: a header context-menu item 'Clear
  sort' resets to the default"*, and AC-4 lists *"'Clear sort' returns to the
  column-0 default"* as a criterion. The `clear_sort()` proxy method exists and
  is called once at build to set the default, **but no user-facing affordance
  invokes it** — `MultiSortHeaderView` sets no `ContextMenuPolicy` and neither
  surface adds a "Clear sort" menu item (grep for `"Clear sort"` over
  `src/` and `tests/` returns nothing). A user who has built a multi-key sort
  can only modifier-cycle each key off one at a time or plain-click a column;
  there is no one-action reset. See DEF-1 below.

### AC-5 — Grouping collapses rows · PASS
Selecting a Group-by value builds a `GroupingTreeModel` and swaps the
`QStackedWidget` to the tree; `(none)` rebuilds nothing and restores the exact
flat table (`references_section.py:529-544`). Group nodes render
`"<value> (<n>)"` (`grouping_tree_model.py:87-90`).
Evidence: `test_group_by_swaps_to_tree_and_restores_table`,
`test_group_nodes_show_value_and_count`; verifier
`test_created_buckets_by_day_not_timestamp` confirms the *Created (by day)*
option buckets on the `YYYY-MM-DD` prefix (`references_section.py:518-527`),
the one group path the build suite left uncovered.

### AC-6 — Collapse/expand · PASS
Groups start expanded (`_rebuild_tree` → `self._tree.expandAll()`,
`references_section.py:562`); Expand all / Collapse all links toggle every group
(`:570-576`); `_fit_height` resizes to the visible-node count via
`_visible_tree_rows` so the outer scroll handles overflow with no nested
scrollbar (`:407-445`), recomputed on every expand/collapse signal (`:578-579`).
Evidence: `test_expand_collapse_all_changes_visible_rows`.

### AC-7 — Grouping composes with multi-sort · PASS
The tree is fed `_ordered_rows()` read from the proxy in sorted order; the model
buckets *preserving arrival order within a group* (so the multi-sort holds inside
groups) and orders group nodes by key with `(none)` last
(`grouping_tree_model.py:185-197`). A sort change while grouped rebuilds the tree
live (`references_section.py:546-551`).
Evidence: `test_grouping_composes_with_multi_sort_within_group`,
`test_sort_change_while_grouped_reorders_children`, `test_none_group_sorts_last`;
verifier `test_created_by_day_groups_ordered_with_none_last`.

### AC-8 — Composes with the PI-116 filter · PASS
`MultiSortProxyModel` inherits `filterAcceptsRow`, so `setFilterFixedString` /
`setFilterKeyColumn(-1)` / case-insensitive filtering survive unchanged
(`references_section.py:324-325, 447-448`). When grouped, the tree is rebuilt
from the proxy's *filtered+sorted* rows; a filter excluding every row shows the
no-match empty state with zero group nodes and hides the stack
(`:454-469`).
Evidence: `test_filter_excluding_all_shows_empty_state_no_groups`,
`test_filter_inherited_from_base`.

### AC-9 — Standalone panel parity · PASS
`ReferencesPanel` inserts a `MultiSortProxyModel` between the base
`_RecordTableModel` and the master view with case-insensitive sort, installs a
`MultiSortHeaderView` (gaining single- AND multi-column header sort it lacked),
and appends a Group-by combo (Source type / Relationship / Target type)
(`panels/references.py:98-113, 192-210`). Grouping rebuilds from the
already-filtered records (`_ordered_visible_records` over `_apply_filter`), so it
composes with the source/target dropdowns and free-text filter via AND
(`:294-313, 463-513`).
Evidence: `test_header_click_sorts_previously_unsorted_list`,
`test_modifier_click_builds_two_key_order`,
`test_grouping_composes_with_source_dropdown`,
`test_grouping_composes_with_free_text_filter`.

### AC-10 — No regression to navigation / add-delete · PASS
Both surfaces resolve a row from whichever view emitted the index:
`ReferencesSection._row_at` maps tree indices through
`GroupingTreeModel.row_dict` (group nodes → `None`) and table indices proxy→
source (`references_section.py:608-622`); `ReferencesPanel._record_at_index`
covers grouped-tree, proxy, and raw source indices (`panels/references.py:348-367`).
Double-click (section) / single-click (panel) navigation, the right-click menu,
and add/delete therefore act on the correct underlying edge whether the table or
the grouped tree is visible.
Evidence: `test_navigation_from_grouped_row_emits`,
`test_double_click_group_node_does_not_navigate`,
`test_click_navigation_from_grouped_row`,
`test_existing_source_index_click_still_navigates`.

## Defects

### DEF-1 — "Clear sort" header context-menu affordance not implemented (minor)
- **Spec:** §3.1 (*"a header context-menu item 'Clear sort' resets to the
  default (single key on column 0, ascending)"*) and AC-4.
- **Observed:** `clear_sort()` exists on `MultiSortProxyModel` and is unit-tested,
  but it is invoked only once internally (`references_section.py:349`) to set the
  build-time default. No `ContextMenuPolicy` is set on `MultiSortHeaderView` and
  no "Clear sort" `QMenu` item exists on either surface (confirmed by grep).
- **Impact:** functional capability is present; only the user-facing one-action
  reset is missing. A user can still reach the default by plain-clicking column 0
  or cycling keys off individually, so this is a usability/affordance gap, not a
  correctness defect.
- **Remediation (for the build owner, not done here):** add a header
  `CustomContextMenu` (or reuse the table's context-menu path when the click is
  over the header) offering "Clear sort" → `proxy.clear_sort()` on both
  `ReferencesSection` and `ReferencesPanel`, plus a test asserting the menu item
  resets `sort_keys()` to `[(0, Ascending)]`.

## Notes (not defects)
- The standalone `ReferencesPanel` applies no build-time default sort key
  (`_sort_keys` starts empty → fetched order), preserving PI-116's list-only
  initial ordering. This is consistent with the spec (the panel had no sort
  before; AC-9 requires only that it *gains* header-click sort) and §4.3's
  "deterministic default" wording binds the section, whose default is column-0
  ascending. No action needed.
- *Created (by day)* group ordering relies on `YYYY-MM-DD` string order equalling
  chronological order; correct for the ISO prefixes the access layer emits
  (verified).
