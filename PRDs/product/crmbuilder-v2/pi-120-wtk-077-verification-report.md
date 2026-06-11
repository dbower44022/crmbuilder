# PI-120 / WTK-077 — Verification Report

**Verifier Work Task:** WTK-077 (area: ui)
**Under test:** WTK-076 build (commit `5c8299c`) of the PI-120 delta
**Against:** WTK-075 Design spec (`pi-120-workstream-panel-work-task-grid-ui-design.md` v0.1) §6 acceptance criteria
**Scope:** the Workstream-panel child Work Tasks grid — `GridContract` seam in the shared grid (References contract as the unchanged default), `WorkTaskGridSection`, and `workstreams.py`'s `fetch_detail_extras`/`_work_tasks_section` join. The References-grid usages and the PI-116/117/118/119 foundations are re-exercised as regression guards.
**Method:** source read of the WTK-076 production diff against the spec; execution of the build's own panel + widget suites plus the spec-named regression suites; a new widget suite closing the §5.4 grid-feature-stack gap; ruff on the touched files. This phase writes **no production code** — only a new test module and this report.

## Verdict

**All 8 acceptance criteria PASS.** No deviations from the design found. The Workstream detail pane's *Work Tasks* section is an inline grid: one row per child Work Task showing identifier, title, area, status, and a derived claim-state string. Area and claim state — absent from the edge summary — are sourced from the fetched Work Task records on the `fetch_detail_extras` worker thread, with graceful degradation to identifier-only rows when a record is missing. The grid is the *same* grid the References panel uses (one implementation, two `GridContract` configurations — no fork): the PI-116 debounced filter, PI-117 multi-column sort + grouping, PI-118 inline preview, and PI-119 drag-resize all function for Work Task rows. The References default contract is byte-for-byte today's behavior; the 25 existing usages, `test_context_menus`, `test_references_section*`, and `test_linked_record_preview` are unchanged and green. The grid is read-only (navigable, no Add/Delete). The empty case preserves `"No Work Tasks recorded."` The full-extract `RecordGridSection` rename (§3.7) and the sixth *Claimed at* column (§3.4) are recorded as deliberate out-of-scope decisions.

## Evidence base

All commands run from repo root. `QT_QPA_PLATFORM=offscreen`, the established widget-test pattern. The design's §5 `cd crmbuilder-v2` prefix is needed only so `uv` resolves the project venv; the suite paths are repo-root `../tests/...`.

- WTK-076 build suites (re-run, green): `test_workstreams_panel.py`,
  `test_references_section.py` (incl. the WTK-076 GridContract guards).
- Regression suites named by the design §5 (re-run, green):
  `test_references_section_sort_group.py`,
  `test_references_section_resize_wtk073.py`,
  `test_linked_record_preview.py`, `test_context_menus.py`.
- New WTK-077 suite (closes §5.4 / AC3): **9 passed** —
  `test_work_task_grid_wtk077.py` (filter, sort routing, grouping into the
  tree with the contract's own Area/Status/Claim-state options, preview
  extractor, Interactive header + Title Stretch + min-section floor).
- Combined spec run: **112 passed in 3.32s**, zero failures.
- Wider grid-machinery sweep (`test_grouping_tree_model`, `test_link_filter_input`,
  `test_multi_sort_header`, `test_multi_sort_proxy`,
  `test_references_section_group_by_day_wtk069`): **33 passed**.
- `ruff check tests/.../test_work_task_grid_wtk077.py
  src/crmbuilder_v2/ui/widgets/references_section.py
  src/crmbuilder_v2/ui/panels/workstreams.py` — **All checks passed!**

## Source confirmation (the delta)

**`GridContract` seam — `references_section.py:210–272`.** Confirmed a frozen
dataclass naming the eight references-specific seams (columns, datetime_keys,
group_options, stretch_column, heading, empty_text, preview_subtitle_key,
show_add_button, row_menu). `_REFERENCES_CONTRACT` is the built-in default;
`ReferencesSection.__init__` selects `contract or _REFERENCES_CONTRACT`
(`:399`), so every existing call site (no contract argument) is unchanged.
`_RefsModel` (`:308–367`), `_cell_display` (`:764–776`), `_rebuild_tree`
(`:778–794`), `_group_field`/`_group_value` (`:719–739`), the preview extractor
(`:593–599`), and the add-button guard (`:811–813`) all read `self._contract`.
This is exactly the §3.1–§3.2 design — one implementation, two configurations.

**`WorkTaskGridSection` — `references_section.py:944–973`.** Confirmed a thin
subclass (not a copy) that calls `super().__init__(..., contract=_WORK_TASK_CONTRACT,
rows=rows)` — no references `_flatten`, no edge writes. The Work Task contract
(`:262–272`) supplies the five-column model, empty `datetime_keys`, Area/Status/
Claim-state group options, `stretch_column=1` (Title), `show_add_button=False`,
and the read-only `_work_task_row_menu` (Go to + Copy identifier, no Delete).

**`workstreams.py` integration.** `fetch_detail_extras` (`:107–118`) loads
`child_work_tasks` via `_load_child_work_tasks` (`:120–152`): the child set is
the inbound `work_task_belongs_to_workstream` edges (membership source of truth),
joined to `list_work_tasks()` records by identifier, on the worker thread, with a
`try/except` degrading to `{"work_task_identifier": cid}` on a fetch failure
(§3.3). `_work_tasks_section` (`:256–279`) builds five-field rows via
`_work_task_row` (`:281–304`) — claim state derived as `"Claimed · {who}"` /
`"Unclaimed"` only when the record was loaded — returns `WorkTaskGridSection`
with `set_add_enabled(False)` + `navigate_requested` wired, and preserves the
`"No Work Tasks recorded."` dim label for the empty case. The workstream-level
references block at `:231–239` is untouched (§3.5, D7).

## Acceptance criteria

### AC1 — *Work Tasks* section is an inline grid; each child a row with all five fields · PASS
`test_work_task_grid_renders_all_five_fields` asserts headers
`[Identifier, Title, Area, Status, Claim state]` and per-row cells for a claimed
(`"Claimed · AGP-dev-storage"`) and an unclaimed (`"Unclaimed"`) child;
`test_detail_pane_renders_parent_pi_and_work_tasks` confirms the section is now a
grid (rows), not `<a href>` labels (C4).

### AC2 — Area + claim state sourced from fetched records (worker thread), not by widening the summary · PASS
`test_fetch_detail_extras_joins_edges_with_records` confirms the membership edges
resolve to full records carrying `work_task_area`/`work_task_claimed_by`.
Source: the enrichment is in `_load_child_work_tasks`, called from
`fetch_detail_extras` (worker thread); `access/entity_summary.py` is untouched
(§3.3, C7, D4).

### AC3 — Same grid as References: filter, multi-sort + grouping, preview, drag-resize; no fork · PASS
The new `test_work_task_grid_wtk077.py` exercises the inherited stack on
`WorkTaskGridSection`: PI-116 filter narrows rows 3→1
(`test_filter_narrows_work_task_rows`); PI-117 sort routing applies
(`test_sort_routing_applies_on_work_task_grid`) and grouping swaps to the tree,
bucketing by the contract's own Area option
(`test_grouping_swaps_to_tree_and_buckets_by_area`,
`test_group_combo_offers_work_task_options`); PI-118 preview extractor names the
far-side `work_task` with `area` subtitle
(`test_preview_extractor_names_work_task_with_area_subtitle`); PI-119 header is
`Interactive` with Title on `Stretch` and a `_MIN_SECTION_WIDTH` floor
(`test_non_title_columns_are_interactive`, `test_title_column_stays_stretch`,
`test_resize_section_takes_effect`, `test_minimum_section_size_floor`). No forked
grid — `WorkTaskGridSection` is a subclass of `ReferencesSection` (C1, C5).

### AC4 — All 25 References usages render identically; default contract byte-for-byte today's behavior · PASS
`test_references_default_contract_headers_unchanged` confirms the default-contract
headers are exactly Direction/Relationship/Identifier/Type/Title/Status/Created/
Updated. The full `test_references_section*` suites pass unchanged; the contract
is selected as `contract or _REFERENCES_CONTRACT`, so the no-argument call sites
take the identical path (C2).

### AC5 — `test_context_menus`, `test_references_section*`, `test_linked_record_preview` pass unchanged · PASS
All green in the combined 112-passed run. The Work Task row menu is a *separate*
contract-supplied factory (`_work_task_row_menu`); the References menu path
(`_references_row_menu`) is untouched, so the context-menu sweep keeps its exact
assertions (C2, C3).

### AC6 — Work Task grid is read-only: navigable, no Add/Delete · PASS
`test_work_task_grid_section_double_click_navigates` emits
`navigate_requested("work_task", "WTK-001")`;
`test_work_task_grid_renders_all_five_fields` and
`test_work_task_grid_section_has_no_add_button` confirm no
`references_section_add_button` even with a client present;
`test_work_task_grid_section_row_menu_is_read_only` confirms the menu is
`[Go to …, Copy identifier]` with no "Delete reference" (C6).

### AC7 — Empty case renders `"No Work Tasks recorded."` · PASS
`test_work_task_grid_empty_case_preserved` confirms no `WorkTaskGridSection` is
built and the dim label is present when there are no child edges.

### AC8 — Full-extract rename (§3.7) and sixth *Claimed at* column (§3.4) recorded as deliberate out-of-scope · PASS
The `RecordGridSection` extraction is documented as a pure-rename follow-on in
the WTK-076 commit message and the spec §3.7 / D2 — `ReferencesSection` is
deliberately not renamed (would touch 25 imports for no functional gain). The
sixth *Claimed at* column is recorded as out-of-scope in §3.4 / D8 (the WTK names
five fields; claim state is the single derived string). Both are explicit
decisions, not silent omissions.

## Graceful degradation — disposition

The spec's §3.3 degradation path (a child id whose record can't be loaded keeps
its identifier and renders area/claim state as the dash sentinel) is confirmed by
`test_fetch_detail_extras_degrades_when_record_missing`: with the record list
empty, both membership-edge children still define rows
(`{WTK-001, WTK-002}`), each falling back to the identifier-only dict. In
`_work_task_row`, such a row leaves `area`/`claim_state` `None`, which the grid
renders as `_DASH`. The membership edge set defines the rows; a missing field
never drops a row. Correct, in-spec behavior.

## Notes for the orchestrating session

- No production code written or changed by this phase (verification only). The
  one new file is `tests/crmbuilder_v2/ui/widgets/test_work_task_grid_wtk077.py`
  (9 tests closing the §5.4 grid-feature-stack acceptance gap that WTK-076's own
  tests did not directly assert on the Work Task contract).
- WTK-076's tests already covered fields, navigation, the empty case, the
  fetch-join + degradation, the read-only menu, the suppressed Add button, and
  the unchanged References-default headers; this phase confirmed those and added
  the inherited-feature-stack coverage the spec's §5 verification approach calls
  for (filter / sort / grouping / preview / resize on the Work Task grid).
