# PI-119 / WTK-074 — Verification Report

**Verifier Work Task:** WTK-074 (area: ui)
**Under test:** WTK-073 build (commit `24ed8d4`) of the PI-119 delta
**Against:** WTK-072 Design spec (`pi-119-link-panel-column-resize-ui-design.md` v0.1) §6 acceptance criteria
**Scope:** the resize-enablement delta only — flat-table header `ResizeToContents`→`Interactive` on the embedded `ReferencesSection`, `_MIN_SECTION_WIDTH` floor, one-time content seed, and the settled out-of-scope decisions for the grouped tree (§3.4) and width persistence (§3.5). The PI-116/117/118 foundations (filter, multi-sort, grouping, preview) are re-exercised as regression guards, not re-verified as features.
**Method:** source read of the WTK-073 production diff against the spec; execution of the build's own resize suite plus the spec-named regression suites; ruff on the touched file. This phase writes **no production code**.

## Verdict

**All 7 acceptance criteria PASS.** No deviations from the design found. The embedded link grid is now drag-resizable (`Interactive`), col 4 *Title* stays `Stretch` and absorbs the slack, sections are floored at `_MIN_SECTION_WIDTH` (48 px), and widths are content-seeded once. Multi-sort routing + glyph, grouping table↔tree swap, the debounced filter, and the inline preview all continue to work. `test_context_menus` and `test_linked_record_preview` are byte-unchanged and green. The grouped-tree auto-fit (§3.4) and width-persistence (§3.5) deferrals are present in code and documented as deliberate, not silent.

## Evidence base

All commands run from repo root (`testpaths = ["tests", ...]`; the spec's
`cd crmbuilder-v2` prefix is a doc artifact — the suite lives at repo-root
`tests/`). `QT_QPA_PLATFORM=offscreen`, the established widget-test pattern.

- WTK-073 resize suite (re-run, green): **7 passed** —
  `test_references_section_resize_wtk073.py`.
- Regression suites named by the design §5 (re-run, green): **81 passed** —
  `test_references_section.py`, `test_references_section_sort_group.py`,
  `test_linked_record_preview.py`, `test_context_menus.py`.
- Combined run: **88 passed in 3.04s**, zero failures.
- `ruff check crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py
  tests/crmbuilder_v2/ui/widgets/test_references_section_resize_wtk073.py` —
  **All checks passed!**

## Source confirmation (the delta)

**Flat-table header — `references_section.py:356–373`.** Confirmed:
`table_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)` replaces
the prior `ResizeToContents`; col 4 kept on `Stretch`
(`setSectionResizeMode(4, Stretch)`); `setMinimumSectionSize(_MIN_SECTION_WIDTH)`
applied; `self._table.resizeColumnsToContents()` runs once, after
`setHorizontalHeader` + `attach_proxy` so the model+view are wired and the
content metrics are real. `_MIN_SECTION_WIDTH = 48` is a module constant
(`:114`). This is exactly the §3.1–§3.2 design.

**Grouped tree header — `references_section.py:628–632`, inside `_rebuild_tree`.**
Confirmed still `ResizeToContents` + col 4 `Stretch`, re-applied on each rebuild.
This is the §3.4 settled decision, not an omission. The Work Task's literal
instruction to "confirm the same for the tree header" is **superseded by the
spec it cites**: §3.4 settles the tree as out-of-scope for this iteration
(frequent `_rebuild_tree`; standalone-panel precedent). Treated as PASS-by-design
under AC7, not a regression.

**`MultiSortHeaderView` — untouched.** No edit to `multi_sort_header.py` in the
build. Resize lives in the inherited `QHeaderView` resize-mode machinery;
section-divider drags do not emit `sectionClicked`, so sort routing/glyph stay
orthogonal (§3.3). Confirmed by `test_sort_routing_survives_resize_enablement`.

## Acceptance criteria

### AC1 — User can drag any non-Title border; Title yields/absorbs slack · PASS
Non-Title columns `(0,1,2,3,5,6,7)` are `Interactive`
(`test_non_title_columns_are_interactive`); col 4 is `Stretch`
(`test_title_column_stays_stretch`). Decisive behavioral proof: a
`ResizeToContents` section silently ignores `resizeSection`; an `Interactive`
one honors it — `header.resizeSection(2, 200)` then `sectionSize(2) == 200`
passes (`test_resize_section_takes_effect`). The single `Stretch` column
guarantees the grid fills the viewport with no trailing gutter (§3.1).

### AC2 — Initial widths content-seeded, not `defaultSectionSize` · PASS
`resizeColumnsToContents()` is invoked once after model+view wiring
(`references_section.py:373`), reusing Qt's own content metrics — the same
computation the prior `ResizeToContents` performed, applied once and leaving the
sections `Interactive`/draggable thereafter. Per the design's offscreen-metrics
note (§3.1), exact seeded pixel values are platform-dependent and deliberately
**not** asserted; verification is by construction (the seed call is present and
correctly ordered) plus the mode assertions above. No deviation.

### AC3 — Column cannot drag below `_MIN_SECTION_WIDTH`; glyph never clipped · PASS
`header.minimumSectionSize() == _MIN_SECTION_WIDTH` (48), and an over-drag to 1 px
is clamped to `>= _MIN_SECTION_WIDTH` (`test_minimum_section_size_floor`). The
48 px floor keeps the divider grabbable and protects `MultiSortHeaderView`'s
right-aligned precedence glyph from clipping (§3.2).

### AC4 — Header clicks still set/cycle multi-key sort + paint glyph · PASS
`header._route_click(2, NoModifier)` sets the proxy primary to col 2 and
`indicator_for(2)` still resolves the glyph
(`test_sort_routing_survives_resize_enablement`). No regression to multi-sort
(C1) with resize enabled.

### AC5 — Grouping, filtering, inline preview behave as before · PASS
- **Grouping (C2):** group combo → tree swap + `_group_model` built
  (`test_grouping_still_swaps_to_tree`); `test_references_section_sort_group.py`
  green.
- **Filter (C3):** debounced `LinkFilterInput` narrows proxy rows 3→1
  (`test_filter_still_narrows_rows`).
- **Preview (C4):** `test_linked_record_preview.py` unchanged and green; resize
  is geometry-only and `PreviewController` anchors via column-width-independent
  `_row_at` (§3.6).

### AC6 — `test_context_menus` and `test_linked_record_preview` pass unchanged · PASS
Both suites byte-unchanged in the build and green in the combined run
(88 passed). No menu/preview code was touched.

### AC7 — Tree auto-fit and width persistence recorded as deliberate out-of-scope · PASS
- Grouped tree stays `ResizeToContents` (§3.4) — confirmed in source at
  `references_section.py:628–632` and called out in the WTK-073 commit message
  as a deliberate supersession of the Work Task's literal tree-header
  instruction.
- Width persistence (§3.5) is **deferred**: no `QSettings`/state handle exists in
  `ReferencesSection` (rebuilt from scratch on each detail load), confirmed by
  source read; the design records the future `saveState()/restoreState()` path
  keyed per entity-type. Both are documented decisions (D4, D5), not silent
  omissions.

## Per-user / per-panel width persistence — disposition

The Work Task asks to verify persistence "only insofar as the Design settled it
as in-scope vs deferred." **Settled DEFERRED (§3.5 / D5).** PI-119 ships
resize-enablement only; persistence is out of scope this iteration with a
documented extension path. Verifier confirms the build correctly omits it (no
persistence state added) and the deferral is explicit — this is the correct,
in-spec outcome, not a gap.

## Notes for the orchestrating session

- One harmless doc-vs-reality mismatch: the design's §5 command block prefixes
  `cd crmbuilder-v2`, but tests resolve from repo root (`pyproject.toml`
  `testpaths`). The build's own commit ran them correctly; flagged only so a
  future runner doesn't copy the `cd` literally.
- No production code written or changed by this phase (verification only).
