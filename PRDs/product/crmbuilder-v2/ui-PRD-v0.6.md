# CRMBuilder v2 — User Interface PRD

**Version:** 0.6
**Last Updated:** 05-16-26 17:30
**Status:** Draft — pending approval
**Predecessor:** `ui-PRD-v0.5.md` (engagement management; ships first per DEC-095)
**Design input:** `styling-design-pass.md` (v0.1, Conversation 1 output per SES-027)

## Change Log

| Version | Date | Description |
| --- | --- | --- |
| 0.6 | 05-16-26 17:30 | Initial draft from Styling Conversation 2 (build planning). v0.6 is the first v2 release whose primary frame is visual rather than structural — it discharges PI-001 (full styling design pass per DEC-024) after four prior deferrals and the workstream reopening in DEC-076. v0.6 ships in parallel with v0.5 (engagement management); the two workstreams couple only at v0.5's new engagement panel, which v0.6 retrofits alongside the existing twelve panels. Source content for visual decisions is `styling-design-pass.md` (this PRD cites rather than restates §1 tokens and §2 component visual decisions). Captures three architectural decisions taken in this conversation for recording at PRD approval: version-bundling resolved as v0.6 separate from v0.5 (DEC-095), six-slice structure A–F (DEC-096), per-slice screenshot + closeout WCAG check acceptance pattern (DEC-097). |

---

## 1. Overview

### Purpose

This document specifies the requirements for CRMBuilder v2 user interface v0.6 — the styling release. v0.5 (engagement management, in parallel build) closes the multi-engagement routing gap structurally. v0.6 closes the corresponding gap visually: v2 ships v0.5 with Qt-default styling on twelve methodology and governance panels, a sidebar with zero deliberate visual treatment, dialogs that mix three different ad-hoc grays and two different reds, and a crash banner that exists outside any design system. v0.6 is the build specification handed to Claude Code, which executes it through a six-prompt slice series.

### Background

PI-001 was authored at v0.1 close (DEC-024) with the framing that v2's early releases should ship structural capability first and visual polish later. The framing held through v0.2 (DEC-026), v0.3 (DEC-037), and v0.4 (DEC-042). DEC-042 added a specific trigger mechanism: PI-001 would open ahead of any other v0.5 candidate if CBM-redo Phase 1 surfaced visual friction. That trigger has not fired and is unlikely to fire in v0.5's timeframe either; the v0.5-orientation conversation concluded that continuing to defer on a trigger that cannot fire is silent abandonment rather than real deferral, and reopened PI-001 as a parallel workstream alongside v0.5 (DEC-076).

The workstream comprises two design-and-planning conversations followed by Claude Code execution. Conversation 1 (SES-027) produced `styling-design-pass.md` — a 709-line document covering design tokens (density, color, typography, radius/border, elevation, icon library) and component visual decisions across ten subsections (sidebar, panel chrome, master pane, detail pane, buttons, form controls, dialogs, About, status surfaces, crash banner) plus application priorities and acceptance criteria. Conversation 1 also produced eight design-pass decisions (DEC-087 through DEC-094).

This PRD is the output of Conversation 2 (build planning, this conversation). It takes the design pass as input and produces a release-scoped specification suitable for slice-level Claude Code execution.

### Source decisions

This PRD does not re-derive design decisions; it specifies requirements grounded in the following decision records.

Deferral and reopening chain:

- **DEC-024** — PI-001 created at v0.1 close: full styling design pass deferred with the framing that v2's early releases ship structural capability first.
- **DEC-026, DEC-037, DEC-042** — Three subsequent deferrals through v0.2, v0.3, and v0.4 closes. DEC-042 added the CBM-redo-friction trigger mechanism.
- **DEC-075** — v0.5-orientation conversation findings: the CBM-redo-friction trigger is structurally unlikely to fire because methodology panels are empty pre-CBM and CBM Phase 1 is post-v0.5.
- **DEC-076** — PI-001 reopens as parallel workstream alongside v0.5. Workstream plan committed at `styling-workstream-plan.md`. Boundary between styling and v0.5 owns §4 of that document.
- **DEC-077** — Paper-test conversation deferred until v0.5 ships and a CBM engagement record is created.

Design-pass decisions (Conversation 1, SES-027):

- **DEC-087** — Density target: Default. Workstation context (3× 4K monitors) rules out compact and comfortable. 4px spacing scale with derived sizes (28px list rows, 28px form fields, 88px minimum button width).
- **DEC-088** — Token-naming structure: theme-keyed dict (`TOKENS["light"][key]`). Dark-mode-ready without consumer-code retrofit; ~5 LOC cost today versus rename-every-color-reference cost if dark mode ships later.
- **DEC-089** — Brand accent: cool blue `#1F5FBF` (steely, deliberate) retiring the legacy `#1F3864` navy stub. Cool-gray neutral scale paired (`#FFFFFF` through `#0F1318`). Status colors harmonized: danger `#C0392B`, warning `#B0731A`, success `#2D7A4D`.
- **DEC-090** — Font family: Inter Variable bundled (~280 KB). JetBrains Mono Variable bundled (~250 KB) for identifier columns, code surfaces, About-dialog paths. Loaded via `QFontDatabase.addApplicationFont()` at startup.
- **DEC-091** — Modal elevation only via `QGraphicsDropShadowEffect` (Qt's built-in effect, not custom paintEvent). Plus a `color.neutral.900` 8%-alpha backdrop overlay when a modal is active. Rest of the app stays fully flat on one z-plane.
- **DEC-092** — Icon library: Lucide (~1,400 icons, ISC, single regular-weight 2px stroke). Bundled additively as per-icon SVGs at `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/lucide/`. Loader helper recolors at runtime via token system.
- **DEC-093** — Selected-state visual vocabulary: 3px left accent bar + `color.accent.subtle` tinted background + `color.neutral.900` medium-weight text. Applied uniformly to sidebar entries and master-pane rows so the two surfaces share one design vocabulary. Implemented via shared `QStyledItemDelegate` subclass for master panes; custom item rendering for the sidebar `QListWidget`.
- **DEC-094** — About dialog: modest-showcase treatment. Wordmark "CRMBuilder v2" plus tagline below ("Declarative CRM deployment and methodology authoring" — refineable at build time). Metadata table restructured from `QFormLayout` to a vertical two-line-per-row list with `font.family.mono` paths. No custom brand mark.

Forthcoming decisions (to be recorded after this PRD is approved, see Section 11):

- **DEC-095** — Version bundling for the styling work: ship as separate v0.6 release rather than bundled into v0.5. Independence of the two workstreams is load-bearing; bundling permanently blurs the project's release-version navigation index.
- **DEC-096** — Slice structure for v0.6: six slices (Foundation + About, Sidebar + master-pane delegate, Panel retrofits + ReferencesSection, Dialogs + form controls, Status + crash banner, Closeout). Reconciliation differences from the workstream plan §5.3 strawman documented in §7 of this PRD.
- **DEC-097** — Slice acceptance pattern: per-slice after-state screenshot committed to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/`, plus eyeball verification against the design pass. Automated WCAG AA contrast check against codified `tokens.py` values runs once at slice F closeout per design-pass A9.

---

## 2. Scope

### In Scope

The following are required deliverables for v0.6.

1. **Design tokens module.** New `crmbuilder-v2/src/crmbuilder_v2/ui/tokens.py` exposing the theme-keyed token system specified in `styling-design-pass.md` §1. Every token from the design pass is codified with the exact hex / px / pt values that document specifies: density-derived sizes (28px list rows, 28px form fields, 88px minimum button width, 16px panel chrome padding, 12px inter-pane spacing, 20/12/16px dialog margins); 9-step cool-gray neutral scale plus accent and status colors; Inter Variable + JetBrains Mono Variable font tokens; size/weight/line-height scales; radius and border tokens; elevation tokens for modals.

2. **Font asset bundling.** Inter Variable and JetBrains Mono Variable committed to `crmbuilder-v2/src/crmbuilder_v2/ui/assets/fonts/`. Total binary cost ~530 KB. Both OFL-licensed; license files committed alongside. Loaded at app startup via `QFontDatabase.addApplicationFont()` per DEC-090.

3. **Icon asset bundling and loader.** Lucide SVGs at `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/lucide/{kebab-case-name}.svg` for the initial wave needed by v0.6 surfaces. Initial wave: `pencil`, `trash-2`, `rotate-ccw`, `external-link`, `copy`, `plus`, `x`, `chevron-right`, `chevron-down`, `chevron-up`, `circle-alert`, `circle-x`, `check`, `asterisk`. License file (ISC) committed. Loader helper at `crmbuilder-v2/src/crmbuilder_v2/ui/icons.py` wraps `QSvgRenderer` to produce a `QIcon` at requested size with runtime color tinting via the token system per DEC-092.

4. **Base widget hooks for token consumption.** Existing base widgets (`ListDetailPanel`, `EntityCrudDialog`, `EntityCrudDeleteDialog`, `ReferencesSection`) gain hooks for tokens — either via a project-level QSS stylesheet applied at app startup, or via per-widget `setStyleSheet` blocks reading from `tokens.py`. Mechanism choice per slice A's implementation prompt; criterion is that every existing v0.5 widget renders against the new token system after slice A merges, without changing structural behavior.

5. **Modal elevation infrastructure.** `crmbuilder-v2/src/crmbuilder_v2/ui/elevation.py` providing a helper that applies `QGraphicsDropShadowEffect` per the `shadow.dialog` token to a given `QDialog` instance. Plus a `ModalBackdropOverlay` widget at `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/modal_backdrop.py` that paints a full-window overlay at `overlay.modal_backdrop` (`color.neutral.900` 8% alpha) when any modal is open. Both wired into the dialog base classes so every existing `QDialog` subclass picks up the treatment without per-dialog modification.

6. **About dialog re-skin.** Existing `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/about.py` restructured per design pass §2.8 and DEC-094: wordmark + tagline header block (replaces the current minimal title), metadata table restructured from `QFormLayout` to vertical two-line-per-row list with mono-font path values, single secondary "Close" button right-aligned. Minimum width preserved at 440px. Acts as the canary surface that exercises the full token system end-to-end before any panel work.

7. **Sidebar visual treatment.** Custom item rendering on the existing `QListWidget`-based sidebar implementing design pass §2.1: 220px-wide container with `color.neutral.100` background and right-edge 1px hairline border; non-selectable group headers in `font.size.caption` `font.weight.semibold` with `+0.04em` letter-spacing; 32px entry height with `font.size.body`; selected-state 3px left accent bar plus `color.accent.subtle` background plus `color.neutral.900` medium-weight text per DEC-093; hover state without accent bar; stale-indicator dot color flipped from legacy `#1F3864` to `color.accent.default`. Implementation either via custom `QListWidget` subclass or via a `QListWidget` item delegate — slice B's choice.

8. **Master-pane delegate.** Shared `QStyledItemDelegate` subclass at `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/master_pane_delegate.py` implementing design pass §2.3 across all `QTableView`, `QTreeView`, and `QListView` master panes in the application. The delegate handles: 28px row height; row-divider hairlines in `color.neutral.200`; column header treatment with `font.size.small` `font.weight.semibold` `color.neutral.700` text on `color.neutral.100` background; hover-state row tinting; selected-state row treatment matching the sidebar vocabulary (3px left accent bar + `color.accent.subtle` background + `color.neutral.900` medium-weight text) per DEC-093; soft-deleted-row treatment (50% text contrast plus leading Lucide `trash-2` icon in the identifier column when `?include_deleted=true` is on); identifier-column mono-font rendering (`font.family.mono` at `font.size.small`). Registered on every existing panel's master pane in slice B; the eventual v0.5 engagement panel inherits via the same registration in slice C.

9. **Panel retrofits.** Every panel in `crmbuilder-v2/src/crmbuilder_v2/ui/panels/` absorbs tokens per design pass §2.2 (panel chrome) and §2.4 (detail pane). Specifically: panel content background `color.neutral.50`; outer padding 16px (`space.4`); master/detail `QSplitter` retained with `space.3` (12px) handle width and centered hairline divider; default split 45/55; detail-pane form layout changed from current `QFormLayout` (label-left) to label-above with 4px label-to-field gap and 12px row-to-row spacing per design pass §2.4. Affected panels: 12 panels shipping in v0.5 (8 governance: Sessions, Decisions, Risks, Planning Items, Topics, References, Charter, Status; 4 methodology: Domains, Entities, Processes, CRM Candidates) plus v0.5's new Engagement panel (the 13th) if v0.5 has shipped by this slice's land time, which is expected per DEC-095's separate-release sequencing.

10. **ReferencesSection sub-sectioned plain-list rendering.** Existing `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` restructured per design pass §2.4 to render references in sub-sections grouped by relationship kind. Each sub-section has a `font.size.small` `font.weight.semibold` `color.neutral.700` header (kind name in title case — "Decided in", "Is about", "Hands off to", "Receives from", "Supersedes", "Superseded by", "References"). Entries below each header render identifier in `font.family.mono` at `font.size.small` `color.neutral.700` followed by title in `font.size.body` `color.neutral.800`. Sub-sections separated by 16px (`space.4`) vertical space. "Add reference" text-only button below the last sub-section with Lucide `plus` icon. Empty-state line "No references" in `color.neutral.500` when no references registered.

11. **Dialog chrome and form controls.** All `QDialog` subclasses pick up the design system per design pass §2.7: container background `color.neutral.0`, inner padding 20px (`space.5`), `radius.dialog` (6px) where the platform renders it, drop shadow and backdrop overlay from the elevation infrastructure (deliverable 5). Record-editing dialogs (the `EntityCrudDialog` subclasses) gain an internal context strip at the top of the dialog body showing identifier and record name. Delete-confirm dialogs follow §2.7's delete-specific treatment. Form controls absorb tokens per design pass §2.6: text inputs and combos at 28px height with `border.field`/`border.field_focus`/`border.danger`/disabled state coverage; multi-line text inputs at 80px minimum height; checkboxes at 16×16 with `color.accent.default` fill when checked.

12. **Button styling — five categories.** Per design pass §2.5, all buttons across the application render in one of five categories with full state coverage (default / hover / pressed / focused / disabled). Primary (accent fill, white text) replaces ad-hoc primary treatments; Secondary (transparent with `color.neutral.300` border) replaces existing default `QPushButton` treatment; Destructive (`color.danger.default` fill) retires the legacy `#c1272d` red on `reference_delete.py` and `crud_dialog.py` plus the legacy `#b6868a` disabled-destructive treatment; Text/Link (transparent with accent-colored text) covers "Add reference" and similar inline affordances; Icon-only (28×28 with `color.neutral.700` icon at rest) covers toolbar refresh and show-deleted toggles. All categories share 6×14px padding and `radius.subtle`; constructive buttons share 88px minimum width so Save/Cancel line up.

13. **Status, error, and warning surfaces.** Three patterns codified per design pass §2.9: inline form-field errors below editable fields (`font.size.caption` in `color.danger.text`, paired with the field's red border which carries the primary visual signal); inline panel-level warnings as single-row callouts with Lucide `circle-alert` icon plus warning text in `color.warning.default` — the existing `_WARNING_STYLE = "color: #B22222;"` on `panels/processes.py` updates from danger-red to warning-amber because the soft-deleted-domain message is informational rather than error; error dialog (`dialogs/error.py`) gets a header retoken with leading Lucide `circle-x` icon plus title text in `color.danger.text`, retiring the legacy `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"`.

14. **Crash banner re-skin.** Existing `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py` folded into the design system per design pass §2.10 and DEC-094: background `color.danger.default`, text in `color.neutral.0` at `font.size.body` `font.weight.medium`, leading Lucide `circle-alert` icon, semi-transparent white-on-color buttons with proper state coverage. Retires the bespoke `_BANNER_BACKGROUND` and ad-hoc button styling.

15. **About-dialog version bump and README release note.** `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.6.0"`. README at `crmbuilder-v2/README.md` gets a v0.6 release note matching v0.5's format: one-paragraph summary plus a bullet list of token surfaces, the five retoken categories (button categories, form controls, dialogs, status surfaces, crash banner), and the bundled-asset additions (Inter, JetBrains Mono, Lucide).

### Out of Scope

The following are explicitly deferred.

- **Functional changes.** No new widgets, no rearranged information density, no new keyboard shortcuts, no new dialogs. Visual treatment only. Per workstream plan §3.2.

- **Dark mode color values.** The token structure (DEC-088, theme-keyed) supports adding a `TOKENS["dark"]` key without consumer-code retrofit, but no dark-mode values are authored in v0.6. Deferred to a separate PI if requested. Per workstream plan §3.2 and design pass §4.6.

- **Animation and transitions.** No animated state transitions beyond Qt defaults (e.g., the existing fade-in on the modal backdrop overlay is one specified ~150ms transition; nothing else). Per workstream plan §3.2.

- **Cross-platform polish.** Linux and macOS are production targets. Windows-on-best-effort. Per workstream plan §3.2 and design pass §4.6.

- **Full accessibility audit.** WCAG AA contrast verification at slice F closeout (per design pass A9) is the only accessibility commitment v0.6 makes. Focus-traversal order audit, screen-reader pass, keyboard-only navigation audit deferred to a separate workstream if requested. Per design pass §4.6.

- **Icon SVG authoring beyond initial set.** Future surfaces will need additional Lucide icons; they get added per-surface as v0.7+ work surfaces them. Per design pass §1.6.

- **Brand mark.** The About dialog ships with wordmark + tagline; no custom logo is authored in v0.6. Brand-mark authoring is a separate subjective design problem unsuitable for remote conversation resolution per DEC-094.

- **Stylesheet introspection or automated pixel measurement.** No build-time check verifies that QSS values match `tokens.py` values; correctness is established by eyeball plus the WCAG contrast check. A future PI may add automated checks if drift becomes a problem.

- **Reference-relationship vocabulary changes, schema migrations, new entity types, API endpoint changes.** v0.6 is visual-only. Any storage- or routing-layer work is out of scope.

- **Retrofit of any v1 application surfaces.** v1 work, not v2.

---

## 3. Architecture

### Process model

Unchanged from v0.5. The desktop process spawns the API subprocess and the MCP subprocess per engagement; the UI reaches the storage layer exclusively through the REST API. v0.6 is visual-only and does not touch the process model.

### Layer responsibilities

v0.6 adds three new modules, restructures two existing widgets, and retoken-touches every existing panel and dialog. No new top-level structural change.

| Layer | Module | Status | Responsibility |
| --- | --- | --- | --- |
| Tokens | `crmbuilder_v2.ui.tokens` | new | Theme-keyed token dict (`TOKENS["light"][key]`) plus accessor function. Codifies every value from `styling-design-pass.md` §1. |
| Icon loader | `crmbuilder_v2.ui.icons` | new | Wraps `QSvgRenderer` to produce `QIcon` at requested size with runtime color tinting from the token system. |
| Modal elevation | `crmbuilder_v2.ui.elevation` | new | Helper that applies `QGraphicsDropShadowEffect` per `shadow.dialog` to any `QDialog`. |
| Modal backdrop | `crmbuilder_v2.ui.widgets.modal_backdrop` | new | Full-window overlay widget at `overlay.modal_backdrop` painted when any modal is active. |
| Master-pane delegate | `crmbuilder_v2.ui.widgets.master_pane_delegate` | new | Shared `QStyledItemDelegate` subclass implementing row treatment per design pass §2.3 (selected state, soft-deleted treatment, identifier-column mono font). Registered on every panel's master pane. |
| Sidebar | `crmbuilder_v2.ui.sidebar` | extended | Visual treatment per design pass §2.1: container background, group headers, entry geometry, selected-state vocabulary, stale-indicator-dot color update. Either custom `QListWidget` subclass or item delegate. |
| Panels | `crmbuilder_v2.ui.panels.*` | retoken | All 12 existing panels (Sessions, Decisions, Risks, Planning Items, Topics, References, Charter, Status, Domains, Entities, Processes, CRM Candidates) plus the v0.5 Engagement panel pick up tokens. Detail-pane form layout changes from `QFormLayout` to label-above. No structural changes. |
| Base widgets | `crmbuilder_v2.ui.base.*` | extended | `ListDetailPanel`, `EntityCrudDialog`, `EntityCrudDeleteDialog` gain token-consuming chrome. Form-row layout helpers gain label-above support. |
| References section | `crmbuilder_v2.ui.widgets.references_section` | restructured | Sub-sectioned plain-list rendering per design pass §2.4. |
| Dialogs | `crmbuilder_v2.ui.dialogs.*` | extended | About dialog re-skinned (DEC-094). Error dialog re-skinned per §2.9. Crash banner re-skinned per §2.10. Record-editing dialogs gain internal context strip. Delete-confirm dialogs gain treatment per §2.7. |
| Assets | `crmbuilder_v2.ui.assets.*` | new | `fonts/` for Inter Variable and JetBrains Mono Variable. `icons/lucide/` for the initial Lucide SVG set. License files (OFL, ISC) committed alongside. |
| Application shell | `crmbuilder_v2.ui.app` | extended | App startup loads bundled fonts via `QFontDatabase.addApplicationFont()` before the main window opens. |
| Storage layer | `crmbuilder_v2.access.*`, `crmbuilder_v2.api.*` | unchanged | v0.6 is visual-only. |
| Migrations | `crmbuilder-v2/migrations/` | unchanged | No schema changes; no Alembic revisions. |
| Tests | `tests/crmbuilder_v2/` | extended | New test module for the WCAG contrast verification (slice F). No new tests for the visual surfaces themselves — visual verification is screenshot-based per DEC-097. v0.5 test suite continues to pass. |

### Configuration

Unchanged from prior releases. No new environment variables, no config file additions.

---

## 4. Functional Requirements

`styling-design-pass.md` is the authoritative source for visual decisions. This PRD does not restate token values or component-by-component visual specifications. The mapping from design-pass section to v0.6 slice is in §7 (Implementation Plan Reference).

### 4.1 Token system

Design pass §1. Codified in `tokens.py` with the exact values that document specifies. Consumers read via `tokens.get(key)` or equivalent accessor; theme-keying is structural per DEC-088. Slice A delivers the token module end-to-end; subsequent slices consume from it without modifying it.

### 4.2 Font and icon assets

Design pass §1.3 (typography) and §1.6 (icon library). Bundled per DEC-090 and DEC-092. The icon loader at `ui/icons.py` provides `lucide(name, size=16, color_token="color.neutral.700") -> QIcon` per design pass §1.6. App startup loads both font families before the main window opens; if loading fails, the app falls back to system defaults rather than blocking launch.

### 4.3 About dialog

Design pass §2.8 and DEC-094. The canary surface; slice A delivers it end-to-end as the smallest contained exercise of the full token system. Wordmark `"CRMBuilder v2"` in `font.size.heading_2` `font.weight.semibold`; tagline below in `font.size.small` `color.neutral.500`. Metadata table restructured to two-line-per-row vertical list with mono paths. Single "Close" button right-aligned.

### 4.4 Sidebar

Design pass §2.1 and DEC-093. Slice B delivers visual treatment for the existing two sidebar groups (Governance, Methodology). The eventual v0.5 sidebar mechanism (engagement-switcher affordance) is owned by v0.5; v0.6 inherits whatever shape v0.5 ships.

### 4.5 Master pane delegate

Design pass §2.3 and DEC-093. Slice B delivers the shared `QStyledItemDelegate`. The delegate is registered on each existing panel's master-pane view in slice B itself (one-line registration per panel — touched in slice B, not slice C, so slice B closes with all panels' master panes rendering the new vocabulary even though panel chrome and detail panes are still Qt-default until slice C).

### 4.6 Panel chrome, detail pane, ReferencesSection

Design pass §2.2, §2.4. Slice C delivers panel chrome retoken across all panels, the label-above form layout change in detail-pane form builders, and the ReferencesSection restructure. The label-above change is structural (modifies form-builder code) rather than purely QSS; it is the only structural retrofit in slice C.

### 4.7 Buttons and form controls

Design pass §2.5 and §2.6. Slice D delivers full state coverage for the five button categories and the form controls (text input, multi-line text, combo box, checkbox). Slice D also delivers the internal context strip on record-editing dialogs and the delete-confirm dialog treatment per §2.7.

### 4.8 Status, error, warning surfaces; crash banner

Design pass §2.9 and §2.10. Slice E delivers inline form-field error treatment, the inline panel-level warning callout pattern (applied first to `panels/processes.py`'s soft-deleted-domain message), the error-dialog header retoken, and the crash-banner re-skin into the design system.

### 4.9 Closeout

Slice F delivers `__version__` bump to `"0.6.0"`, README release note, status update from `"v0.5 complete"` to `"v0.6 complete"`, automated WCAG AA contrast verification per DEC-097, and session record drafts for SES-028 (this conversation).

---

## 5. Cross-Cutting Concerns

### 5.1 About-dialog version bump

Slice F sets `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` to `"0.6.0"`. The About dialog reads via `importlib.metadata` with `__version__` as fallback per the CLAUDE.md v2 version-source convention.

### 5.2 README release note

Slice F adds a v0.6 release-note entry to `crmbuilder-v2/README.md` matching v0.5's format: one-paragraph summary plus a bullet list naming the design tokens module, the bundled fonts, the bundled icons, the five button categories, the new master-pane delegate, the sub-sectioned ReferencesSection, the modal elevation treatment, the retired legacy color values (`#1F3864`, `#f4f4f4`, `#444`, `#666`, `#888`, `#c1272d`, `#b6868a`, `#B22222`).

### 5.3 Test target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target. v0.5's test suite remains green; v0.6 adds one new test module (`tests/crmbuilder_v2/ui/test_token_contrast.py`) that exercises the WCAG AA contrast check per DEC-097 against the codified `tokens.py` values. No tests added for visual surfaces themselves — visual verification is screenshot-based per DEC-097.

### 5.4 Status update

Status is updated from `"v0.5 complete"` to `"v0.6 complete"` after slice F passes. Authored through the desktop UI's versioned-replace pattern per existing convention.

### 5.5 Screenshot capture

Per DEC-097, each visual slice (A through E) commits an after-state screenshot per affected surface to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/`. Doug captures screenshots after running the slice's Claude Code prompt and verifying eyeball-level rendering. Screenshots are PNG, sized to fit content (not full screen unless the surface itself fills the screen). Filename convention: `{surface-name}.png` (e.g., `about-dialog.png`, `sidebar.png`, `master-pane-delegate.png`, `domains-panel.png`). Total expected screenshot count across v0.6: ~15–20 PNGs at ~100–300 KB each, ~3–5 MB total.

---

## 6. Acceptance Criteria

Cumulative acceptance criteria for v0.6 = foundation criteria (slice A) + visual-vocabulary criteria (slice B) + retrofit criteria (slice C) + dialog and form criteria (slice D) + status-surface criteria (slice E) + closeout criteria (slice F).

### Slice A — Foundation + About dialog

A1. `crmbuilder-v2/src/crmbuilder_v2/ui/tokens.py` exists and exposes every token category specified in design pass §1 via the theme-keyed dict structure per DEC-088. A consumer reading `TOKENS["light"]["color.accent.default"]` returns `"#1F5FBF"`.

A2. Inter Variable and JetBrains Mono Variable load at app startup via `QFontDatabase.addApplicationFont()`. The font registry returns both family names; the application's default font is Inter at `font.size.body` (14px).

A3. The Lucide icon loader at `ui/icons.py` returns a `QIcon` for every icon in the initial wave (deliverable 3 in §2). Color tinting via the token system returns visibly correct results for at least `color.neutral.700`, `color.accent.default`, and `color.danger.default`.

A4. The modal elevation infrastructure (drop shadow + backdrop overlay) applies to every `QDialog` subclass without per-dialog modification. Opening any dialog renders the shadow and dims the underlying main window to `color.neutral.900` at 8% alpha.

A5. The About dialog renders per design pass §2.8: wordmark, tagline, mono-font metadata table, single "Close" button. Eyeball verification against the design pass.

A6. After-state screenshot of the About dialog committed to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-A/about-dialog.png`.

A7. v0.5's test suite continues green; no functional regression.

### Slice B — Sidebar + master-pane delegate

B1. Sidebar renders per design pass §2.1: 220px container with `color.neutral.100` background, right-edge hairline, group headers in small-caps-ish treatment, 32px entries with `font.size.body` text.

B2. Sidebar selected-state renders per DEC-093: 3px left accent bar in `color.accent.default`, `color.accent.subtle` background, `color.neutral.900` medium-weight text. Hover state distinct (background only, no bar). Focus state matches selected plus visible focus ring.

B3. Stale-indicator dot color is `color.accent.default` (replaces the legacy `#1F3864`).

B4. The shared master-pane delegate is registered on every panel's `QTableView` / `QTreeView` / `QListView`. Every master pane renders the new selected-state vocabulary (matching B2) plus row dividers, column header treatment, soft-deleted-row treatment, and identifier-column mono font.

B5. The tree-view variant on the Topics panel uses Lucide `chevron-right`/`chevron-down` for expand/collapse instead of Qt's default branch indicator. Indentation per level is 16px (`space.4`).

B6. After-state screenshots committed to `slice-B/`: `sidebar.png` (showing one selected entry and one hovered entry), `master-pane-table.png` (any table-view panel), `master-pane-tree.png` (Topics panel), `master-pane-soft-deleted.png` (any panel with show-deleted on and a soft-deleted record visible).

B7. v0.5 test suite remains green; no functional regression.

### Slice C — Panel retrofits + ReferencesSection

C1. Every panel renders per design pass §2.2: `color.neutral.50` panel background, 16px outer padding, splitter handle at `space.3` (12px) width with centered hairline divider, default 45/55 split.

C2. Every detail pane uses the label-above form layout per design pass §2.4: label in `font.size.small` `font.weight.medium` `color.neutral.700`, 4px gap to field below, 12px between rows, required-field marker as Lucide `asterisk` icon (not the word "Required").

C3. Editable field state coverage matches design pass §2.4: default, focused (border `color.accent.default` + focus-ring outline), error (border `color.danger.default`), disabled (`color.neutral.100` background, `color.neutral.300` text). Read-only fields visually distinct from disabled (`color.neutral.100` background, no border, `color.neutral.700` text).

C4. Status combo on every panel that has one (Domains, Entities, CRM Candidates) shows valid-transitions hint caption below the combo per design pass §2.4.

C5. ReferencesSection renders sub-sectioned plain-list per design pass §2.4: kind headers in title case, identifier column in mono font, entry hover state, right-click context menu unchanged from v0.5 behavior, "Add reference" text-only button below the last sub-section.

C6. After-state screenshots committed to `slice-C/`: one per affected panel (`sessions-panel.png`, `decisions-panel.png`, ..., `crm-candidates-panel.png`, `engagement-panel.png`) plus `references-section-multi-kind.png` showing a record with at least three relationship kinds rendered.

C7. v0.5 test suite remains green; no functional regression.

### Slice D — Dialogs + form controls

D1. Every record-editing `QDialog` subclass renders with the internal context strip per design pass §2.7: identifier in mono font, record name in body font, `color.neutral.100` background, hairline below.

D2. Every button across the application renders in one of the five categories (Primary, Secondary, Destructive, Text/Link, Icon-only) per design pass §2.5. State coverage complete for each category (default / hover / pressed / focused / disabled). The legacy `#c1272d` red and `#b6868a` disabled-destructive treatment no longer appear anywhere in the running application.

D3. Form controls render per design pass §2.6: text input at 28px height, multi-line text at 80px minimum, combo box with Lucide `chevron-down` affordance and properly-tokenized dropdown popup, checkbox at 16×16 with Lucide `check` icon when checked.

D4. Delete-confirm dialogs render per design pass §2.7's delete-specific treatment: no context strip, single paragraph body at `font.line.relaxed` (1.6), destructive button right-aligned with cancel to its left.

D5. After-state screenshots committed to `slice-D/`: `edit-dialog-with-context-strip.png`, `delete-confirm-dialog.png`, `button-states-primary.png`, `button-states-secondary.png`, `button-states-destructive.png`, `form-controls.png` (showing a form with at least one of each control type).

D6. v0.5 test suite remains green; no functional regression.

### Slice E — Status, error, warning + crash banner

E1. Inline form-field errors render per design pass §2.9: caption-sized text in `color.danger.text` below the affected field, paired with red field border.

E2. Inline panel-level warnings render per design pass §2.9: Lucide `circle-alert` icon plus warning text in `color.warning.default`. The Processes panel's soft-deleted-domain warning specifically uses the warning-amber treatment (not the legacy danger-red `#B22222`).

E3. Error dialog (`dialogs/error.py`) header renders per design pass §2.9: Lucide `circle-x` icon plus heading-3 title in `color.danger.text`. The legacy `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` is removed from the file.

E4. Crash banner renders per design pass §2.10: `color.danger.default` background, white text, Lucide `circle-alert` icon, semi-transparent white-on-color button states. The legacy `_BANNER_BACKGROUND` constant is removed.

E5. After-state screenshots committed to `slice-E/`: `inline-field-error.png`, `inline-panel-warning.png` (the Processes soft-deleted-domain case is the canonical example), `error-dialog.png`, `crash-banner.png`.

E6. v0.5 test suite remains green; no functional regression.

### Slice F — Closeout

F1. `__version__` is `"0.6.0"`; About dialog shows v0.6.0.

F2. README at `crmbuilder-v2/README.md` has a v0.6 release-note entry matching v0.5's format.

F3. `uv run pytest tests/crmbuilder_v2/ -v` passes green across the full suite including the new WCAG contrast test module.

F4. The new WCAG AA contrast check passes for every text-on-background combination listed in design pass §4.4 (A9). Failures are not tolerated; the contrast check is a build gate.

F5. Status entity updated from `"v0.5 complete"` to `"v0.6 complete"` via the versioned-replace pattern.

F6. Cumulative roll-up: A1–A7 plus B1–B7 plus C1–C7 plus D1–D6 plus E1–E6 plus F1–F5 pass in the running application.

F7. SES-028 session record draft and DEC-095 through DEC-097 decision records drafted in the close-out payload per the SES-025/026/027 close-out pattern.

---

## 7. Implementation Plan Reference

Slice breakdown, dependencies, and per-slice Claude Code prompts are at `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`. The implementation plan is the companion document to this PRD.

### Reconciliation with workstream plan strawman

Workstream plan §5.3 sketched a five-slice strawman (Foundation / Governance retrofit / Methodology retrofit / Dialog polish / Closeout). This PRD's six-slice structure (DEC-096) differs in three ways:

1. **Master-pane delegate is its own slice (B) rather than buried in the panel retrofits.** The delegate is shared across all 12+ panels; pulling it to a foundation-tier slice avoids artificially coupling governance and methodology retrofit work.

2. **Governance and methodology retrofits collapsed into one slice (C).** The retrofit pattern is identical across all panels; splitting it repeats the same review work twice without buying anything. Risk concentration is mitigated by slice B having already landed the shared delegate — slice C is mostly QSS plus the ReferencesSection layout, which is mechanical.

3. **Status / error / warning + crash banner promoted to its own slice (E).** The workstream plan would have folded these into "dialog polish." Pulling them out keeps two distinct concerns (dialog chrome versus status surfaces) separately reviewable.

### Slice dependencies

Slices land in lettered order. A → B → C → D → E → F is strict; no parallel landing. Slice F gates on all prior slices' acceptance criteria passing in the running application.

### Engagement-panel coupling

Per workstream plan §4, v0.5 ships first (engagement management as a separate v0.5 release per DEC-095). When slice C runs, the v0.5 engagement panel is present in `panels/` and absorbs the retrofit alongside the other 12 panels. No separate coordination needed.

---

## 8. Constraints

### Visual-only

v0.6 introduces no functional changes, no new entity types, no schema migrations, no new endpoints, no new keyboard shortcuts, no new dialogs (re-skinning existing dialogs is in scope; introducing new dialogs is not). Per workstream plan §3.2.

### No changes to v1

Unchanged from v0.1–v0.5. v2 work is strictly additive to v1.

### Constraint: no regression of v0.5 functional behavior

Slices A through E must not change any v0.5 functional behavior. The v0.5 test suite is the regression net; every slice gates on v0.5 tests continuing to pass (slice acceptance criterion A7 / B7 / C7 / D6 / E6).

### Constraint: token consumption is one-way

`tokens.py` is read-only after slice A merges. Subsequent slices consume from it; they do not modify it. Any token-value adjustment surfaced during slice B–E execution lands as a token-only change isolated to a single commit, with affected slices rebased if mid-flight. This keeps token authority concentrated in one place.

### Constraint: structural changes confined to enumerated surfaces

The only structural code changes v0.6 makes are (a) base-widget hooks for token consumption (slice A), (b) the modal elevation infrastructure (slice A), (c) the master-pane delegate registration on every panel (slice B), (d) the label-above form layout change in detail-pane form builders (slice C), and (e) the ReferencesSection restructure (slice C). Everything else is QSS plus per-widget style application. Slice prompts must not introduce structural changes outside this enumeration.

### Constraint: WCAG AA contrast is a build gate

Per DEC-097, the slice F WCAG contrast check is not advisory — it is a build gate. If any text-on-background combination from design pass §4.4 fails, slice F fails and a token-value adjustment must land before v0.6 can ship. The check is automated and runs in pytest.

### Constraint: screenshots are committed git-tracked

Per DEC-097, after-state screenshots are git-tracked at `PRDs/product/crmbuilder-v2/styling-screenshots/`. They are not gitignored. This means v0.6's commit history grows by ~3–5 MB of PNG content; that is the intended trade for project navigability.

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Inter or JetBrains Mono fail to load at startup on some platform (Linux compositor quirk, macOS font registry edge case) | Low | Medium | The font loader falls back to system defaults rather than blocking app launch. Slice A acceptance criterion A2 verifies loading succeeds on Doug's primary platform (Linux). Windows is out of scope per §2 Out of Scope. |
| QSS rules fail to apply uniformly across Qt versions (the Qt-supplied QSS engine has known inconsistencies, especially around `QGraphicsDropShadowEffect` rendering on `QDialog`) | Medium | Medium | Modal elevation is the riskiest surface. Slice A acceptance criterion A4 requires verifying drop shadow renders on a `QDialog` instance; if it fails, the slice prompt re-investigates. Workstream plan §3.2 already accepts cross-platform variability — Linux/macOS only. |
| The shared master-pane delegate (slice B) breaks an existing panel's per-panel column rendering | Low | High | Every panel's master pane has the same `QTableView`-based shape per v0.4's `ListDetailPanel` factory pattern. Slice B's prompt verifies each panel renders correctly post-registration. If a panel has custom column rendering that conflicts, the delegate's `paint()` falls through to `super().paint()` for non-overridden cases. |
| Label-above form layout (slice C) makes some panel's detail pane render awkwardly because a field's content is naturally wide (e.g., a long description box plus a narrow status combo on the same row) | Medium | Low | Label-above means every field claims full row width. Existing detail-pane form builders use `QFormLayout` which already mostly renders one-field-per-row; the layout change is mostly mechanical. Slice C's acceptance criterion C2 catches any awkward case via eyeball verification on screenshots. |
| WCAG AA contrast check (slice F) fails for the warning-amber on white at caption size | Medium | Low | Design pass §4.4 (A9) already flags this as borderline at 12px caption size. If the check fails, the warning token darkens slightly (e.g., from `#B0731A` to `#9D6517`) in `tokens.py`; the change is isolated to the token module and rebases trivially. |
| Screenshot capture (per DEC-097) becomes burdensome and Doug accumulates partial coverage across slices | Low | Low | Each visual slice's acceptance criterion lists the exact screenshot filenames expected. Slice F's roll-up criterion (F6) gates on cumulative coverage. If screenshot capture proves friction-laden, the pattern is revisable at v0.7+ work without affecting v0.6's substance. |
| `QGraphicsDropShadowEffect` applied uniformly to every `QDialog` causes noticeable rendering lag on opening dialogs on lower-end hardware | Low | Low | Doug's hardware is a 3× 4K workstation; lag is unlikely. If lag surfaces, the elevation token's blur radius can be reduced from 16px to 8px in `tokens.py`; isolated change. |
| The new Lucide icons render at the wrong size or with the wrong stroke weight when color-tinted via the runtime helper | Low | Medium | Slice A acceptance criterion A3 verifies the loader produces visibly correct results for at least three colors. If tinting fails for some icons (e.g., icons with multiple paths and inline fills), the affected icons are re-exported without inline fills. |
| v0.5 engagement panel ships with a structural shape that doesn't accommodate the master-pane delegate cleanly (e.g., a custom view widget instead of `QTableView`) | Low | Medium | Per workstream plan §4, v0.5's engagement panel inherits from v0.4's `ListDetailPanel` pattern. If v0.5 deviates, slice C's prompt handles the engagement panel as a separate per-surface case rather than the omnibus retrofit; the workstream plan §4 already anticipates this. |

---

## 10. Open Questions

1. **Tagline final wording on the About dialog.** Design pass §2.8 proposes "Declarative CRM deployment and methodology authoring" with two alternatives noted ("CRM deployment and methodology tooling for consultants." / "End-to-end CRM implementation tooling."). Slice A refines if the proposed wording reads awkwardly in the actual rendered dialog layout. Decision is UI-detail.

2. **QSS application mechanism — project-level stylesheet vs per-widget `setStyleSheet`.** Slice A's foundation work makes this choice. Project-level stylesheet applied at app startup is more concentrated but harder to scope (every widget in the tree picks it up); per-widget `setStyleSheet` is more explicit but distributes token references across the codebase. Working assumption for slice A's prompt: hybrid — a project-level stylesheet handles app-wide chrome (background colors, font family, default text color) while per-widget `setStyleSheet` handles widget-specific treatment. Slice A's prompt may revise.

3. **Modal backdrop overlay parent.** The `ModalBackdropOverlay` widget needs a parent — either the main window (overlay is a child of `QMainWindow` and sized to its central widget) or a top-level transparent window above the main window. Slice A's choice; either works. Working assumption: child of main window for simpler parenting and Qt cleanup semantics.

4. **Light vs darker warning-amber.** Design pass §4.4 flags `#B0731A` warning on white as borderline at 12px caption size. If the slice F WCAG check fails, the token value adjusts. Two viable refined values: `#9D6517` (slightly darker, passes AAA) or `#B0731A` at body size only (caption usage of warning text becomes disallowed). Slice F decides if and only if the check fails.

5. **Engagement panel screenshot coverage in slice C.** If v0.5 has shipped by slice C's time, the engagement panel is included in the retrofit and gets its own `slice-C/engagement-panel.png`. If v0.5 has slipped, the engagement panel is not present and slice C's screenshot set omits it. Acceptance criterion C6 lists the expected panels conditional on v0.5 status at slice C land time.

6. **Whether to retire `requirements_window.py`'s `ActiveClientContext`-to-legacy-`ClientContext` bridge in this release.** The bridge is v1 tech debt unrelated to v0.6's visual scope; explicitly out of scope.

---

## 11. Decisions to Be Recorded

Per DEC-014 (every v2 conversation produces a session record) and DEC-025 (`conversation_reference` convention + seed-prompt-in-`topics_covered`), this PRD's authoring conversation (Styling Conversation 2, SES-028) and its decisions are captured in the v2 database at PRD closeout.

Records to write at PRD closeout:

- **SES-028** — Styling Conversation 2 (build planning). Status: Complete. `conversation_reference`: descriptive text per DEC-025 referencing this PRD draft, the `ui-v0.6-implementation-plan.md` draft, and the v0.6 slice build prompts. `topics_covered` opens with a seed-prompt summary (no formal kickoff prompt existed; the conversation worked from the styling design pass and the workstream plan directly) followed by the three architectural decisions resolved.

- **DEC-095** — Version bundling for the styling work: ship as separate v0.6 release rather than bundled into v0.5. Context: workstream plan §6 named the question explicitly. Decision rationale: functional independence of the two workstreams is load-bearing; release versions are v2's primary navigation index; bundling permanently blurs that index. Cost: one additional closeout. Alternatives: bundle into v0.5 (rejected on navigability grounds).

- **DEC-096** — Slice structure for v0.6: six slices A–F. A = Foundation + About; B = Sidebar + master-pane delegate; C = Panel retrofits + ReferencesSection; D = Dialogs + form controls; E = Status + crash banner; F = Closeout. Context: workstream plan §5.3 had a five-slice strawman that buried the master-pane delegate and split governance/methodology retrofits artificially. Decision rationale: pulling the delegate to its own slice avoids artificial coupling; collapsing governance/methodology retrofits avoids redundant review; promoting status surfaces to their own slice separates two distinct concerns. Alternatives: stay close to strawman (rejected on artificial-coupling and redundant-review grounds).

- **DEC-097** — Slice acceptance pattern: per-slice after-state screenshot committed to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/` plus eyeball verification against the design pass; automated WCAG AA contrast check against codified `tokens.py` values at slice F closeout. Context: visual work has different acceptance signals than functional work; needed a pattern. Decision rationale: screenshots become project history and release-note material; eyeball is the appropriate primary signal for a solo developer with the right aesthetic eye; WCAG check is the one automated commitment per design pass A9. Alternatives: automated pixel-measurement (rejected as overkill at this scale); eyeball-only without screenshots (rejected on history-loss grounds).

- **References** — `decided_in` from SES-028 to each of DEC-095, DEC-096, DEC-097. `is_about` from SES-028 to PI-001 (the styling pass parent planning item).

A status update reflecting that UI v0.6 is now in build (phase `"v0.6 in build"`, version label incremented per the closeout sequence) is also appropriate at the same time.

---

*End of document.*
