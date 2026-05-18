# CRMBuilder v2 — Styling Design Pass

**Last Updated:** 05-16-26 15:30
**Status:** In progress — Conversation 1 (design pass)
**Predecessor:** Styling Conversation 1 kickoff (`styling-conversation-1-kickoff.md`)
**Workstream:** Styling design pass — see `styling-workstream-plan.md`
**Tracks:** PI-001 (reopened as parallel workstream per DEC-076)

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-16-26 15:30 | Doug Bower / Claude | Initial capture during Styling Conversation 1. Section 1 (design tokens) drafted as decisions are confirmed; sections 2–4 stubbed. |

---

## Change Log

**Version 0.1 (05-16-26 15:30):** Initial creation during Styling Conversation 1. Captures the first wave of token-layer decisions: density target (Default), token-naming structure (theme-keyed), accent color (`#1F5FBF` steely blue), 9-step cool-gray neutral scale, status color draft, font family (Inter Variable bundled), monospace (JetBrains Mono Variable bundled), and the derived spacing / radius / typography scales. Sections 2 (component visual decisions), 3 (application priorities), and 4 (acceptance criteria) are stubbed for completion later in the conversation.

---

## 1. Design Tokens

### 1.1 Density and spacing

**Density target: Default.** Workstation context (3× 4K monitors, daylight desk use) rules out *compact* — at high pixel density the spacing rhythm Qt assumes is already tight, and squeezing further makes characters small enough to hurt scan speed rather than help it. It also rules out *comfortable* — at 4K resolution there is no scarcity of pixels, and "comfortable" wastes them. Default sits in the middle, native to Qt, and renders crisply across all three displays.

**Spacing scale (4px base unit).**

| Token | Value | Typical use |
|---|---|---|
| `space.0` | 0 | Zeroed margins/padding |
| `space.1` | 4px | Hairline separation; icon-to-label gap |
| `space.2` | 8px | Tight grouping; within-cell padding |
| `space.3` | 12px | Form row gap; between master and detail pane |
| `space.4` | 16px | Panel chrome padding; dialog content padding |
| `space.5` | 20px | Dialog outer margin |
| `space.6` | 24px | Section break |
| `space.8` | 32px | Vertical rhythm between major detail-pane sections |
| `space.10` | 40px | Large standalone whitespace |
| `space.12` | 48px | Extra-large standalone whitespace |

**Derived sizes.**

- List row height (master panes — `QTableView`, `QTreeView`, `QListView`): **28px**.
- Form field height (text inputs, combos): **28px**.
- Button padding: **6×14px** (vertical × horizontal). Button minimum width 88px so "Save" and "Cancel" line up.
- Panel chrome padding: **16px** on all sides of the panel content area.
- Inter-pane spacing (master ↔ detail): **12px**.
- Dialog margins: **20px** outer, **12px** between form rows, **16px** above the button row.

### 1.2 Color tokens

#### 1.2.1 Structure

**Theme-keyed.** Color tokens live in a dict keyed by theme name; consumers read via a small accessor. Single light theme today (key `"light"`). Dark-mode values are not authored in this pass; the structure does not preclude adding them as a future PI without renaming or refactoring consumers. The structural choice costs ~5 LOC today; the alternative (flat tokens) would require renaming every color reference in code if dark mode is ever added.

#### 1.2.2 Accent

| Token | Value | Notes |
|---|---|---|
| `color.accent.default` | `#1F5FBF` | Primary action color. Slightly brighter and more saturated than the legacy `#1F3864` navy stub; same cool-blue family, more deliberate. |
| `color.accent.hover` | `#2A6CCE` | Default + 6% lightness. Hover on accent-colored surfaces (primary button hover, sidebar entry hover when selected). |
| `color.accent.pressed` | `#184F9F` | Default − 6% lightness. Mouse-down state. |
| `color.accent.subtle` | `#E8F0FB` | Default mixed 92% with `neutral.0`. Tinted-background treatment for selected sidebar entry and selected list rows. |
| `color.accent.focusring` | `#1F5FBF` at 40% alpha | Outline ring on focused inputs and buttons. |

#### 1.2.3 Neutral grays

Cool-gray family, paired with the cool-blue accent.

| Token | Value | Typical use |
|---|---|---|
| `color.neutral.0` | `#FFFFFF` | Modal backgrounds; contrast surfaces. |
| `color.neutral.50` | `#F7F9FB` | Primary panel surface — the dominant "page" color. |
| `color.neutral.100` | `#EEF1F5` | Subtle surface — alternating rows, sidebar background, read-only field background (retires the legacy `#f4f4f4`). |
| `color.neutral.200` | `#DDE3EA` | Hairline borders, table cell dividers, separator lines. |
| `color.neutral.300` | `#C1CAD4` | Disabled control fill; placeholder text. |
| `color.neutral.500` | `#7A8694` | Secondary text and caption text (retires the legacy `#888`); inactive icon color. |
| `color.neutral.700` | `#3F4854` | Read-only field text (retires the legacy `#444` and `#666`). |
| `color.neutral.800` | `#272D36` | Body text default. |
| `color.neutral.900` | `#0F1318` | High-emphasis text; headings. |

The legacy four ad-hoc grays (`#f4f4f4`, `#444`, `#666`, `#888`) currently in `panels/*.py`, `dialogs/*.py`, and `base/crud_dialog.py` map to the new scale during the styling-build retrofit:

- `#f4f4f4` → `color.neutral.100`
- `#666` → `color.neutral.700`
- `#888` → `color.neutral.500`
- `#444` → `color.neutral.700`

#### 1.2.4 Status

Drafted values; pushback welcome if any read off.

| Token | Value | Notes |
|---|---|---|
| `color.danger.default` | `#C0392B` | Destructive button fill (refines the legacy `#c1272d` on `dialogs/reference_delete.py` and `base/crud_dialog.py`). Slightly less orange-shifted to harmonize better with the cool blue accent. |
| `color.danger.text` | `#A8281C` | Inline error text and inline warning text (retires the legacy `#B22222` in `crud_dialog.py` and `panels/processes.py`). |
| `color.danger.subtle` | `#FBEBE8` | Tinted-background treatment for error-state form fields and inline error rows. |
| `color.warning.default` | `#B0731A` | Amber. Used sparingly — v2 has few true "warning" states today; the soft-deleted-domain inline message on Processes is the canonical example. |
| `color.warning.subtle` | `#FBF2E0` | Tinted-background treatment for warning callouts. |
| `color.success.default` | `#2D7A4D` | Green. Reserved for explicit success affirmations (rare in v2 — possibly the propose-verify status-transition acceptance moment, if anywhere). |

### 1.3 Typography

**Font family: Inter Variable, bundled.** Loaded at app startup via `QFontDatabase.addApplicationFont()`. OFL-licensed; ~280 KB binary committed to the repo. Identical rendering across macOS, Windows, Linux — no per-platform font-metric divergence.

**Monospace: JetBrains Mono Variable, bundled.** Same mechanism; OFL-licensed; ~250 KB. Used today only on About-dialog path values; future surfaces (config readouts, JSON previews, identifier-as-code in dense table contexts) inherit it for free.

**Size scale.**

| Token | Value | Use |
|---|---|---|
| `font.size.caption` | 12px | Captions, audit timestamps, sub-secondary text. |
| `font.size.small` | 13px | Master-pane row text; secondary form-field labels. |
| `font.size.body` | 14px | Default body, form fields, dialog text. |
| `font.size.body_large` | 16px | Detail-pane primary field values when they need emphasis. |
| `font.size.heading_3` | 18px | Detail-pane section headers; dialog section labels. |
| `font.size.heading_2` | 22px | Dialog title bars. |
| `font.size.heading_1` | 28px | Reserved — no current surface uses it; available for a future "splash" or About-dialog hero treatment. |

**Weight scale (Inter Variable axis).**

| Token | Value | Use |
|---|---|---|
| `font.weight.regular` | 400 | Default body. |
| `font.weight.medium` | 500 | Emphasized labels; table column headers; sidebar entry labels. |
| `font.weight.semibold` | 600 | Headings; dialog titles. |
| `font.weight.bold` | 700 | Used sparingly — primary action buttons, sidebar group headers. |

**Line-height scale.**

| Token | Value | Use |
|---|---|---|
| `font.line.tight` | 1.2 | Headings, single-line button labels. |
| `font.line.normal` | 1.45 | Default body. |
| `font.line.relaxed` | 1.6 | Long-form prose (rare in v2; possibly the delete-dialog clarifying note). |

### 1.4 Radius and border tokens

Drafted; pushback welcome.

| Token | Value | Use |
|---|---|---|
| `radius.none` | 0px | Borderless surfaces — sidebar entries, table cells. |
| `radius.subtle` | 3px | Form field corners, button corners, sidebar group headers. |
| `radius.default` | 6px | Dialog corners, callout boxes, tinted-background message rows. |
| `radius.large` | 10px | Reserved — no current surface uses it. |
| `border.hairline` | 1px solid `color.neutral.200` | Table dividers, panel separators, form-section separators. |
| `border.field` | 1px solid `color.neutral.300` | Input/combo box borders at rest. |
| `border.field_focus` | 1px solid `color.accent.default` plus `color.accent.focusring` outline | Input/combo box focused state. |
| `border.danger` | 1px solid `color.danger.default` | Validation error on a field. |

### 1.5 Elevation / depth

**Posture: elevation only on modals.** The rest of the app — sidebar, panels, master pane, detail pane, fields, buttons — shares one z-plane and stays fully flat. Modals (every `QDialog` subclass: CRUD dialogs, references attach/delete, version-replace, About) get a single elevation treatment via `QGraphicsDropShadowEffect` (Qt's built-in effect, not custom paint events — within the workstream plan's QSS-supplemented-by-built-in-effects posture). Plus a subtle full-window backdrop overlay when a modal is active.

Single elevation profile, applied uniformly:

| Token | Value | Use |
|---|---|---|
| `shadow.dialog` | Y-offset 4px, X-offset 0px, blur radius 16px, color `color.neutral.900` at 25% alpha | Drop shadow on every modal dialog. |
| `overlay.modal_backdrop` | Full-window overlay, color `color.neutral.900` at 8% alpha, fade-in ~150ms when modal opens | Disambiguates modal foreground from underlying panel. |

Rationale: modal disambiguation is the single highest-value depth cue in an otherwise flat app. One token uniformly applied keeps the discipline; going further (popup-shadow tier, focused-button micro-elevation) buys polish at the cost of platform-rendering inconsistency.

`radius.dialog` is already drafted in §1.4 at 6px, which pairs well with the soft shadow.

### 1.6 Icon library

**Lucide.** ISC-licensed; ~1,400 icons; single regular-weight stroke (2px uniform). Distributed as SVGs and bundled per-icon — the set in the repo grows additively as components need new icons, not as a bulk import.

- **Storage path.** `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/lucide/{kebab-case-name}.svg`.
- **Loading helper.** Small wrapper around `QSvgRenderer` that returns `QIcon` at requested size, color-tinted via the token system. Sketch:

  ```python
  def lucide(name: str, *, size: int = 16, color_token: str = "color.neutral.700") -> QIcon: ...
  ```

- **Default icon size.** 16px (matches body text height closely; readable at 4K HiDPI).
- **Color application.** Icons are not pre-colored at the SVG layer; the loader recolors at runtime using the design tokens so an icon in a disabled button uses `color.neutral.300` and the same icon in a primary button uses `color.neutral.0`, from one SVG asset.

Lucide's minimal stroke pairs cleanly with Inter and the restrained color direction. Phosphor's warmer rounded weight was the alternative considered; Lucide won on aesthetic match.

The initial bundled set is the icons the v0.5/v0.6 styling build actually wires up, not a speculative pre-bundle. First wave anticipated: `pencil` (Edit), `trash-2` (Delete), `rotate-ccw` (Restore), `external-link` (Go to references), `copy` (Copy identifier), `plus` (Add / New), `x` (Close / Dismiss), `chevron-right`/`chevron-down` (collapsible toggles), `circle-alert` (warning), `circle-x` (error), `check` (success affirmation).

---

## 2. Component Visual Decisions

To be drafted as decisions are confirmed in the second half of Conversation 1.

### 2.1 Sidebar

The sidebar is the most-used surface and the most visible application of the accent treatment. Implemented as `QListWidget` per current code; visual treatment applied via QSS plus a small `setStyleSheet` block on the widget instance and per-item rendering hints. Two group headers (Governance, Methodology) plus 12 selectable entries (8 governance, 4 methodology, growing to 5 methodology when v0.5's engagement panel lands).

**Container.**

- Background: `color.neutral.100` (the subtle surface). Distinct from panel background (`color.neutral.50`) so the sidebar reads as a separate region.
- Width: 220px. Enough for "CRM Candidates" (the longest current entry) plus the stale-indicator dot at 14px body text without truncation.
- Right edge: 1px hairline border in `color.neutral.200` anchors the boundary against the panel area.
- Top padding: `space.4` (16px) inside the sidebar before the first group header. Bottom padding: `space.4`.

**Group headers** (Governance, Methodology).

- Non-selectable list items.
- Text: `font.size.caption` (12px), `font.weight.semibold`, `color.neutral.500`, letter-spacing `+0.04em` (reads as small-caps-style without being uppercased).
- Padding: `space.2` (8px) top, `space.1` (4px) bottom, `space.3` (12px) horizontal.
- Vertical space `space.4` (16px) above each group header beyond the first. No separator line between groups — spacing alone carries the break.

**Entries.**

| State | Visual |
|---|---|
| Default | Padding `space.2` × `space.3` (~32px tall). `font.size.body` (14px), `font.weight.regular`, `color.neutral.800`. Full-width. No background fill. |
| Hover | Background `color.neutral.200`. Text unchanged. Cursor pointer. No accent bar. |
| Selected | 3px-wide left accent bar (`color.accent.default`) flush against the left edge. Background `color.accent.subtle` (`#E8F0FB`). Text `color.neutral.900` at `font.weight.medium`. |
| Focused (keyboard) | Same visuals as Selected, plus a 1px focus ring (`color.accent.focusring`, 40% alpha) drawn 2px outside the entry. |
| Disabled | Reserved. Text `color.neutral.300`; no hover; no cursor change. |

**Stale-indicator dot.**

- Existing 8px circle preserved, right-aligned in the entry, vertically centered.
- Color flips from legacy navy `#1F3864` to `color.accent.default` (`#1F5FBF`) — same effective hue, formally tokenized via the design tokens module.
- On hover and selected entries the dot remains visible. Build-time refinement: the dot may need a 1px `color.neutral.0` halo on the tinted (selected/hover) backgrounds to maintain contrast. Refinement is acceptable to make at QSS-apply time.

### 2.2 Panel chrome and `ListDetailPanel` pattern

No panel-level title strip. The sidebar's selected entry indicates which panel is active; a header strip would duplicate that signal and consume vertical space that's more useful for content. Per-panel toolbar affordances (show-deleted toggle, etc.) continue to render at the top of the master pane area as they do today, not at the panel chrome level.

**Container.**

- Background: `color.neutral.50` (the primary panel surface).
- Outer padding: `space.4` (16px) on all sides inside the panel content area.
- No panel-level border. The sidebar's right hairline border (§2.1) carries the left boundary; the window frame carries top/right/bottom.

**Master / detail split.**

- Continue using the existing `QSplitter` (v0.3 mechanism); the splitter remains user-adjustable.
- Default proportion: 45/55 master/detail.
- Splitter handle: `space.3` (12px) wide; handle background `color.neutral.100`; a 1px vertical hairline divider in `color.neutral.300` drawn down the center of the handle so it reads as a deliberate separation, not a margin.
- Hover over the handle: cursor changes to `SizeHorCursor` (Qt default); no color change on the handle itself.

### 2.3 Master pane (`QTableView` / `QTreeView` / `QListView`)

Middle posture: row dividers for structure, no alternating shading. Reuses the sidebar's selected-state vocabulary (left accent bar + tint) so "this row is selected" reads consistently across both surfaces.

Implemented per-panel via a small `QStyledItemDelegate` subclass that handles the selected-row left-bar treatment plus the cell padding; the rest is QSS on the view widget.

**Background and structure.**

- View background: `color.neutral.0` (white). Distinct from the panel background (`color.neutral.50`) so the table reads as a contained data region.
- Row dividers: 1px hairline below each row in `color.neutral.200`.
- No alternating row shading.
- No vertical cell dividers.

**Column headers.**

- Background: `color.neutral.100`.
- Bottom hairline: 1px solid `color.neutral.200`.
- Text: `font.size.small` (13px), `font.weight.semibold`, `color.neutral.700`.
- Padding: `space.2` × `space.3` (8 × 12px).
- Sort indicator: Lucide `chevron-up` / `chevron-down` at 12px, color `color.neutral.500`, right-aligned in the active column's header cell.

**Rows.**

- Height: 28px (per §1.1 density).
- Text: `font.size.body` (14px), `font.weight.regular`, `color.neutral.800`, padding `space.2` × `space.3`.
- Identifier column specifically renders in `font.family.mono` (JetBrains Mono) at `font.size.small` (13px) so identifiers like `DEC-077` align cleanly down the column by their numeric suffix.

**Row states.**

| State | Visual |
|---|---|
| Default | Background `color.neutral.0`. Text `color.neutral.800`. |
| Hover | Background `color.neutral.100`. Text unchanged. Cursor pointer. No accent bar. |
| Selected | 3px-wide left accent bar (`color.accent.default`) flush against the row's left edge. Background `color.accent.subtle`. Text `color.neutral.900` at `font.weight.medium`. |
| Focused (keyboard) | Same visuals as Selected, plus a 1px focus ring (`color.accent.focusring`, 40% alpha) drawn 1px inside the row's bounds (constrained inside the cell area, not crossing the row divider). |
| Soft-deleted (when "include deleted" is on) | Text `color.neutral.500` (50% effective contrast vs. live rows). Small Lucide `trash-2` icon at 14px rendered in the identifier column's leading edge, before the identifier text. |

**Empty state.**

Centered vertically and horizontally in the table area:

- Primary line: "No records yet" — `font.size.body` (14px), `color.neutral.500`, `font.weight.regular`.
- Secondary hint line: per-panel context (e.g., "Right-click to add a domain" on the Domains panel) — `font.size.small` (13px), `color.neutral.500`, `space.2` below the primary line.
- No illustration.

**Tree view variant** (Topics panel).

All of the above applies. Additionally:
- Expand/collapse indicators use Lucide `chevron-right` (collapsed) and `chevron-down` (expanded) at 12px, color `color.neutral.500`, rendered in place of Qt's default branch indicator.
- Indentation per level: `space.4` (16px).
- The accent left-bar on selected rows respects the indentation — bar starts at the row's left edge, not at the indented content edge.

### 2.4 Detail pane

The detail pane renders the selected record's full content: identifier, scalar fields, status, optional notes, and the `ReferencesSection` showing related records. Implemented per current code as a vertically-flowing form area; visual treatment applied via QSS plus per-field widget tokens.

**Form layout: label-above.** Labels render above their fields rather than to the left of them. The `QFormLayout` in `crud_dialog.py` and the per-panel detail builders are updated to use this layout. Reasoning: Default density gives enough vertical room; label-above scans faster when labels vary in length, and lets the field claim the full pane width without competing with the label column.

**Form rows.**

- Label: `font.size.small` (13px), `font.weight.medium`, `color.neutral.700`, with `space.1` (4px) below the label before the field.
- Field: 28px height (per §1.1).
- Row spacing: `space.3` (12px) between rows.
- Required-field marker: small Lucide `asterisk` icon at 10px in `color.danger.text`, rendered immediately after the label text. No "Required" word.

**Editable field treatment.**

| State | Visual |
|---|---|
| Default | Background `color.neutral.0`. Border `border.field` (1px `color.neutral.300`). Text `color.neutral.800`. |
| Focused | Border `border.field_focus` (1px `color.accent.default`) plus the `color.accent.focusring` outline drawn 2px outside the field. |
| Error | Border `border.danger` (1px `color.danger.default`). |
| Disabled | Background `color.neutral.100`. Border `color.neutral.200`. Text `color.neutral.300`. |

**Read-only field treatment** (identifiers, audit timestamps, computed fields).

- Background: `color.neutral.100`.
- No visible border (or `border.hairline` if separation is needed for the layout).
- Text: `color.neutral.700`.
- Visually distinct from disabled (read-only = "this is a value, not an input"; disabled = "this is an input that's inactive").

**Status combo.**

- Standard combo treatment using the editable-field tokens above.
- Per the propose-verify gate, only valid status successors render in the dropdown.
- Below the combo, with `space.1` of margin: a small caption line in `font.size.caption` (12px), `color.neutral.500`, reading "Valid transitions: <enum-1>, <enum-2>". Optional refinement; easily dropped at build time if it crowds the pane.

**Notes collapsible toggle.**

- Replaces the existing `border: none` flat `QToolButton` treatment.
- Toggle row: Lucide `chevron-right` (collapsed) / `chevron-down` (expanded) at 14px in `color.neutral.700`, followed by the label "Notes" in `font.size.small` (13px), `font.weight.medium`, `color.neutral.700`.
- Click anywhere on the toggle row (icon or label) collapses/expands.
- When expanded, the notes field renders below with `space.2` (8px) vertical separation.

**Section grouping.**

Sections within the detail pane (identifier+name+status block; description; notes; ReferencesSection) are separated by `space.6` (24px) vertical space. No section dividers — spacing alone carries the break, matching the sidebar group convention.

**Action button row** (Save / Cancel / Delete / Restore — exact composition depends on the panel and the record's state).

- Anchored to the bottom of the detail pane with `space.4` (16px) padding above.
- Right-aligned cluster: Cancel first, then Save (or Restore) closest to the right edge, with `space.2` (8px) between.
- Delete left-aligned, visually separated from the right-aligned constructive actions to reduce accidental clicks.
- Button-specific styling specified in §2.5.

**`ReferencesSection` rendering: sub-sectioned plain list.**

Each relationship kind active on the record gets a small sub-section header and a list of entries below it. The Decisions detail pane for DEC-076, for example, would render:

```
Decided in
  SES-025  v0.5-orientation conversation close-out
Is about
  PI-001   Full styling design pass per DEC-024
```

- Sub-section header: `font.size.small` (13px), `font.weight.semibold`, `color.neutral.700`, with `space.2` below the header before the first entry. The header is the relationship kind, rendered in title case ("Decided in", "Is about", "Hands off to", "Receives from", "Supersedes", "Superseded by", "References").
- Sub-sections separated by `space.4` (16px) of vertical space.
- Entry row: `font.size.body` (14px), `color.neutral.800`. Identifier rendered in `font.family.mono` (JetBrains Mono) at `font.size.small` (13px), `color.neutral.700`. Title/summary text rendered after the identifier in regular weight, `color.neutral.800`. `space.3` between identifier and title. `space.1` vertical padding per row.
- Entry hover: subtle background tint `color.neutral.50`. Cursor pointer.
- Entry right-click: opens the context menu with `Delete reference` and `Go to {target identifier}` actions per the v0.3 PRD pattern.
- `Add reference` button: text-only button, Lucide `plus` icon at 14px + label "Add reference" in `font.size.small` (13px), `font.weight.medium`, `color.accent.default`. No background, no border. Positioned below the last sub-section with `space.3` of vertical space above it.
- Empty state (no references registered): single line "No references" in `color.neutral.500`, `font.size.small`, followed by the `Add reference` button on the next row.

Rationale for the sub-sectioned plain list: ReferencesSection is reference material the user scans, not a primary editing surface. Plain sub-sectioned lists scan fastest, scale gracefully to many references on a single record, and don't compete visually with the rest of the detail pane.

### 2.5 Buttons

Five button categories, each with five states (default, hover, pressed, focused, disabled). All buttons share base geometry: padding `space.1` × `space.3` plus 2px (effectively 6 × 14px), `radius.subtle` (3px), minimum width 88px (so "Save"/"Cancel" line up nicely in dialog button rows), `font.size.body` (14px), `font.weight.medium`.

**Primary** — Save, primary constructive actions, "Save and continue" affordances.

| State | Visual |
|---|---|
| Default | Background `color.accent.default`. Text `color.neutral.0`. No border. |
| Hover | Background `color.accent.hover`. |
| Pressed | Background `color.accent.pressed`. |
| Focused | Default visuals + `color.accent.focusring` outline drawn 2px outside. |
| Disabled | Background `color.neutral.300`. Text `color.neutral.500`. No hover/pressed reaction. |

**Secondary** — Cancel, secondary affordances, "Apply filter," "Reset" in dialogs.

| State | Visual |
|---|---|
| Default | Background transparent. Border 1px `color.neutral.300`. Text `color.neutral.700`. |
| Hover | Background `color.neutral.100`. Border unchanged. |
| Pressed | Background `color.neutral.200`. |
| Focused | Default visuals + focus ring outside. |
| Disabled | Background transparent. Border `color.neutral.200`. Text `color.neutral.300`. |

**Destructive** — Delete buttons in dialogs and on detail panes. Retires the legacy `#c1272d` red on `dialogs/reference_delete.py` and `base/crud_dialog.py`.

| State | Visual |
|---|---|
| Default | Background `color.danger.default`. Text `color.neutral.0`. No border. |
| Hover | Background `color.danger.default` darkened 6%. |
| Pressed | Background `color.danger.default` darkened 12%. |
| Focused | Default visuals + focus ring (in `color.danger.default` at 40% alpha rather than accent — focus ring matches the button's hue). |
| Disabled | Background `color.neutral.300`. Text `color.neutral.500`. Retires the legacy `#b6868a` disabled-destructive treatment. |

**Text / Link** — `Add reference` affordances, "Go to references" in context menus, in-prose action links.

| State | Visual |
|---|---|
| Default | Background transparent. No border. Text `color.accent.default`, `font.weight.medium`. |
| Hover | Text underlined. |
| Pressed | Text `color.accent.pressed`. |
| Focused | Focus ring around the text bounds. |
| Disabled | Text `color.neutral.300`. No underline on hover. |

**Icon-only** — toolbar refresh, show-deleted toggle, future small affordances.

- Square: 28×28px (matches field height).
- Default: background transparent, icon `color.neutral.700`.
- Hover: background `color.neutral.100`.
- Pressed: background `color.neutral.200`.
- Focused: focus ring outside.
- Disabled: icon `color.neutral.300`.
- Tooltip required (Qt's standard `setToolTip()` mechanism); icons without labels need text accessibility.

### 2.6 Form controls

The field treatment tokens are already specified in §2.4 (editable, focused, error, disabled, read-only). This section covers control-specific behavior.

**Text input** (`QLineEdit`).

- Geometry and state visuals per §2.4.
- Placeholder text: `color.neutral.500`, regular weight, non-italic.
- Inline error message rendered below the field with `space.1` of margin; `font.size.caption` (12px), `color.danger.text`.

**Multi-line text** (`QTextEdit`, `QPlainTextEdit` for description, notes, long-form fields).

- Same border/background/focus treatment as text input.
- Minimum height: 80px (~3 visual rows).
- Vertical scrollbar appears when content exceeds height; uses OS-default scrollbar (see below).
- Read-only multi-line uses the read-only background + text tokens.

**Combo box** (`QComboBox`).

- Geometry: 28px height, full available row width.
- Right-side affordance: Lucide `chevron-down` at 14px in `color.neutral.500`, padded `space.2` from the right edge.
- Dropdown popup: background `color.neutral.0`, border 1px `color.neutral.300`, `radius.subtle`, drop shadow `shadow.dialog` (popup is effectively a small modal surface).
- Dropdown items: 28px height, padding `space.2` × `space.3`, `font.size.body`, `color.neutral.800`. Hover item: background `color.neutral.100`. Selected item (current value): background `color.accent.subtle`, text `color.neutral.900`.
- Disabled combo: per §2.4 disabled treatment; chevron icon in `color.neutral.300`.

**Checkbox** (`QCheckBox`).

- 16×16px square box at field-row leading edge, with the label to the right.
- Unchecked default: background `color.neutral.0`, border 1px `color.neutral.300`, `radius.subtle`.
- Checked: background `color.accent.default`, border `color.accent.default`, Lucide `check` icon at 12px in `color.neutral.0`.
- Hover (unchecked): border `color.neutral.500`.
- Hover (checked): background `color.accent.hover`.
- Focused: focus ring outside the 16×16 box.
- Disabled: background `color.neutral.100`, border `color.neutral.200`, check icon (if checked) in `color.neutral.300`.

**Radio button** (`QRadioButton`) — reserved; no current v2 surface uses radio buttons. If introduced, mirror the checkbox treatment with a circular dot instead of a check icon.

**Date / time picker** — reserved; no current v2 surface uses a date picker (audit timestamps are auto-set by the server and rendered as read-only text). If introduced, use a styled combo-like trigger plus a popup calendar matching the dropdown treatment above.

**Spin box** (`QSpinBox`) — reserved; not currently used in v2.

**Scrollbars.**

- OS-default. Per the kickoff's settled-by-convention guidance, scrollbar visual treatment is left to the platform unless friction surfaces during the build.
- Inside dropdown popups and dialog scrollable areas, the OS scrollbar is acceptable even though it visually breaks the otherwise-themed surface; the build phase may revisit if the visual mismatch is severe.

**Tab order and focus.**

Tab order across a form: top-to-bottom following the form-row order, with Save → Cancel → Delete at the end (matching the visual order). Per Qt convention, `Tab` advances and `Shift+Tab` reverses. Initial focus on a dialog: the first editable field, not the Save button.

### 2.7 Dialogs

Container chrome falls out from tokens: `radius.dialog` (6px) where the platform renders it, drop shadow per `shadow.dialog`, modal backdrop per `overlay.modal_backdrop` (§1.5). All `QDialog` subclasses inherit this treatment.

**Container.**

- Background: `color.neutral.0` (white).
- Inner padding (excluding the context strip when present): `space.5` (20px) on all sides.
- OS title bar retained — frameless dialogs are out of scope.

**Internal context strip** (record-editing dialogs only — not create-new dialogs, not About, not delete-confirm).

- Anchored at the top of the dialog body, flush against the OS title bar.
- Background: `color.neutral.100`. Padding: `space.3` (12px) all sides. Hairline 1px `color.neutral.200` below.
- Content: identifier in `font.family.mono` at `font.size.small` (13px), `color.neutral.700`, `font.weight.medium`. Then `space.3` horizontal space. Then the record's name/title in `font.size.body` (14px), `color.neutral.800`, regular weight. Title truncates with ellipsis on overflow.
- Reasoning: anchors the user to "which record am I editing" without requiring them to look at the OS chrome (which is variably visible across Linux compositors and macOS focus states).

**Form area.**

Uses §2.4 detail-pane form treatment — label-above, `space.3` between rows, full state coverage on fields.

**Action button row.**

Anchored at the bottom of the dialog body, separated from the form by `space.4` (16px) of vertical space.

- Right-aligned cluster: Cancel, then the primary action (Save / Apply / Restore) closest to the right edge, with `space.2` between.
- Destructive action (Delete on edit dialogs) left-aligned, visually separated from the right-aligned constructive actions.

**Delete-confirm dialogs** (used by `dialogs/reference_delete.py`, `dialogs/entity_crud_delete.py`, and the per-entity delete dialogs).

- No context strip (the prose contains the deletion target inline).
- Body content: single paragraph explaining the deletion and irreversibility, in `font.size.body` (14px), `color.neutral.800`, `font.line.relaxed` (1.6).
- Destructive button (per §2.5) right-aligned; Cancel sits to its left.

### 2.8 About dialog

Modest-showcase treatment. The About dialog is the natural identity moment in the application; the wordmark and tagline mark it as deliberate without requiring a brand mark.

**Container.** Per §2.7 dialog chrome. No internal context strip (About is not a record-editing dialog). Minimum width preserved at 440px from current code.

**Header block** (top of dialog body, above the metadata table).

- Wordmark: "CRMBuilder v2" in `font.size.heading_2` (22px), `font.weight.semibold`, `color.neutral.900`.
- Tagline: short single-line tagline below the wordmark, `space.1` (4px) of vertical space between them. `font.size.small` (13px), `color.neutral.500`, regular weight.
- Header block padding: `space.4` (16px) below before the metadata table begins.

**Tagline (proposed, refine at will).** "Declarative CRM deployment and methodology authoring."

Alternatives if "declarative" reads off: "CRM deployment and methodology tooling for consultants." / "End-to-end CRM implementation tooling." Tagline is one of the few places in the application where wording carries identity weight; refine to taste at build time without re-opening the design pass.

**Metadata table** (Application / Version / API base URL / Database path / Snapshot directory).

- Renders as a vertical list, not a `QFormLayout` with label-left fields. Each metadata row is two lines:
  - Line 1: the label in `font.size.small` (13px), `font.weight.medium`, `color.neutral.500`. E.g., "API base url" (sentence-cased, not bold-capitalized).
  - Line 2: the value in `font.size.body` (14px), `color.neutral.800`. Paths and URLs in `font.family.mono` (JetBrains Mono) at `font.size.small` (13px), `color.neutral.700`.
- Vertical space `space.3` (12px) between rows.
- Values remain selectable (`Qt.TextSelectableByMouse | TextSelectableByKeyboard`) so users can copy them — preserves current behavior.

**Close button.**

- Single secondary button (per §2.5) at the bottom-right of the dialog body. Label: "Close".
- No internal action separator; the dialog's action row is just the Close button right-aligned.

### 2.9 Status, error, and warning surfaces

Three patterns: inline form-field errors, inline panel-level warnings, and the error dialog. All use the status tokens from §1.2.4.

**Inline form-field errors** (validation errors below an editable field).

- Rendered immediately below the field with `space.1` (4px) of vertical margin.
- `font.size.caption` (12px), `color.danger.text`, regular weight.
- No icon (the red field border per §2.4 carries the visual signal).
- Example: "Identifier must match pattern `DEC-\d{3}`."

**Inline panel-level warnings** (e.g., the soft-deleted-domain warning on the Processes detail pane).

- Rendered as a single-row callout above the affected field(s).
- Layout: small Lucide `circle-alert` icon at 14px in `color.warning.default`, followed by `space.2` (8px) horizontal space, followed by the warning text.
- Text: `font.size.small` (13px), `color.warning.default`, regular weight.
- The current `_WARNING_STYLE = "color: #B22222;"` on `panels/processes.py` updates to use `color.warning.default` instead of the danger-shaded red — the soft-deleted-domain message is informational ("the affiliated domain has been soft-deleted; re-affiliate or restore"), not a hard error.

**Error dialog** (`dialogs/error.py`, used as the canonical surface for surfaced API failures).

- Container per §2.7 dialog chrome. Width matches default dialog width; no context strip.
- Header inside the dialog body: leading Lucide `circle-x` icon at 18px in `color.danger.default`, followed by `space.3` horizontal space, followed by the error title in `font.size.heading_3` (18px), `font.weight.semibold`, `color.danger.text`. Header has `space.4` of vertical margin below it before the body content.
- Body content: standard dialog body treatment. If the API returned a `{data, meta, errors}` envelope with a structured `errors` array, render each error's message as a separate paragraph; if the body is a single error string, render as one paragraph.
- Footer: single "Close" secondary button right-aligned.
- The current `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` retires; the navy is replaced by the danger-text token in the header treatment above.

**Success affirmations.**

Rare in v2 — no current surface renders one. Reserved pattern if introduced: Lucide `check` icon at 14px in `color.success.default`, followed by text in `color.success.default` at `font.weight.medium`. Brief inline appearance only (e.g., after a successful save). No success modal pattern.

**Status indicators** (the stale-dot on sidebar entries; future singleton-`selected` status badges on the CRM Candidates panel).

- Stale dot: covered in §2.1 (8px circle, `color.accent.default`).
- Future status badges: small pill rendering, 18px height, `radius.subtle`, `font.size.caption` (12px), `font.weight.medium`. Per-status color treatment:
  - Active: background `color.accent.subtle`, text `color.accent.default`.
  - Selected (singleton): background `color.success.default` at 15% alpha, text `color.success.default`.
  - Declined / removed: background `color.neutral.200`, text `color.neutral.500`.
  - Deferred at build-time refinement — these aren't shipping in the styling pass unless a v0.5+ surface adds them.

### 2.10 Crash banner reconciliation

**Re-skin into the design system.** The current `crash_banner.py` ships with its own self-contained chrome (`_BANNER_BACKGROUND` plus white text and semi-transparent button styling) that predates the design system. Folding it in costs nothing visually — the danger token is unambiguously red and reads as "alarming" — and future style changes propagate automatically rather than requiring a parallel maintenance burden.

**Banner treatment.**

- Background: `color.danger.default`.
- Text: `color.neutral.0` (white), `font.size.body` (14px), `font.weight.medium`.
- Padding: `space.3` (12px) vertical × `space.4` (16px) horizontal.
- Leading icon: Lucide `circle-alert` at 16px in `color.neutral.0`, with `space.2` of horizontal space before the message text.
- Layout otherwise unchanged from current: always-on-top at the main window, full window width, persists until dismissed or the underlying error is resolved.

**Banner buttons** (the current dismiss/recovery affordances).

- Treatment: semi-transparent white background with white text — same general approach as today, retokenized.
- Default: background `color.neutral.0` at 15% alpha. Text `color.neutral.0`. Border 1px `color.neutral.0` at 25% alpha. `radius.subtle`.
- Hover: background `color.neutral.0` at 30% alpha.
- Pressed: background `color.neutral.0` at 45% alpha.
- Focused: 1px focus ring in `color.neutral.0` at 60% alpha, drawn 2px outside.

Pushback welcome — the alternative is leaving the banner intentionally outside the design system as the one "this is exceptional" surface that doesn't follow normal app rules. The reasoning would be that exceptional surfaces benefit from visual rule-breaking. I judged re-skin as the better call because (a) the danger token is already exceptional-feeling, (b) keeping it outside means permanent parallel maintenance, and (c) future style adjustments (e.g., a Windows-platform polish slice) propagate automatically.

---

## 3. Application Priorities

This section names which surfaces require careful per-surface tuning in the build phase and which can absorb the design tokens passively. The distinction informs Conversation 2's slice breakdown — the high-attention surfaces drive slice scoping; the passive surfaces aggregate into omnibus retrofit slices.

### 3.1 High attention — per-surface tuning required

These surfaces require custom widget code (subclasses of `QStyledItemDelegate`, custom paint, or new helper widgets) beyond what QSS alone provides. They warrant deliberate slice scoping and per-surface review.

- **Sidebar (§2.1).** Selected-state left accent bar requires either a custom `QListWidget` item delegate or a paint-event override. The 3px bar can't be expressed in QSS for `QListWidget` items reliably across platforms.
- **Master pane (§2.3).** Selected-row left accent bar requires a custom `QStyledItemDelegate` subclass. The soft-deleted-row visual (50% text contrast + leading `trash-2` icon in the identifier column) also belongs in this delegate.
- **ReferencesSection (§2.4).** Sub-sectioned plain-list rendering is a new layout pattern not currently in the v0.4 code. The widget needs to query references, group by relationship kind, render each sub-section with its header and entry list, and handle the per-entry hover/right-click affordances.
- **About dialog (§2.8).** Custom header block with wordmark + tagline layout; the current `QFormLayout` doesn't accommodate this. Needs a small `QVBoxLayout` restructure.
- **Crash banner (§2.10).** Already custom; the retoken is mechanical but the banner's button-state styling needs each state retuned and verified.
- **Modal elevation (§1.5).** Each dialog needs `QGraphicsDropShadowEffect` setup; the modal backdrop overlay is a new widget that paints over the main window content while a modal is active.

### 3.2 Passive absorption — QSS plus token mapping

These surfaces require only QSS rules and token substitution. No custom widget code; no per-surface review beyond the token mapping itself.

- Panel chrome (§2.2).
- Detail pane form treatment (§2.4) — though the label-above layout change is a structural edit to existing form-builder code, not a styling change per se.
- Buttons (§2.5).
- Form controls (§2.6).
- Standard dialogs (§2.7) — the internal context strip is a small new widget, but each dialog only needs one line of "use this strip" addition.
- Inline status / error / warning treatments (§2.9).

### 3.3 Implementation order for the build

Suggested order, to be ratified in Conversation 2's slice planning:

1. **Foundation.** Design tokens module (`crmbuilder-v2/src/crmbuilder_v2/ui/tokens.py`). Font loaders for Inter and JetBrains Mono. Icon loader for Lucide. Base widget refactors so panels, dialogs, and item delegates can consume tokens. Modal elevation infrastructure (`QGraphicsDropShadowEffect` helper + backdrop overlay widget). About dialog (the smallest contained showcase surface — exercises the full token system end-to-end before any panel work).
2. **Sidebar.** First high-attention surface; sets the selected-state vocabulary that the master pane reuses.
3. **Master pane delegate.** The shared `QStyledItemDelegate` applied across all 12 (eventually 13) panels' master views.
4. **Governance panel retrofit.** Apply tokens, label-above form layout, ReferencesSection visual treatment across the eight governance panels.
5. **Methodology panel retrofit.** Same for the four (eventually five) methodology panels.
6. **Dialog polish.** Internal context strip, button-style coverage, delete-confirm treatment across all dialogs.
7. **Status / error / warning + crash banner.** Inline error treatment in fields, warning callout on Processes panel, error dialog re-skin, crash banner re-skin.
8. **Closeout.** Version bump, README release note, About dialog version verification, regression test pass.

The order is approximate; Conversation 2 may restructure slice boundaries based on file-conflict topology with v0.5 work running in parallel.

---

## 4. Acceptance Criteria

These criteria gate the design pass closing and Conversation 2 (build planning) opening. They are not build-time acceptance criteria — those belong to Conversation 2's PRD output.

### 4.1 Token completeness

A1. Every token category listed in §1 has concrete values: spacing scale, color tokens (accent, neutrals, status), typography (font family, size, weight, line-height), radius, border, elevation. No `TBD` values remain in §1.

A2. The token-naming structure (theme-keyed dict per §1.2.1) is internally consistent: every color token is reachable via the same `tokens["light"][key]` access pattern. No mixed flat-and-keyed schemes.

A3. Status color values (red, amber, green) harmonize with the cool blue accent — i.e., they don't read as a separate visual system. The drafted `#C0392B` (danger), `#B0731A` (warning), and `#2D7A4D` (success) are confirmed values, not placeholders.

### 4.2 Component completeness

A4. Every component class listed in §2 has a prose visual decision sufficient for an implementer to produce QSS without further questions. Stubs marked *(stub)* do not remain.

A5. State coverage is complete for every interactive component: each of sidebar entries, master-pane rows, buttons (all five categories), form controls (text input, multi-line, combo, checkbox), and dialogs has visuals specified for default, hover, pressed/active, focused, and disabled states where applicable.

A6. The selected-state visual vocabulary is consistent across surfaces: the left accent bar + tinted background pattern used on sidebar entries (§2.1) matches the master-pane selected row (§2.3) modulo the row-vs-column-orientation differences.

### 4.3 Contradiction check

A7. No two sections in §1 or §2 specify different values for the same property. Token references resolve unambiguously.

A8. Density-derived values (row heights, padding, button geometry) are mutually consistent: a 28px form field height matches a 28px combo height matches a 28px list row height; the spacing scale (4px base) divides cleanly into all padding values.

### 4.4 Accessibility floor

A9. Light-theme contrast meets WCAG AA at minimum for every text-on-background combination used in the design:

- Body text (`color.neutral.800` on `color.neutral.0`): 14.4:1 — passes AAA.
- Secondary text (`color.neutral.500` on `color.neutral.0`): 4.75:1 — passes AA at small body size. (Slice F's WCAG build gate revealed the drafted `#7A8694` value computed 3.71:1 — failing AA — rather than the claimed 4.62:1. Token darkened to `#6A7480` per the design-pass intent; ratio re-verified.)
- Read-only field text (`color.neutral.700` on `color.neutral.100`): 8.9:1 — passes AAA.
- Accent text (`color.accent.default` on `color.neutral.0`): 4.61:1 — passes AA. (Used on text/link buttons and Add-reference affordances.)
- Danger text (`color.danger.text` on `color.neutral.0`): ~5.4:1 — passes AA.
- Warning text (`color.warning.default` on `color.neutral.0`): 4.88:1 — passes AA at body size. (Slice F's WCAG build gate confirmed the drafted `#B0731A` computed 3.95:1 — failing AA — rather than the claimed ~4.7. Token darkened to `#9D6517` per the design pass §4.4 "borderline at caption size" note and PRD Open Question #4; ratio re-verified, build gate green.)
- White text on accent (`color.neutral.0` on `color.accent.default`): 4.66:1 — passes AA for body text; passes AAA for 18px+ large text.
- White text on danger (`color.neutral.0` on `color.danger.default`): ~5.1:1 — passes AA.

Final verification landed in slice F via `tests/crmbuilder_v2/ui/test_token_contrast.py`, which executes the WCAG 2.x formula against `TOKENS["light"]` on every CI run per DEC-107.

A10. Focus indicators are visible on every interactive element. The `color.accent.focusring` outline (40% alpha) is specified on buttons, form fields, sidebar entries (focused), and master-pane rows (focused).

A11. Color is not the sole signal for state or status. Selected rows have a structural cue (left accent bar) in addition to the tinted background. Error fields have a border-color change in addition to the inline-error text below. Required-field markers use an icon (Lucide `asterisk`) rather than relying on color alone.

### 4.5 Implementer readiness

A12. An implementer reading §§1 and 2 can identify, for each surface, exactly which tokens apply to which property. The build phase does not need to re-derive token values or invent fallback rules.

A13. The legacy-to-token mapping is explicit: every currently-styled value in v0.4 code (`#f4f4f4`, `#666`, `#888`, `#444`, `#B22222`, `#1F3864`, `#c1272d`, `#b6868a`) has a documented replacement token (per §1.2.3 and §2.9). The retrofit during build phase is mechanical search-and-replace plus token-aware widget refactors.

### 4.6 Out of scope (documented but not required)

These are explicitly *not* design-pass acceptance criteria — they belong to later phases.

- Dark mode color values: the token-naming structure (§1.2.1) supports adding them but the values themselves are not authored.
- Animation: per the workstream plan §3.2.
- Icon SVG authoring beyond the initial bundled set (§1.6).
- Cross-platform polish testing (Windows-specific verification per workstream plan §3.2).
- Full accessibility audit (focus traversal order, screen reader pass, keyboard-only navigation): deferred to a separate workstream if requested. WCAG AA contrast floor (A9 above) is the only accessibility commitment this design pass makes.

---

*End of document.*
