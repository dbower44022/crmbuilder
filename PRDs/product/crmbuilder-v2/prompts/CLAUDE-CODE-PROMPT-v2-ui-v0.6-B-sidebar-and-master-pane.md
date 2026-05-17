# CLAUDE-CODE-PROMPT-v2-ui-v0.6-B-sidebar-and-master-pane

**Last Updated:** 05-16-26 18:05
**Series:** v2-ui-v0.6
**Slice:** B (2 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.6-A (foundation + About dialog)

## Purpose

Slice **B — Sidebar + master-pane delegate** delivers the shared visual vocabulary per DEC-093: the 3px left accent bar + tinted background + medium-weight text treatment, applied uniformly to sidebar entries and master-pane rows. After this slice merges, every sidebar entry and every master-pane row across all panels renders the new selected-state visuals, even though panel chrome and detail panes are still Qt-default until slice C.

Six deliverables:

1. **Sidebar visual treatment.** Container background, group-header treatment, entry geometry, stale-indicator dot recolor per design pass §2.1.

2. **Sidebar selected-state custom rendering.** `QStyledItemDelegate` on the existing `QListWidget` in `ui/sidebar.py` rendering the 3px left accent bar + tinted background + medium-weight text per DEC-093.

3. **Shared master-pane delegate.** New `ui/widgets/master_pane_delegate.py` with a `MasterPaneDelegate(QStyledItemDelegate)` class. Handles row height, dividers, column headers, hover/selected/focused state, soft-deleted-row treatment, identifier-column mono font.

4. **Tree-view variant delegate.** A `MasterPaneTreeDelegate(MasterPaneDelegate)` subclass extending the parent with Lucide chevron indicators replacing Qt's default branch indicator, plus 16px indentation per level, plus selected-state left-bar respecting indentation per design pass §2.3.

5. **Delegate registration on every panel.** `ListDetailPanel.__init__()` applies `MasterPaneDelegate` automatically; the Topics panel overrides via a class attribute to use `MasterPaneTreeDelegate`. `VersionedPanel`-based panels (Charter, Status) and any other panel not inheriting from `ListDetailPanel` get per-panel registration.

6. **Inheritance-topology verification pass.** Before relying on the centralized hook, slice B verifies which panels inherit from which base and adds fallback registration for the panels that don't pick up the delegate automatically.

This slice does NOT add: panel chrome retoken beyond what slice A delivered (slice C); label-above form layout in detail panes (slice C); ReferencesSection sub-sectioned rendering (slice C); button categories (slice D); form-control state coverage (slice D); status / error / warning surfaces (slice E); crash banner (slice E); `__version__` bump (slice F).

## Project context

Slice A landed the foundation: tokens, fonts, icons, modal elevation, base widget chrome hooks, About dialog re-skin. The token system is read-only after slice A merges per PRD §8; slice B consumes tokens via the `t()` accessor from `styling.py` and does not modify them.

DEC-093 commits the two surfaces — sidebar entries and master-pane rows — to one design vocabulary. The selected-state treatment is 3px left accent bar in `color.accent.default` + `color.accent.subtle` tinted background + `color.neutral.900` medium-weight text. Both surfaces use `QStyledItemDelegate` for the custom rendering. Slice B's job is to honor that promise consistently across both surfaces and across all 12+ panels that ship with v2 today.

The master-pane delegate is the highest-leverage piece in v0.6: registered once via `ListDetailPanel.__init__()` (per the slice B prompt's central decision), it covers every panel's row rendering automatically. Get the delegate right and the consistency promise holds; get the registration wrong and individual panels silently render with Qt defaults, breaking DEC-093.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report.
3. Confirm git identity: `git config user.name` = `Doug Bower`, `git config user.email` = `dbower44022@users.noreply.github.com`.
4. Pull latest: `git pull --rebase origin main`. Slice A must be on `main`.
5. Verify slice A is in place:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` contains `TOKENS`, `t`, `build_app_stylesheet`, `apply_stylesheet`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/icons.py` exists with the `lucide()` loader.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/modal_backdrop.py` exists.
   - App launches: `uv run crmbuilder-v2` (or the appropriate launcher command) — About dialog renders with wordmark + tagline per design pass §2.8.
6. Confirm storage server operational. Health check at `http://127.0.0.1:8765/health`; start in background if needed (verify-first per slice A's pre-flight pattern).
7. Confirm v0.5 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. This is the regression net.

## Reading order

Before producing any code, read:

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (focus: §2 items 7–8; §4.4–4.5; §6 ACs B1–B7).
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (focus: §4 Slice B).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (focus: §2.1 Sidebar, §2.3 Master pane, §3.1 high-attention surfaces, DEC-093 in §1.2.2 references).
5. v2 source files relevant to this slice:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` — being modified for §2.1 treatment.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — base class for centralized delegate registration; already touched by slice A for chrome hooks.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_panel.py` — base for Charter and Status panels; verify whether it has a master-pane view that needs delegate registration.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py` — the tree-view variant target.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/charter.py`, `panels/status.py` — `VersionedPanel`-based; fallback registration target.
   - All other `crmbuilder-v2/src/crmbuilder_v2/ui/panels/*.py` files — verify inheritance topology.

## Step 1 — Inheritance topology verification pass

BEFORE writing any code, audit every file in `ui/panels/` to determine:

- Which class each panel's primary widget inherits from (`ListDetailPanel`, `VersionedPanel`, something else, or `QWidget` directly).
- Whether each panel has a master-pane view that the delegate needs to attach to.
- What method on the base class is responsible for constructing the master view (likely `_create_master_widget` or equivalent — verify).

Produce a table or list noting, for each panel: filename, base class, has-master-view (yes/no), and which mechanism will register the delegate (centralized via `ListDetailPanel.__init__`, centralized via `VersionedPanel.__init__`, or per-panel fallback).

This audit informs Steps 5 and 6 below. If the audit surfaces a panel pattern not anticipated (e.g., a panel using a custom widget that's neither `ListDetailPanel` nor `VersionedPanel`), pause and report before proceeding — the slice B prompt assumed two base patterns, and a third would warrant explicit handling rather than improvised fallback.

### 1.1 Acceptance verification (Step 1)

- Audit table produced and reviewed against the implementation plan §3 panel list. Expected: 8 governance panels (Sessions, Decisions, Risks, Planning Items, Topics, References, Charter, Status) and 4 methodology panels (Domains, Entities, Processes, CRM Candidates) — total 12. Plus v0.5's Engagement panel as a 13th if v0.5 has shipped by slice B's run time.
- Each panel's base class is documented.
- Charter and Status confirmed as `VersionedPanel`-based; all others confirmed as `ListDetailPanel`-based (or pause-and-report if otherwise).

## Step 2 — Sidebar visual treatment (`ui/sidebar.py`)

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/sidebar.py` per design pass §2.1.

### 2.1 Container chrome

- Set fixed width to 220px via `setFixedWidth(220)`.
- Apply background `t("color.neutral.100")` via per-widget `setStyleSheet`.
- Apply right-edge 1px hairline border in `t("color.neutral.200")` via the same `setStyleSheet` (use `border-right: 1px solid <neutral.200>;`).
- Top and bottom padding: `t("space.4")` (16px) via `setContentsMargins` or QSS padding.

### 2.2 Group headers (Governance, Methodology)

- Render as non-selectable `QListWidgetItem` instances per the v0.5 convention.
- Item text in `t("font.size.caption")` (12px), `t("font.weight.semibold")` (600), `t("color.neutral.500")`, with `letter-spacing: 0.04em` applied via per-item font properties or QSS.
- Padding: `t("space.2")` top, `t("space.1")` bottom, `t("space.3")` horizontal.
- Vertical space `t("space.4")` (16px) above each group header beyond the first.
- No separator line between groups.

### 2.3 Entry geometry

- Set sizeHint per entry to 32px height (`space.2` top + `font.size.body` line + `space.2` bottom roughly).
- Entry text: `t("font.size.body")` (14px), `t("font.weight.regular")` (400), `t("color.neutral.800")`.

### 2.4 Stale-indicator dot recolor

The existing stale-indicator dot logic remains; change the color from the legacy `#1F3864` to `t("color.accent.default")` (`#1F5FBF`). Locate the existing dot-drawing code and replace the color constant.

### 2.5 Acceptance verification (Step 2)

- App launches; sidebar renders 220px wide with `color.neutral.100` background and a right-edge hairline.
- Group headers (Governance, Methodology) render in semibold caption-size text in `color.neutral.500`.
- Entries render in body-size text at `color.neutral.800`.
- Stale-indicator dot color is `#1F5FBF` rather than `#1F3864`.

Note: selected-state visuals are NOT yet applied (covered in Step 3). After Step 2 alone, hovering and selecting an entry produces Qt's default highlight.

## Step 3 — Sidebar selected-state custom rendering

In `ui/sidebar.py`, add a `QStyledItemDelegate` subclass — call it `SidebarItemDelegate` — that overrides `paint()` to render the selected-state vocabulary per DEC-093.

### 3.1 `SidebarItemDelegate` paint logic

In `paint(painter, option, index)`:

- If the item is non-selectable (group header), fall through to `super().paint(painter, option, index)` — the QSS-driven group-header treatment from Step 2.2 handles it.

- If the item is selectable:
  - Determine state: default, hover, selected, focused (using `option.state` flags). Selected and focused can co-occur (keyboard focus on a selected row).
  - If selected: fill the entry background with `t("color.accent.subtle")` via `painter.fillRect(option.rect, QColor(...))`. Then draw the 3px left accent bar by filling a 3px-wide vertical strip flush against `option.rect.left()` with `t("color.accent.default")`.
  - If hover (and not selected): fill the entry background with `t("color.neutral.200")`. No accent bar.
  - If focused (keyboard, not just selected): in addition to the selected/hover background, draw a 1px focus ring in `t("color.accent.focusring")` (40% alpha) drawn 2px outside the entry bounds. The focus ring is informational — Qt's default focus rendering may conflict; suppress the default via `option.state &= ~QStyle.State_HasFocus` before calling super or paint manually.
  - Draw the text: selected → `t("color.neutral.900")` at `t("font.weight.medium")`; default → `t("color.neutral.800")` at `t("font.weight.regular")`.
  - Stale-indicator dot, if present, drawn after text rendering as in Step 2.4 (the dot color is `color.accent.default` regardless of state; may need a 1px `color.neutral.0` halo on tinted backgrounds to maintain contrast — verify visually in screenshot).

### 3.2 Attach the delegate

In `Sidebar.__init__` (or equivalent), attach the delegate via `self.list_widget.setItemDelegate(SidebarItemDelegate(self.list_widget))`.

### 3.3 Acceptance verification (Step 3)

- Hovering a sidebar entry tints its background `color.neutral.200`.
- Clicking a sidebar entry renders the 3px left accent bar plus `color.accent.subtle` background plus `color.neutral.900` medium-weight text.
- Keyboard navigation (arrow keys) renders the focus ring.
- Group headers (non-selectable) continue to render in semibold caption style without any selected-state visual artifacts.
- Stale-indicator dot remains visible on selected entries.

## Step 4 — `MasterPaneDelegate` class

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/master_pane_delegate.py` exposing `MasterPaneDelegate(QStyledItemDelegate)`.

### 4.1 Constructor

```python
class MasterPaneDelegate(QStyledItemDelegate):
    def __init__(
        self,
        parent: QObject | None = None,
        *,
        is_soft_deleted_visible: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_soft_deleted_visible = is_soft_deleted_visible or (lambda: False)
        # Cache resolved hex / px values for paint-time efficiency
        self._color_neutral_0 = QColor(t("color.neutral.0"))
        self._color_neutral_100 = QColor(t("color.neutral.100"))
        ...
```

The `is_soft_deleted_visible` callable lets each panel pass a lambda reading its own toggle state. The delegate queries it per-paint to decide whether to render the soft-deleted-row treatment for rows whose record is soft-deleted. Default is `lambda: False` so panels without soft-delete state still work.

### 4.2 `paint()` implementation

Implement `paint(painter, option, index)`:

- Determine row state: default, hover, selected, focused. Same flag-checking pattern as `SidebarItemDelegate`.
- Determine row visual class:
  - Soft-deleted? Check `index.data(SOFT_DELETED_ROLE)` (where `SOFT_DELETED_ROLE` is a custom `Qt.UserRole + N` defined in the file or in a shared constants module). If the role data is truthy AND `self._is_soft_deleted_visible()` is True, render with `color.neutral.500` text and a leading Lucide `trash-2` icon at 14px in the identifier column.
  - Otherwise render with `color.neutral.800` text (or `color.neutral.900` medium-weight if selected).
- Selected-state treatment (per DEC-093, same as sidebar):
  - Background: `color.accent.subtle`.
  - 3px left accent bar in `color.accent.default`, flush against `option.rect.left()`.
  - Text in `color.neutral.900` at `font.weight.medium`.
- Hover-state treatment:
  - Background: `color.neutral.100`.
  - No accent bar.
- Focused (keyboard) state:
  - Selected-state + 1px focus ring in `color.accent.focusring` drawn 1px inside the row's bounds (constrained inside the cell area, not crossing the row divider).
- Row divider: 1px hairline in `color.neutral.200` along the bottom of the row, drawn after the cell content.
- Identifier column rendering: if the column matches the identifier-column index (passed at construction time, or detected via the column's header text — TBD by slice B's prompt-runner; reasonable default is column 0), use `font.family.mono` (JetBrains Mono) at `font.size.small` (13px). For the soft-deleted-row treatment, render the leading `trash-2` icon at 14px before the identifier text with `space.1` (4px) horizontal padding.

### 4.3 `sizeHint()` implementation

Return `QSize(width, 28)` — row height 28px per design pass §1.1 density.

### 4.4 Custom data roles

If `SOFT_DELETED_ROLE` is not already defined in the v0.5 codebase, define it in `master_pane_delegate.py` as a module-level constant: `SOFT_DELETED_ROLE = Qt.UserRole + 100` (or another non-conflicting integer; verify the existing v0.5 panels don't already use the same role number).

The panel-side mechanism that POPULATES the soft-deleted role on each row remains panel-specific code — not in scope for slice B. Slice B's prompt-runner verifies whether v0.5 panels already populate this role on soft-deleted rows; if not, the delegate falls back to `False` (renders the row as live) until a future slice adds the role population.

### 4.5 Column headers

Override `initStyleOption(option, index)` (or use a separate header-painting mechanism via QSS on the header view, since column headers are NOT painted by the delegate). The QSS rule for `QTableView QHeaderView::section` added in slice A's `build_app_stylesheet()` already covers the visual treatment per design pass §2.3. Slice B verifies the rule applies correctly; no additional code needed for column headers unless a specific issue surfaces.

### 4.6 Acceptance verification (Step 4)

- `from crmbuilder_v2.ui.widgets.master_pane_delegate import MasterPaneDelegate` succeeds.
- Instantiating `MasterPaneDelegate()` succeeds with default `is_soft_deleted_visible`.
- (Acceptance gates pending Step 5 registration; visual verification on actual panels covered in Step 7.)

## Step 5 — `MasterPaneTreeDelegate` class

In the same `master_pane_delegate.py` file, subclass `MasterPaneDelegate` as `MasterPaneTreeDelegate`. Extend with:

### 5.1 Branch indicator override

In `paint()` or a sibling method (`drawBranches`, depending on Qt's tree-view delegate dispatch), replace Qt's default branch indicator with the Lucide chevron icons:

- Collapsed row: Lucide `chevron-right` at 12px in `t("color.neutral.500")`.
- Expanded row: Lucide `chevron-down` at 12px in `t("color.neutral.500")`.

Icons resolved via the `lucide()` loader from `ui/icons.py`. The icon is rendered at the leading edge of the row, positioned according to the row's indentation depth.

### 5.2 Indentation respect

Tree views set `indentation` (the QTreeView property) — slice B's prompt verifies the current value on the Topics panel and updates to `t("space.4")` (16px) if it differs. The selected-state left accent bar (inherited from `MasterPaneDelegate`) renders at `option.rect.left()`, which respects the indentation — verify visually.

### 5.3 Acceptance verification (Step 5)

- `from crmbuilder_v2.ui.widgets.master_pane_delegate import MasterPaneTreeDelegate` succeeds.
- (Visual verification on Topics panel covered in Step 7.)

## Step 6 — Centralized delegate registration in `ListDetailPanel`

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py`:

### 6.1 Class attribute for delegate override

Add a class attribute `master_pane_delegate_cls: type[QStyledItemDelegate] = MasterPaneDelegate`. Subclasses (specifically the Topics panel) can override this to `MasterPaneTreeDelegate` via a class-level assignment.

### 6.2 Registration in `__init__`

After the master view is constructed (the existing `_create_master_widget` call site), instantiate the delegate from `self.master_pane_delegate_cls` and attach via `self.master_view.setItemDelegate(delegate)`. Pass the panel's soft-deleted-visibility callable if one is available (slice B's prompt-runner determines how to source this — likely a method on the panel like `self._is_soft_deleted_visible` which returns the current state of the panel's show-deleted toggle).

### 6.3 Topics panel override

In `crmbuilder-v2/src/crmbuilder_v2/ui/panels/topics.py`, add the class attribute override:

```python
class TopicsPanel(ListDetailPanel):
    master_pane_delegate_cls = MasterPaneTreeDelegate
```

(plus the necessary import).

### 6.4 Acceptance verification (Step 6)

- Every `ListDetailPanel` subclass panel renders its master pane through `MasterPaneDelegate` automatically.
- The Topics panel specifically renders through `MasterPaneTreeDelegate` (visible by chevron-icon branch indicators).
- No panel renders with Qt's default selection blue.

## Step 7 — `VersionedPanel` and other-base panel fallback registration

Per the Step 1 audit, register the delegate explicitly on every panel that does NOT inherit from `ListDetailPanel`. Confirmed targets: Charter (`panels/charter.py`) and Status (`panels/status.py`), both via `VersionedPanel`.

Two approaches; slice B's prompt-runner picks whichever is cleaner given `VersionedPanel`'s actual structure:

- **Option α:** Add the same class-attribute + registration pattern to `VersionedPanel.__init__()`. Centralized for the two affected panels.
- **Option β:** Per-panel registration in each of `charter.py` and `status.py`. Surgical.

If `VersionedPanel` has a master-pane view following a uniform pattern, Option α. If the two panels construct their views differently, Option β.

If the Step 1 audit surfaced any panel outside `ListDetailPanel` and `VersionedPanel` (NOT expected in v0.6 based on the implementation plan), per-panel registration handles them too.

### 7.1 Acceptance verification (Step 7)

- Open the Charter panel: the master-pane row rendering matches the other panels (selected state shows the accent bar + tint + medium-weight text).
- Open the Status panel: same.
- Confirm by inspection that no panel falls back to Qt's default selection blue.

## Step 8 — Visual regression smoke

Run the application and visit every panel in turn. For each panel, verify:

- Master-pane rows render with `color.neutral.0` background, no alternating shading.
- Hovering a row tints it `color.neutral.100`.
- Selecting a row applies the selected-state vocabulary (left accent bar, tinted background, medium-weight text).
- Column headers render in semibold caption-size text per the slice A QSS rule.
- 1px row dividers between rows are visible.
- The Topics panel additionally shows Lucide chevrons replacing the default branch indicator; indentation is 16px per level.

If a panel exists that has a soft-deleted-toggle (e.g., Domains, Entities, Processes), toggle the option on and verify a soft-deleted row renders with `color.neutral.500` text plus leading `trash-2` icon in the identifier column.

Verify the v0.5 test suite still passes: `uv run pytest tests/crmbuilder_v2/ -v`.

## Commit message template

```
v2: ui v0.6 slice B — sidebar + master-pane delegate

Delivers the shared visual vocabulary per DEC-093: 3px left
accent bar + color.accent.subtle background + medium-weight
text, applied uniformly to sidebar entries and master-pane
rows across all panels.

Sidebar (ui/sidebar.py):
- 220px width with color.neutral.100 background and right-
  edge hairline
- Group headers in semibold caption-size, color.neutral.500
- Entries at 32px height with body-size text
- Stale-indicator dot recolored from legacy #1F3864 to
  color.accent.default (#1F5FBF)
- SidebarItemDelegate handles selected/hover/focused custom
  rendering per DEC-093

Master-pane delegate (ui/widgets/master_pane_delegate.py):
- MasterPaneDelegate(QStyledItemDelegate) handles row height
  (28px), dividers, hover/selected/focused state, soft-
  deleted-row treatment, identifier-column mono font
- MasterPaneTreeDelegate(MasterPaneDelegate) extends with
  Lucide chevron branch indicators and 16px indentation
- Takes is_soft_deleted_visible callable so panels pass their
  own toggle state without coupling delegate to panel internals

Registration:
- Centralized via ListDetailPanel.__init__() with master_pane_-
  delegate_cls class attribute for override; covers 10 panels
- Topics panel overrides to MasterPaneTreeDelegate
- VersionedPanel-based panels (Charter, Status) get equivalent
  registration via VersionedPanel.__init__()
- No panel renders with Qt's default selection blue

Next: slice C (panel retrofits + ReferencesSection).

No schema changes; no API changes; v0.5 test suite remains green.
```

After committing, run:

- `git push origin main`
- Notify Doug that slice B is complete and ready for screenshot capture per the protocol in implementation plan §7. Doug captures and commits four screenshots to `styling-screenshots/slice-B/`: `sidebar.png` (one selected entry, one hovered), `master-pane-table.png` (any table-view panel showing the selected-state), `master-pane-tree.png` (Topics panel showing chevrons + indentation), `master-pane-soft-deleted.png` (any panel with show-deleted toggled on showing a soft-deleted row).

## Out of slice

- Panel chrome retoken beyond slice A's `list_detail_panel.py` base hooks (slice C).
- Detail-pane label-above form layout (slice C).
- Field state coverage (slice C).
- ReferencesSection sub-sectioned rendering (slice C).
- Notes collapsible toggle visual treatment (slice C).
- Internal context strip on record-editing dialogs (slice D).
- Button categories beyond Secondary default (slice D).
- Form-control state coverage (slice D).
- Inline form-field error styling (slice D — final state coverage).
- Status / error / warning surfaces (slice E).
- Crash banner re-skin (slice E).
- `__version__` bump (slice F).
- README v0.6 release note (slice F).
- WCAG contrast test module (slice F).

---

*End of slice B prompt.*
