# PI-148 — Discoverable Preview Affordance — Test Verification (WTK-154)

**Version:** 0.1
**Status:** Test verification (no production code; verifies the WTK-153 build against the WTK-152/§5–§6 spec)
**Planning Item:** PI-148 — *Make the link-panel inline preview discoverable — visible per-row affordance, not just timed hover*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-154 (area: ui) — Test phase of workstream WSK-139
**Subject build:** commit `bfeb80ee` (WTK-153 — *discoverable inline-preview peek button*)
**Subject design:** `pi-148-discoverable-preview-affordance-ui-design.md` v0.1 (§5 acceptance criteria, §6.2 automated verification); ratified by `pi-148-discoverable-preview-affordance-design-verification-wtk152.md`

## 0. What this note records

WTK-154 is the Test phase: verify the affordance the Develop phase (WTK-153)
shipped against the design's acceptance criteria (§5) and automated-verification
list (§6.2), on all three surfaces — the embedded `ReferencesSection` grid, the
generalized Work-Task grid (`WorkTaskGridSection` / PI-120, plus
`EntityFieldsGridSection`), and the standalone `ReferencesPanel`. **Test/verification
only — no production code changed.** The build already carried a comprehensive
suite; this verification (a) confirms every §5 / §6.2 item maps to a passing
test, (b) closes three coverage gaps against named criteria with new tests, and
(c) flags any deviation. **No deviation from the spec was found.**

## 1. Result

- `pytest tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py tests/crmbuilder_v2/ui/test_context_menus.py` → **75 passed, 1 warning** (a pre-existing PySide deprecation warning on `QMouseEvent`, unrelated to this work). 72 were the WTK-153 build's tests; 3 are added here (§3).
- `ruff check tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py` → **All checks passed**.
- The regression target `test_context_menus.py` is **green** with the affordance installed (AC-8); the build's own `test_panel_context_menu_unchanged_with_preview` / `test_section_context_menu_unchanged_with_preview` / right-click-dismiss tests confirm the Go-to / Open / Delete menu label sets and the `navigate_requested` / `open_requested` triggers are unchanged.

## 2. Acceptance-criteria → test coverage (§5)

| AC | Criterion | Covering test(s) | Verdict |
|---|---|---|---|
| 1 | Visible affordance per row; group node / Relationship cell show none | `test_affordance_is_focusable_icon_button_hidden_at_rest`, `test_affordance_show_at_labels_positions_and_reveals`, `test_controller_reveals_affordance_on_previewable_row`, `test_controller_group_node_reveals_no_affordance`, `test_affordance_reveals_on_panel_source_and_target_not_relationship` | ✓ |
| 2 | Operable by pointer → pinned card for that row/endpoint | `test_affordance_click_opens_same_card_as_space`, `test_panel_source_cell_opens_source_endpoint` | ✓ |
| 3 | Operable by keyboard + accessible (focus, Enter/Space, `accessibleName`, tooltip) | `test_affordance_is_focusable_icon_button_hidden_at_rest` (tooltip/focus), `test_controller_current_changed_reveals_affordance_for_keyboard` (focus reveal), **`test_affordance_activates_on_keyboard_space` (new)**, `accessibleName` asserted in `test_affordance_show_at...` / `test_controller_reveals_affordance_on_previewable_row` | ✓ |
| 4 | Opens the same content as hover/Space | `test_affordance_click_opens_same_card_as_space` (same identifier + focusable as Space), **`test_all_three_triggers_open_same_record_and_coexist` (new)** | ✓ |
| 5 | Accelerators intact (dwell transient, Space pinned, Esc, arrow re-target) | `test_accelerators_intact_after_affordance_installed`, **`test_all_three_triggers_open_same_record_and_coexist` (new)**; Esc/arrow-retarget covered by the existing `_on_key_press` / `_on_current_changed` tests | ✓ |
| 6 | Consistent on all three surfaces (column-aware on the panel) | `test_affordance_reveals_on_all_three_grid_surfaces`, `test_affordance_reveals_on_panel_source_and_target_not_relationship`, `test_panel_affordance_is_cell_anchored`, `test_section_affordance_is_row_anchored` | ✓ |
| 7 | Hides on grace, reorder/regroup/refilter, context menu, scroll/resize | `test_controller_dismiss_hides_affordance`, `test_controller_sort_change_hides_affordance`, `test_controller_invalid_index_in_mousemove_hides_affordance`, `test_controller_affordance_enter_cancels_dismiss_grace`, **`test_affordance_viewport_leave_starts_dismiss_grace` (new)**; scroll/resize wired to `_hide_affordance` in `attach_view` | ✓ |
| 8 | Context menu / Go-to / Open / double-click unchanged | `test_panel_context_menu_unchanged_with_preview`, `test_section_context_menu_unchanged_with_preview`, `test_section_right_click_dismisses_open_card`, `test_panel_right_click_dismisses_open_card`, `test_context_menus.py` | ✓ |
| 9 | No model / column-model restructuring | `test_affordance_reveal_click_hide_calls_no_model_mutator`, `test_section_open_enrich_dismiss_calls_no_model_mutator` | ✓ |

## 3. Coverage gaps closed (new tests)

Three acceptance criteria were satisfied by the implementation but had no *explicit*
test. Added to `test_linked_record_preview.py` (test-only, additive):

1. **`test_affordance_activates_on_keyboard_space`** (AC-3) — reveals the button,
   focuses it, and presses **Space**, asserting it opens the same pinned card a
   click does (the Qt-native `QPushButton` Space→`clicked` path through
   `_on_affordance_clicked` → `open_for_index`). (`Space`, not `Return`: a
   non-default `QPushButton` maps only Space to `clicked`.)
2. **`test_all_three_triggers_open_same_record_and_coexist`** (AC-4/AC-5) — drives
   the affordance click, the 400 ms dwell, and Space on the *same* row and asserts
   all three open a card for the *same* far-side record with the correct
   `focusable` variant (click+Space pinned, dwell transient) — the additive
   coexistence the task calls out explicitly.
3. **`test_affordance_viewport_leave_starts_dismiss_grace`** (AC-7) — a real
   viewport `Leave` while the button is shown starts the 200 ms grace (not an
   immediate hide), so the pointer can travel onto the overlaid button; grace
   expiry (wired to `dismiss`) then hides it.

## 4. Deviations from spec

**None.** Every §5 acceptance criterion and §6.2 automated-verification item maps
to a passing test across all three surfaces. Two incidental observations, neither
a deviation:

- The §6.2 prose names a per-surface "MouseMove over a previewable row shows the
  affordance" check; the build verifies the same behavior at the controller seam
  via `_reveal_affordance` (called from `_on_mouse_move` at 0 ms) plus the
  end-to-end `test_section_real_hover_starts_dwell_and_opens_card`, which dispatches
  a real `MouseMove` through the installed event filter. Equivalent coverage, not a
  gap.
- The context-menu label sets asserted by the guards include the **PI-121 / WTK-079**
  additive *"Open &lt;type&gt;"* entries (e.g. the panel row menu is `["Go to source",
  "Open Session", "Go to target", "Open Decision", "Delete reference"]`). That is the
  current `main` baseline the affordance must not disturb — and does not — so the §3.6
  three-item illustration in the design is descriptive of the pre-PI-121 menu, not a
  requirement the affordance violates.

## 5. Outcome

- **WTK-154 (Test, WSK-139) satisfied.** The WTK-153 build holds against the PI-148
  design's §5 / §6.2 verification criteria on all three surfaces; the affordance is
  discoverable (0 ms, visible/focusable per row), pointer- and keyboard-operable,
  opens the same `LinkedRecordPreviewCard` as the dwell/Space accelerators, coexists
  with all three triggers, and introduces no context-menu / Go-to / Open / model
  regression.
- **Suite:** 75 passed (72 build + 3 verification), ruff clean.
