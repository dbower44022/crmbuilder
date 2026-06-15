# PI-148 — Discoverable Preview Affordance — Design Verification & Coverage (WTK-152)

**Version:** 0.1
**Status:** Design verification (no new design content; ratifies the existing design)
**Planning Item:** PI-148 — *Make the link-panel inline preview discoverable — visible per-row affordance, not just timed hover*
**Project:** PRJ-016 — *usability for objects that carry large numbers of links*
**Work Task:** WTK-152 (area: ui) — Design phase of workstream WSK-138
**Subject design:** `pi-148-discoverable-preview-affordance-ui-design.md` v0.1 (authored under WTK-150 / WSK-135)

## 0. Why this note exists (and why it is *not* a second design)

PI-148 has been decomposed twice. The first decomposition's Design Work Task
(**WTK-150**, workstream **WSK-135**) already produced the full design deliverable
`pi-148-discoverable-preview-affordance-ui-design.md` (511 lines, committed to
`main` as `0d444284`). **WTK-152 is the Design Work Task of a *second*
decomposition of the same PI-148** (workstream **WSK-138**); both Design tasks
ask for the identical artifact — *"DECIDE the affordance … SPECIFY placement and
behavior across all three surfaces … Output is a written spec/design only."*

Authoring a second 511-line design for the same PI would duplicate work that
already exists on `main` — the exact failure the Area-Specialist protocol warns
against ("you will build on stale code and duplicate work that already exists").
The correct, additive deliverable for WTK-152 is therefore **not** a redundant
re-spec but an **independent verification** that the existing design (a) fully
satisfies WTK-152's stated requirements and (b) is buildable *as written* against
current `main` — confirming the design's code-seam assumptions still hold. This
note records that verification and ratifies the existing design as the PI-148
design of record for WSK-138 as well.

If a reviewer instead wants the design *re-authored* under WTK-152, the existing
document is the source of truth to copy; nothing in it needs to change to satisfy
WTK-152 (see §1, §2).

## 1. Requirement coverage — WTK-152 → existing design

Every item WTK-152 asks for is already specified. Mapping:

| WTK-152 requirement | Satisfied by (existing design) | Verdict |
|---|---|---|
| **DECIDE** the affordance: hover-reveal peek icon vs always-visible vs info-column, with rationale | §1 "The open decomposition question — settled here"; §3.1 decision table + prose rejecting always-visible (noise + per-row-widget cost on large lists) and info-column (restructures the shared column model, fights sort/group/resize) | ✓ Covered — chosen: single hover/focus-reveal peek-icon button owned by `PreviewController` |
| **SPECIFY** placement & behavior on **ReferencesSection grid** | §3.2 (row-trailing reveal), §4.3 (`ReferencesSection._install_preview` covers it) | ✓ |
| **SPECIFY** placement & behavior on **standalone References panel** | §3.2 + §3.3 (cell-trailing, column-aware: Source col 0 / Target col 2 only, none on Relationship col 1), §4.3 (`ReferencesPanel._install_preview`) | ✓ |
| **SPECIFY** placement & behavior on **generalized Work-Task grid (PI-120)** | §1 background, §4.3 (`WorkTaskGridSection` / `_WORK_TASK_CONTRACT`), plus entity-fields grid for completeness | ✓ |
| **icon/glyph** | §4.4 — bundled Lucide `eye.svg`, the conventional peek glyph; no collision with `external-link` (the *Open* action) | ✓ |
| **label** | §3.5 / §4.4 — visible tooltip *"Preview"* | ✓ |
| **aria-label** | §3.5 — `accessibleName` = `"Preview <identifier>"` (e.g. *"Preview PI-118"*) | ✓ |
| **keyboard focus order** | §3.5 — real focusable `QPushButton`, reachable by Tab when revealed on the focused row, Enter/Space-activatable; only one button exists at a time so tab order is not inflated | ✓ |
| coexist with **context menu** (no regression of `test_context_menus`) | §3.6 + §6.2 regression guard — affordance is a row overlay, **not** a menu item; opening a context menu is a dismisser; menu label sets asserted unchanged | ✓ |
| coexist with **Go-to / Open row actions** | §3.6 — button emits neither `navigate_requested` nor `open_requested`; double-click + *Open …* unchanged | ✓ |
| coexist with **400 ms hover-dwell + Space accelerators** | §3.4 — both preserved byte-for-byte as accelerators; click's pinned card supersedes a pending dwell card (no double card) | ✓ |
| **subtle persistent hint?** — include or not | §7 — considered and **deferred**: the always-immediate (0 ms) eye glyph is itself the cue, so a coachmark/first-run hint is unnecessary; recorded so it can be revisited if telemetry shows the glyph is missed | ✓ Decision stated |
| keep change **ADDITIVE** | §1, §2 (out of scope), §3.8 invariants — no storage/API/access/model change; existing triggers, menus, and contracts untouched | ✓ |
| **VERIFICATION CRITERIA** (affordance on every link row; click opens same card as hover/Space; all three triggers still work; `test_context_menus` + Go-to/Open remain green) | §5 acceptance criteria 1–9; §6.1 manual + §6.2 automated, incl. context-menu regression guard, accelerators-intact guard, all-three-surfaces, no-mutation guard | ✓ |

**Conclusion:** the existing design satisfies WTK-152 in full. No design gap was
found; no addition or correction to the design is required.

## 2. Buildability verification — design claims vs current `main`

The design names specific code seams it reuses. Each was checked against the
working tree at the current `main` HEAD; all hold, which confirms the design can
be built as written without re-architecting:

| Design claim | Source evidence (current `main`) | Verdict |
|---|---|---|
| `PreviewController` is the single open path with the named handlers/timers | `ui/widgets/linked_record_preview.py` — `PreviewController` (L353), `DWELL_MS = 400` (L378), `GRACE_MS = 200` (L381), `attach_view` (L427), `_on_mouse_move` (L490), `_on_current_changed` (L531), `_open` (L545), `dismiss` (L659) | ✓ all present |
| `open_for_index` and `PreviewAffordance` are *new* (the build delta), not pre-existing | absent from the module | ✓ correctly new |
| Affordance reuses `form_helpers.icon_button` with no new token | `ui/widgets/form_helpers.py` — `def icon_button(icon_name, *, tooltip)` (L281); design's `icon_button("eye", tooltip="Preview")` matches the signature | ✓ |
| Two install sites, one per surface family | `ui/panels/references.py:588` (`ReferencesPanel._install_preview`), `ui/widgets/references_section.py:635` (`ReferencesSection._install_preview`) | ✓ |
| Three grid contracts share the parameterized widget | `references_section.py` — `_WORK_TASK_COLUMNS` (L143), `_ENTITY_FIELDS_COLUMNS` (L165), `_WORK_TASK_CONTRACT` (L308); `WorkTaskGridSection(ReferencesSection)` (L1007), `EntityFieldsGridSection` (L1039); `ReferencesPanel(ListDetailPanel)` at `panels/references.py:75` | ✓ |
| Standalone panel has a column-aware extractor + the asserted menu | `panels/references.py` — `_preview_target` (L626) wired in `_install_preview` (L609); `_build_context_menu` (L382) with "Go to source" (L396) / "Go to target" (L405) | ✓ |
| `test_context_menus` is the regression target | `tests/crmbuilder_v2/ui/test_context_menus.py` (note: repo-root `tests/`, not `crmbuilder-v2/tests/`) | ✓ exists |
| Preview tests exist for the build to extend | `tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py` | ✓ exists |
| `eye.svg` must ship (Lucide is bundled per-name); no collision with the *Open* icon | `ui/assets/icons/lucide/eye.svg` **absent** (must be added by the build), `external-link.svg` **present** | ✓ consistent with §4.4 |

**One documentation nit for the implementing Work Task** (not a design error):
the design's §6.2 prose references the test-suite path generically; the concrete
paths are repo-root `tests/crmbuilder_v2/ui/test_context_menus.py` and
`tests/crmbuilder_v2/ui/widgets/test_linked_record_preview.py`. Recorded here so
the downstream build (WSK-139 / Development) does not look under
`crmbuilder-v2/tests/`.

## 3. Outcome

- **Design decision (ratified):** single hover/focus-reveal peek-icon button
  owned by `PreviewController`, revealed at 0 ms on the trailing edge of the
  hovered/focused row (or the hovered Source/Target cell on the standalone panel),
  click/Enter/Space opens the same pinned `LinkedRecordPreviewCard`; always-visible
  and info-column rejected; persistent coachmark deferred. (Per
  `pi-148-discoverable-preview-affordance-ui-design.md` §3.1.)
- **WTK-152 (Design, WSK-138) is satisfied by the existing design** — no new
  design content needed; coverage and buildability verified above.
- **Downstream:** the Development workstream **WSK-139** (`blocked_by` WSK-138)
  builds against `pi-148-discoverable-preview-affordance-ui-design.md` §4–§6,
  using the concrete test paths noted in §2.
