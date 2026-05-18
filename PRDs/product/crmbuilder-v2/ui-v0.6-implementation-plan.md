# CRMBuilder v2 — UI v0.6 Implementation Plan

**Version:** 0.1
**Last Updated:** 05-16-26 19:15
**Status:** Approved
**Companion PRD:** `ui-PRD-v0.6.md`
**Predecessor plan:** `ui-v0.5-implementation-plan.md` (engagement management; ships first per DEC-105)
**Executing prompt series:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.6-{A..F}-*.md`

---

## Change Log

**Version 0.1 (05-16-26 17:30):** Initial draft. Six-slice breakdown for v0.6 build: foundation + About, sidebar + master-pane delegate, panel retrofits + ReferencesSection, dialogs + form controls, status surfaces + crash banner, closeout. Per DEC-106 reconciled against workstream plan §5.3 strawman. Strictly sequential dependency chain — no parallelism within v0.6.

**Version 0.1 (05-16-26 17:45):** Pre-flight corrections during slice A prompt-drafting. Status transitions from "Draft — pending approval" to "Approved." Same three corrections applied as ui-PRD-v0.6.md's parallel 17:45 entry: (1) `tokens.py` references throughout document corrected to `styling.py` — the v0.1-shipped module is rewritten in place rather than replaced by a new module; (2) About dialog file path corrected from `ui/dialogs/about.py` to `ui/about_dialog.py`; (3) `crud_delete_dialog.py` references removed — `EntityCrudDeleteDialog` shares `ui/base/crud_dialog.py` with `EntityCrudDialog`. Plus §3 directory tree gains a third dialog base I missed (`ui/base/versioned_replace_dialog.py`) and `ui/splash.py` (one consumer of legacy constants that must update). Slice A deliverables list rewritten to reflect the corrected file inventory. No content changes to slice structure or acceptance criteria.

**Version 0.1 (05-16-26 19:15):** Identifier rebase to reflect parallel-workstream-consumed identifiers at close-out time. SES-028 → SES-030; DEC-095/096/097 → DEC-105/106/107. Same rebase applied to companion PRD and all six slice prompts. No content change; numbering only. Per the SES-027 rebase pattern from styling Conversation 1.

---

## 1. Overview

This plan implements the v0.6 desktop UI specified in `ui-PRD-v0.6.md`. v0.6 is decomposed into six independently testable slices, each delivered as its own Claude Code prompt. Each prompt produces a working state of the application that exercises a coherent subset of the PRD's acceptance criteria.

Slice boundaries follow DEC-106's six-slice structure. Slice A delivers the foundation (design tokens module, font and icon asset bundling, loader helpers, modal elevation infrastructure, base widget hooks, About dialog re-skin as the canary). Slice B delivers the shared visual vocabulary (sidebar + master-pane delegate). Slice C retrofits every panel with the token system. Slice D delivers dialogs + form controls + button categories. Slice E delivers status / error / warning surfaces and the crash banner re-skin. Slice F is mechanical closeout (version bump, README, WCAG contrast check, regression pass, status update).

After all six prompts execute cleanly, every acceptance criterion in PRD section 6 is satisfied. The application becomes visually coherent incrementally: after slice A the About dialog renders against the new token system but every other surface is unchanged; after slice B the sidebar and every master pane render the new selected-state vocabulary even though panel chrome and detail panes are still Qt-default; after slice C panels are coherent end-to-end; after slices D and E dialogs and status surfaces complete the picture; after slice F the release is shippable.

```
Slice A (foundation + About dialog)
    │
    └──> Slice B (sidebar + master-pane delegate)
            │
            └──> Slice C (panel retrofits + ReferencesSection)
                    │
                    └──> Slice D (dialogs + form controls)
                            │
                            └──> Slice E (status + crash banner)
                                    │
                                    └──> Slice F (closeout)
```

Slices land strictly in order. There is no parallelism within v0.6 because each slice's visual treatment depends on tokens established by prior slices and on widget hooks landed in slice A. Slice E in particular cannot land before slice D because its surfaces (error dialog, crash banner) re-use the button category styling that slice D establishes.

---

## 2. Implementation Choices

### 2.1 Language and runtime

Unchanged from v0.1–v0.5. Python 3.12+, matching `pyproject.toml`'s `requires-python` pin.

### 2.2 Desktop framework — PySide6

Unchanged.

### 2.3 HTTP client — httpx (sync mode)

Unchanged. v0.6 is visual-only and does not touch the API client.

### 2.4 Subprocess management — QProcess

Unchanged.

### 2.5 File watching — QFileSystemWatcher

Unchanged from v0.5. No new entity types means no new snapshot files to watch.

### 2.6 Test framework — pytest + pytest-qt

Unchanged. `qtbot` and `qapp` fixtures continue. v0.6 adds one new test module (`tests/crmbuilder_v2/ui/test_token_contrast.py`) for the WCAG AA contrast check; no new fixtures.

### 2.7 Logging — Python's standard `logging` module

Unchanged. v0.6 does not change logging behavior.

### 2.8 Threading model

Unchanged.

### 2.9 Error handling

Unchanged at the model layer. Visual treatment of error surfaces changes per slice E (inline form-field errors, panel-level warnings, error dialog header retoken) but the error-typing system itself is unchanged.

### 2.10 Existing dialog framework — `EntityCrudDialog`

`EntityCrudDialog` and `EntityCrudDeleteDialog` (the v0.2 base + v0.3 extensions + v0.4 methodology-entity uses) remain the base. Slice D extends them with the internal context strip per design pass §2.7 and applies the new button-category styling. No new dialog framework additions.

### 2.11 Existing reference-create dialog — `ReferenceCreateDialog`

v0.3's cascading-vocab `ReferenceCreateDialog` is reused unchanged in functional behavior. Slice D applies the dialog chrome and form-control treatment per the design system.

### 2.12 New for v0.6 — token consumption mechanism

Slice A's prompt establishes how tokens are consumed by widgets. The working assumption (slice A's prompt may revise) is hybrid:

- **Project-level QSS stylesheet** applied once at app startup, generated from `styling.py` token values. Handles app-wide chrome: default font family, default text color, base background colors, default `QPushButton` / `QLineEdit` / `QComboBox` treatment.
- **Per-widget `setStyleSheet`** for widget-specific cases where the project-level stylesheet would be too broad or wouldn't disambiguate (e.g., the destructive button category needs explicit per-button class application; the sidebar's selected-state visuals can't be expressed in project-level QSS reliably).
- **Custom paint via `QStyledItemDelegate` subclasses** for cases where neither QSS approach works (the master-pane delegate's left accent bar; sidebar selected-state).

Slice A's prompt enumerates which widgets each mechanism handles. Subsequent slices follow that division without re-litigating it.

### 2.13 New for v0.6 — font and icon asset bundling

Two font families and one icon set are committed to the repo at `crmbuilder-v2/src/crmbuilder_v2/ui/assets/`. Total commit size addition ~750 KB across fonts plus ~50–80 KB across initial Lucide icons. License files (SIL Open Font License for fonts, ISC for Lucide) committed alongside.

Asset paths:

- `assets/fonts/Inter-VariableFont_opsz,wght.ttf` plus `OFL.txt`.
- `assets/fonts/JetBrainsMono-VariableFont_wght.ttf` plus `OFL.txt`.
- `assets/icons/lucide/{kebab-case-name}.svg` per icon plus `LICENSE.txt`.

Font and icon assets are git-tracked (not gitignored). Loading happens at app startup via `QFontDatabase.addApplicationFont()` for fonts; icons load on-demand via the `ui/icons.py` helper.

### 2.14 New for v0.6 — screenshot capture protocol

Per DEC-107, each visual slice (A through E) commits after-state screenshots to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/`. Screenshots are PNG, captured by Doug after running the slice's Claude Code prompt and eyeball-verifying rendering.

The Claude Code prompt for each slice produces the code; Doug runs the application, captures the screenshots, and commits them in a separate operator commit immediately after the prompt's commit lands. The slice's acceptance gate (per PRD §6) is satisfied when both the code commit and the screenshot commit are present on `main`.

Filename convention: `{surface-name}.png` (e.g., `about-dialog.png`, `sidebar.png`, `master-pane-table.png`). Filenames are enumerated per slice in PRD §6. Total v0.6 screenshot count: ~15–20 PNGs at ~100–300 KB each.

### 2.15 New for v0.6 — WCAG contrast check

Slice F adds `tests/crmbuilder_v2/ui/test_token_contrast.py` exercising the WCAG AA contrast check per design pass A9 against every text-on-background combination listed in §4.4 of the design pass. The test uses the `wcag-contrast-ratio` Python library (or equivalent — slice F's prompt picks the specific library) to compute contrast ratios from the codified `styling.py` hex values.

The check is a build gate per DEC-107. Failures are not tolerated; if any combination fails, a token-value adjustment lands in `styling.py` and slice F re-runs.

---

## 3. Directory and File Layout

The UI lives under `crmbuilder-v2/src/crmbuilder_v2/ui/`. v0.6 adds five new modules, two new asset directories, restructures two widgets, retoken-touches every existing panel and dialog. No storage layer changes; no API changes; no migrations.

```
crmbuilder-v2/
└── src/crmbuilder_v2/
    └── ui/
        ├── app.py                              # MODIFIED (slice A) — startup loads bundled fonts; main window applies project-level QSS
        ├── styling.py                          # RESTRUCTURED (slice A) — replaces the v0.1 minimal-QSS-stub contents with the theme-keyed token dict + t() accessor + build_app_stylesheet() + apply_stylesheet(app) entry point. Filename retained for back-compat (DEC-024's stub is what this module was tracking; PI-001 discharges it in place).
        ├── icons.py                            # NEW (slice A) — Lucide loader with runtime color tinting
        ├── elevation.py                        # NEW (slice A) — QGraphicsDropShadowEffect helper
        ├── about_dialog.py                     # RESTRUCTURED (slice A) — wordmark + tagline + vertical metadata list per DEC-094 and design pass §2.8; per-dialog backdrop+elevation hooks (standalone QDialog subclass, not in dialogs/)
        ├── crash_banner.py                     # RESTRUCTURED (slice E) — fold into design system
        ├── splash.py                           # MODIFIED (slice A) — call-site updates from legacy ACCENT_COLOR / DEFAULT_FONT_FAMILY constants to t("color.accent.default") / t("font.family.default")
        ├── sidebar.py                          # MODIFIED (slice B) — visual treatment + selected-state custom rendering
        ├── assets/                             # NEW (slice A)
        │   ├── fonts/
        │   │   ├── Inter-VariableFont_opsz,wght.ttf
        │   │   ├── JetBrainsMono-VariableFont_wght.ttf
        │   │   └── OFL.txt
        │   └── icons/lucide/
        │       ├── pencil.svg
        │       ├── trash-2.svg
        │       ├── rotate-ccw.svg
        │       ├── external-link.svg
        │       ├── copy.svg
        │       ├── plus.svg
        │       ├── x.svg
        │       ├── chevron-right.svg
        │       ├── chevron-down.svg
        │       ├── chevron-up.svg
        │       ├── circle-alert.svg
        │       ├── circle-x.svg
        │       ├── check.svg
        │       ├── asterisk.svg
        │       └── LICENSE.txt
        ├── widgets/
        │   ├── modal_backdrop.py               # NEW (slice A) — full-window overlay widget
        │   ├── master_pane_delegate.py         # NEW (slice B) — shared QStyledItemDelegate
        │   └── references_section.py           # RESTRUCTURED (slice C) — sub-sectioned plain-list rendering
        ├── base/
        │   ├── list_detail_panel.py            # MODIFIED (slices A, C) — token-consuming chrome; label-above form support
        │   ├── crud_dialog.py                  # MODIFIED (slices A, D) — token-consuming chrome; elevation + backdrop hooks; both EntityCrudDialog and EntityCrudDeleteDialog live in this file (no separate crud_delete_dialog.py); context strip + button-category application in slice D
        │   └── versioned_replace_dialog.py     # MODIFIED (slices A, D) — token-consuming chrome; elevation + backdrop hooks (covers Charter + Status replace dialogs); button-category application in slice D
        ├── panels/
        │   ├── sessions.py                     # MODIFIED (slice C) — token absorption + label-above form
        │   ├── decisions.py                    # MODIFIED (slice C)
        │   ├── risks.py                        # MODIFIED (slice C)
        │   ├── planning_items.py               # MODIFIED (slice C)
        │   ├── topics.py                       # MODIFIED (slice C)
        │   ├── references_panel.py             # MODIFIED (slice C)
        │   ├── charter.py                      # MODIFIED (slice C)
        │   ├── status.py                       # MODIFIED (slice C)
        │   ├── domains.py                      # MODIFIED (slice C)
        │   ├── entities.py                     # MODIFIED (slice C)
        │   ├── processes.py                    # MODIFIED (slice C) — also _WARNING_STYLE update from danger-red to warning-amber (slice E)
        │   ├── crm_candidates.py               # MODIFIED (slice C)
        │   └── engagement.py                   # MODIFIED (slice C) — if v0.5 has shipped by slice C land time per DEC-105
        ├── dialogs/
        │   ├── error.py                        # MODIFIED (slices A, E) — token-consuming chrome + elevation/backdrop hooks (standalone QDialog); header retoken with circle-x icon + danger-text in slice E
        │   ├── reference_delete.py             # MODIFIED (slice A) — elevation + backdrop hooks (standalone QDialog subclass, does not inherit from EntityCrudDeleteDialog)
        │   └── (other dialogs)                 # MODIFIED (slice D) — context strip + button-category application via the crud_dialog and versioned_replace_dialog bases; no per-file edit needed for any subclass of those bases (decision_create/edit/delete, planning_item_*, risk_*, topic_*, session_create, domain_crud, entity_crud, process_crud, crm_candidate_crud, charter_replace, status_replace, reference_create — all inherit hooks via base)
        └── (no separate crud_delete_dialog.py — both CRUD bases live in crud_dialog.py)

crmbuilder-v2/
├── README.md                                   # MODIFIED (slice F) — v0.6 release-note entry
└── src/crmbuilder_v2/__init__.py               # MODIFIED (slice F) — __version__ = "0.6.0"

PRDs/product/crmbuilder-v2/
└── styling-screenshots/                        # NEW (slices A-E, operator commits)
    ├── slice-A/
    │   └── about-dialog.png
    ├── slice-B/
    │   ├── sidebar.png
    │   ├── master-pane-table.png
    │   ├── master-pane-tree.png
    │   └── master-pane-soft-deleted.png
    ├── slice-C/
    │   ├── sessions-panel.png
    │   ├── decisions-panel.png
    │   ├── ... (one per affected panel)
    │   └── references-section-multi-kind.png
    ├── slice-D/
    │   ├── edit-dialog-with-context-strip.png
    │   ├── delete-confirm-dialog.png
    │   ├── button-states-primary.png
    │   ├── button-states-secondary.png
    │   ├── button-states-destructive.png
    │   └── form-controls.png
    └── slice-E/
        ├── inline-field-error.png
        ├── inline-panel-warning.png
        ├── error-dialog.png
        └── crash-banner.png

tests/crmbuilder_v2/ui/
└── test_token_contrast.py                      # NEW (slice F) — WCAG AA contrast verification
```

No new entries under `access/`, `api/`, or `migrations/`. v0.6 is visual-only.

---

## 4. Build Sequence

Each slice lands as one commit (or a small handful, plus an operator-authored screenshot commit). Slice prefixes are `v2:` per the v2 convention. PRD acceptance criteria from §6 are cross-referenced as `AC#N`.

### Slice A — Foundation + About dialog

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation.md`

**Deliverables:**

- `ui/styling.py` **rewritten in place** — the v0.1 minimal-QSS-stub contents are replaced end-to-end. New content: the `TOKENS: dict[str, dict[str, str]]` dict with the `"light"` theme key codifying every value from design pass §1; the `t(key, theme="light") -> str` accessor; the `build_app_stylesheet(tokens) -> str` function; the `apply_stylesheet(app)` entry point preserved. Legacy constants (`ACCENT_COLOR`, `ACCENT_HOVER`, `ERROR_TEXT_COLOR`, `DEFAULT_FONT_FAMILY`, `DEFAULT_FONT_POINT_SIZE`) removed. Module docstring rewritten to state its new purpose and reference DEC-024 / DEC-076 / PI-001.
- `ui/splash.py` updated: legacy `ACCENT_COLOR` and `DEFAULT_FONT_FAMILY` imports replaced with `t` from `styling`; call sites use `t("color.accent.default")` and `t("font.family.default")`.
- `ui/assets/fonts/` populated with Inter Variable (`Inter-VariableFont_opsz,wght.ttf` from `rsms/inter` GitHub releases) and JetBrains Mono Variable (`JetBrainsMono-VariableFont_wght.ttf` from `JetBrains/JetBrainsMono` GitHub releases), plus `OFL.txt` license file. `ui/app.py` modified to load both at startup via `QFontDatabase.addApplicationFont()` before the main window opens, with fall-back to system defaults if loading fails (no app-blocking).
- `ui/assets/icons/lucide/` populated with the initial wave (14 icons per PRD §2 item 3) plus `LICENSE.txt`. `ui/icons.py` providing `lucide(name, size=16, color_token="color.neutral.700") -> QIcon` with runtime SVG color tinting via the token system. Module-level `(name, size, color_token)` cache; no invalidation (SVG files don't change at runtime).
- `ui/elevation.py` providing `apply_dialog_shadow(dialog: QDialog) -> None` that applies `QGraphicsDropShadowEffect` per `shadow.dialog` to the dialog instance.
- `ui/widgets/modal_backdrop.py` providing the `ModalBackdropOverlay` widget plus module-level `attach(dialog)` / `detach(dialog)` functions. Internal `_active_dialogs: set[QDialog]` toggles visibility. Parented to `QMainWindow.centralWidget()`. Fade-in via `QPropertyAnimation` on `windowOpacity` (or `QGraphicsOpacityEffect` if `windowOpacity` doesn't render correctly on overlay widgets — slice A prompt picks).
- Per-dialog elevation + backdrop hooks added to **five files** total (covers every `QDialog` subclass in the v2 codebase via base classes plus three standalone subclasses):
  - `ui/base/crud_dialog.py` — covers both `EntityCrudDialog` and `EntityCrudDeleteDialog` (single file containing both bases) and every dialog subclass.
  - `ui/base/versioned_replace_dialog.py` — covers `CharterReplaceDialog` and `StatusReplaceDialog`.
  - `ui/about_dialog.py` — standalone `QDialog` subclass at `ui/` top level.
  - `ui/dialogs/error.py` — standalone `QDialog` subclass.
  - `ui/dialogs/reference_delete.py` — standalone `QDialog` subclass (does not inherit from `EntityCrudDeleteDialog`).
- `ui/base/list_detail_panel.py` extended with token-consuming chrome — panel content background, outer padding, splitter handle treatment per design pass §2.2 — applied via project-level QSS plus class-name hooks.
- Project-level QSS stylesheet generation in `ui/styling.py`: the `build_app_stylesheet(tokens)` function produces the QSS string from the token dict. Applied via `QApplication.setStyleSheet(build_app_stylesheet(TOKENS["light"]))` at app startup in `ui/app.py` right after font loading.
- `ui/about_dialog.py` restructured per design pass §2.8 and DEC-094 — wordmark "CRMBuilder v2" in heading-2 semibold, tagline "Declarative CRM deployment and methodology authoring" in small caption, two-line-per-row vertical metadata list with mono-font path values, single right-aligned "Close" button. Minimum width preserved at 440px. (At `ui/about_dialog.py`, NOT `ui/dialogs/about.py` — there is no `about.py` in `dialogs/`.)

**Acceptance gates:**

- AC A1 (`styling.py` rewritten in place; exposes theme-keyed values via the `TOKENS` dict)
- AC A2 (fonts load at startup; default font is Inter at body size)
- AC A3 (Lucide loader returns correctly-tinted icons for at least three colors)
- AC A4 (modal elevation applies to every `QDialog` subclass without per-dialog modification)
- AC A5 (About dialog renders per design pass §2.8)
- AC A6 (About dialog screenshot committed by Doug to `styling-screenshots/slice-A/about-dialog.png`)
- AC A7 (v0.5 test suite continues green)

**Out of slice:** sidebar visual treatment (slice B); master-pane delegate (slice B); any other panel chrome beyond `list_detail_panel.py`'s base hooks (slice C).

---

### Slice B — Sidebar + master-pane delegate

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-B-sidebar-and-master-pane.md`

**Deliverables:**

- `ui/sidebar.py` modified per design pass §2.1: 220px container width with `color.neutral.100` background; right-edge 1px hairline border in `color.neutral.200`; non-selectable group headers in `font.size.caption` `font.weight.semibold` `color.neutral.500` with `+0.04em` letter-spacing; 32px-tall entries in `font.size.body`; selected-state custom rendering (3px left accent bar + `color.accent.subtle` background + `color.neutral.900` medium-weight text) per DEC-093; hover state with background-only treatment (no bar); focus state matches selected plus 1px focus ring; stale-indicator dot color flipped from legacy `#1F3864` to `color.accent.default`.
- `ui/widgets/master_pane_delegate.py` providing the shared `QStyledItemDelegate` per design pass §2.3 and DEC-093: 28px row height; 1px row dividers in `color.neutral.200`; column header treatment with `font.size.small` `font.weight.semibold` `color.neutral.700` text on `color.neutral.100` background; hover-state row tinting in `color.neutral.100`; selected-state row treatment matching sidebar (3px left accent bar + `color.accent.subtle` background + medium-weight text); soft-deleted-row treatment (50% text contrast plus leading Lucide `trash-2` icon in identifier column); identifier-column mono-font rendering.
- Tree-view variant support in the delegate for the Topics panel: Lucide `chevron-right` (collapsed) and `chevron-down` (expanded) at 12px in `color.neutral.500` replacing Qt's default branch indicator; `space.4` (16px) indentation per level; selected-state left accent bar respects indentation per design pass §2.3.
- Master-pane delegate registered on every existing panel's view via one-line registration in each panel's `_create_master_widget` method. Affected panels: all 12 panels currently in `ui/panels/` (Sessions, Decisions, Risks, Planning Items, Topics, References, Charter, Status, Domains, Entities, Processes, CRM Candidates) plus v0.5's Engagement panel if shipped.
- No panel chrome retoken (panel content background, outer padding, splitter handle) in this slice — that lands in slice C. The slice B prompt verifies each panel's master pane renders correctly post-registration but does not touch the surrounding panel chrome.

**Acceptance gates:**

- AC B1 (sidebar renders per §2.1)
- AC B2 (sidebar selected-state per DEC-093 with all three sub-treatments — bar, background, text)
- AC B3 (stale-indicator dot color updated)
- AC B4 (master-pane delegate registered everywhere; new selected-state vocabulary on every panel's master view)
- AC B5 (Topics tree-view variant uses Lucide chevrons; 16px indentation per level)
- AC B6 (four screenshots committed to `slice-B/`)
- AC B7 (v0.5 test suite continues green)

**Out of slice:** panel chrome retoken (slice C); detail-pane form layout (slice C); ReferencesSection rendering (slice C).

---

### Slice C — Panel retrofits + ReferencesSection

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-C-panel-retrofits.md`

**Deliverables:**

- Panel chrome retoken across all 12 (or 13) panels: `color.neutral.50` panel content background per design pass §2.2; 16px outer padding; `QSplitter` retained with `space.3` (12px) handle width, `color.neutral.100` handle background, centered 1px hairline divider in `color.neutral.300`; default split ratio set to 45/55 master/detail.
- Detail-pane form layout changed from `QFormLayout` (label-left) to label-above per design pass §2.4. The change is structural — modifies the per-panel detail-pane construction code. Pattern is uniform across panels: label in `font.size.small` `font.weight.medium` `color.neutral.700` with `space.1` (4px) margin below before the field, fields in 28px height, 12px between rows. Required-field marker as Lucide `asterisk` icon at 10px in `color.danger.text` immediately after label text (replaces any current "Required" word or asterisk character).
- Editable field state coverage applied via class-based QSS rules: default (`color.neutral.0` background + 1px `color.neutral.300` border), focused (1px `color.accent.default` border + `color.accent.focusring` outline 2px outside), error (1px `color.danger.default` border), disabled (`color.neutral.100` background + 1px `color.neutral.200` border + `color.neutral.300` text).
- Read-only field treatment via separate class-based QSS rule: `color.neutral.100` background, no visible border (or `border.hairline` if layout demands), `color.neutral.700` text. Visually distinct from disabled.
- Status combo per design pass §2.4 on every panel that has a status field (Domains, Entities, CRM Candidates): "Valid transitions: <enum-1>, <enum-2>" hint caption below the combo in `font.size.caption` `color.neutral.500`.
- Notes collapsible toggle per design pass §2.4: Lucide `chevron-right` / `chevron-down` at 14px in `color.neutral.700` followed by "Notes" label in `font.size.small` `font.weight.medium` `color.neutral.700`. Click anywhere on the toggle row collapses/expands.
- Section grouping within detail pane: `space.6` (24px) vertical space between major sections (identifier+name+status block; description; notes; ReferencesSection). No section dividers — spacing alone carries the break.
- `ui/widgets/references_section.py` restructured to render sub-sectioned plain-list per design pass §2.4: per-kind sub-section headers in `font.size.small` `font.weight.semibold` `color.neutral.700` (title-cased kind names — "Decided in", "Is about", "Hands off to", "Receives from", "Supersedes", "Superseded by", "References"); entry rows below each header with identifier in `font.family.mono` at `font.size.small` `color.neutral.700` followed by `space.3` then title in `font.size.body` `color.neutral.800`; sub-sections separated by `space.4` (16px); entry-hover tint `color.neutral.50`; existing right-click context menu behavior unchanged; "Add reference" text-only button below the last sub-section with Lucide `plus` icon plus label in `color.accent.default`; empty-state line "No references" in `color.neutral.500` followed by "Add reference" button on the next row when no references registered.

**Acceptance gates:**

- AC C1 (panel chrome per §2.2)
- AC C2 (label-above form layout with required-asterisk icon)
- AC C3 (full editable field state coverage)
- AC C4 (status combo hint caption on panels with status)
- AC C5 (ReferencesSection sub-sectioned plain-list rendering with multi-kind verification)
- AC C6 (one screenshot per affected panel committed to `slice-C/`, plus the multi-kind ReferencesSection screenshot)
- AC C7 (v0.5 test suite continues green)

**Out of slice:** dialogs (slice D); buttons (slice D); status-surface inline-error treatment (slice E); crash banner (slice E).

---

### Slice D — Dialogs + form controls

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-D-dialogs-and-form-controls.md`

**Deliverables:**

- Dialog chrome per design pass §2.7 applied to every `QDialog` subclass via the existing `EntityCrudDialog` and `EntityCrudDeleteDialog` bases: `color.neutral.0` container background; 20px (`space.5`) inner padding; `radius.dialog` (6px) where platform renders; drop shadow + backdrop overlay already wired in slice A.
- Internal context strip per design pass §2.7 on record-editing dialogs (the `EntityCrudDialog` subclasses, not the create-new variants and not About / delete-confirm): anchored at top of dialog body flush with OS title bar; `color.neutral.100` background; 12px (`space.3`) padding all sides; hairline 1px `color.neutral.200` below; content is identifier in `font.family.mono` at `font.size.small` `color.neutral.700` `font.weight.medium` followed by `space.3` then record name in `font.size.body` `color.neutral.800` (truncates with ellipsis on overflow). The strip is added via one extension to `EntityCrudDialog.__init__` rather than per-dialog edits.
- Five button categories per design pass §2.5 with full state coverage. Each category is implemented as a class name applied via `setProperty("buttonCategory", "primary" | "secondary" | "destructive" | "text" | "icon-only")`; the project-level QSS stylesheet (from slice A) carries the per-category state-aware rules. Default button category for any `QPushButton` without an explicit assignment is Secondary. Per-dialog button assignments codified in slice D's prompt (Save/Apply → Primary; Cancel → Secondary; Delete → Destructive; "Add reference" and similar → Text/Link; toolbar refresh and show-deleted toggle → Icon-only).
- The legacy `#c1272d` red and `#b6868a` disabled-destructive treatment removed from `dialogs/reference_delete.py` and `base/crud_dialog.py` (they get the Destructive class-name treatment instead).
- Form control state coverage per design pass §2.6: text input at 28px height with placeholder text in `color.neutral.500` regular weight; multi-line text at 80px minimum height with the same border/state treatment; combo box with right-side Lucide `chevron-down` at 14px in `color.neutral.500` plus properly-tokenized dropdown popup (background `color.neutral.0`, border 1px `color.neutral.300`, `radius.subtle`, drop shadow per `shadow.dialog`; items at 28px height with hover tint `color.neutral.100` and selected-item background `color.accent.subtle`); checkbox at 16×16 with Lucide `check` icon at 12px when checked plus full state coverage.
- Inline error message rendering below text inputs: `font.size.caption` `color.danger.text`, `space.1` (4px) below the field. Paired with red field border per slice C's editable-field error state. The message itself is set via the existing form-validation flow; slice D's work is the visual treatment.
- Delete-confirm dialogs per design pass §2.7 delete-specific treatment: no internal context strip (the prose contains the deletion target inline); body content as single paragraph in `font.line.relaxed` (1.6); destructive button right-aligned with Cancel to its left.
- Tab order across forms: top-to-bottom following form-row order with Save → Cancel → Delete at the end; `Tab` advances and `Shift+Tab` reverses per Qt convention. Initial focus on dialog open: first editable field, not the Save button.

**Acceptance gates:**

- AC D1 (internal context strip on record-editing dialogs)
- AC D2 (five button categories with full state coverage; legacy red treatments removed)
- AC D3 (form control treatment for text input, multi-line, combo, checkbox)
- AC D4 (delete-confirm dialogs per §2.7)
- AC D5 (six screenshots committed to `slice-D/`)
- AC D6 (v0.5 test suite continues green)

**Out of slice:** status / error / warning panel-level surfaces (slice E); crash banner (slice E); WCAG check (slice F).

---

### Slice E — Status, error, warning + crash banner

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-E-status-and-crash-banner.md`

**Deliverables:**

- Inline form-field error styling — already established in slice D as part of form control state coverage. Slice E's responsibility for this is to verify the rendering matches design pass §2.9 across multiple panels (no new code; smoke-test coverage).
- Inline panel-level warnings per design pass §2.9: single-row callout layout with Lucide `circle-alert` icon at 14px in `color.warning.default`, `space.2` (8px) horizontal space, then warning text in `font.size.small` `color.warning.default` regular weight. Applied to `panels/processes.py`'s soft-deleted-domain warning by changing the existing `_WARNING_STYLE = "color: #B22222;"` to use `color.warning.default` (amber, not danger-red) — the soft-deleted-domain message is informational, not error.
- Error dialog (`dialogs/error.py`) header retoken per design pass §2.9: leading Lucide `circle-x` icon at 18px in `color.danger.default`; `space.3` (12px) horizontal space; title in `font.size.heading_3` (18px) `font.weight.semibold` `color.danger.text`; `space.4` (16px) of vertical margin below the header before body content. The legacy `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` constant is removed from the file. Body content rendering and the `{data, meta, errors}` envelope handling are unchanged.
- Crash banner (`ui/crash_banner.py`) re-skinned per design pass §2.10: background `color.danger.default`; text in `color.neutral.0` (white) at `font.size.body` (14px) `font.weight.medium`; padding 12px (`space.3`) vertical × 16px (`space.4`) horizontal; leading Lucide `circle-alert` icon at 16px in `color.neutral.0` with `space.2` of horizontal space before the message text. Banner buttons treated as semi-transparent white-on-color per design pass §2.10: default background `color.neutral.0` at 15% alpha, border 1px `color.neutral.0` at 25% alpha, text `color.neutral.0`, `radius.subtle`; hover background `color.neutral.0` at 30% alpha; pressed at 45% alpha; focused with 1px focus ring in `color.neutral.0` at 60% alpha drawn 2px outside. The legacy `_BANNER_BACKGROUND` and bespoke button-style constants removed from the file. Banner layout otherwise unchanged: always-on-top at the main window, full window width, persists until dismissed or underlying error resolved.

**Acceptance gates:**

- AC E1 (inline form-field error rendering verified)
- AC E2 (inline panel-level warning callout on Processes panel)
- AC E3 (error dialog header retoken; legacy `_BANNER_STYLE` removed)
- AC E4 (crash banner re-skinned; legacy `_BANNER_BACKGROUND` removed)
- AC E5 (four screenshots committed to `slice-E/`)
- AC E6 (v0.5 test suite continues green)

**Out of slice:** version bump (slice F); README (slice F); WCAG contrast check (slice F); status update (slice F).

---

### Slice F — Closeout

**Prompt:** `CLAUDE-CODE-PROMPT-v2-ui-v0.6-F-closeout.md`

**Deliverables:**

- `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` set to `"0.6.0"`.
- README at `crmbuilder-v2/README.md` extended with a v0.6 release-note entry matching v0.5's format: one-paragraph summary plus a bullet list of release highlights (design tokens module, bundled fonts, bundled icons, five button categories, master-pane delegate, sub-sectioned ReferencesSection, modal elevation, retired legacy colors).
- `tests/crmbuilder_v2/ui/test_token_contrast.py` added — exercises the WCAG AA contrast check per DEC-107 against every text-on-background combination listed in design pass §4.4. Uses an established Python WCAG-contrast library (slice F's prompt picks the specific library; `wcag-contrast-ratio` is a candidate). The test is parameterized over the codified combinations from §4.4 (body text on neutral.0; secondary text on neutral.0; read-only text on neutral.100; accent on neutral.0; danger text on neutral.0; warning on neutral.0; white on accent; white on danger). Each combination asserts the computed ratio meets AA at its target text size.
- Full regression test pass: `uv run pytest tests/crmbuilder_v2/ -v` returns green across the full suite (v0.5 tests + the new WCAG contrast test module).
- Final integration smoke: open the desktop app, confirm the About dialog shows v0.6.0; open each panel and confirm rendering matches the design system end-to-end; open each dialog category (create, edit, delete-confirm, references-attach, About, error) and confirm chrome / buttons / fields render per the design pass.

**Acceptance gates:**

- AC F1 (`__version__` is "0.6.0"; About dialog shows v0.6.0)
- AC F2 (README has v0.6 release-note entry)
- AC F3 (full pytest suite passes including new WCAG test module)
- AC F4 (WCAG contrast check passes for every combination)
- AC F5 (status entity updated from "v0.5 complete" to "v0.6 complete" via versioned-replace)
- AC F6 (cumulative roll-up: all prior slices' acceptance criteria pass)
- AC F7 (SES-030 + DEC-105/096/097 + references drafted in close-out payload)

**Out of slice:** status-entity versioned-replace (authored through the desktop UI by the operator after slice F lands, not in Claude Code); SES-030 session record application (operator runs the close-out apply prompt after slice F lands); next-release planning.

---

## 5. Migration Ordering

None. v0.6 is visual-only and ships zero Alembic migrations. The migration ordering section is preserved in this plan for format consistency with prior implementation plans, but `crmbuilder-v2/migrations/` is unchanged.

---

## 6. Test Target

`uv run pytest tests/crmbuilder_v2/ -v` continues as the test target across all six slices. Each slice's acceptance gate includes the requirement that the prior slices' tests continue to pass — every slice is acceptance-gated on the cumulative test suite.

Test counts per slice (estimates):

- Slice A: ~0 new tests; the foundation work is verified by eyeball + screenshot per the About dialog being a functional surface that exercises the full token system. Existing v0.5 test suite must continue passing.
- Slice B: ~0 new tests; sidebar and master-pane delegate verified by eyeball + screenshot.
- Slice C: ~0 new tests; panel retrofits verified by eyeball + screenshot.
- Slice D: ~0 new tests; dialogs and form controls verified by eyeball + screenshot.
- Slice E: ~0 new tests; status surfaces and crash banner verified by eyeball + screenshot.
- Slice F: ~8–12 new tests in `test_token_contrast.py` — one per WCAG combination listed in design pass §4.4.

Estimated cumulative new tests for v0.6: ~8–12, all in the slice F WCAG contrast module. The numbers are small because v0.6 is visual; visual verification is screenshot-based per DEC-107 rather than test-based. The v0.5 test suite carries the regression net.

---

## 7. Screenshot Capture Protocol

Per DEC-107, slices A through E each commit after-state screenshots to `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/`. The protocol:

1. Doug runs the slice's Claude Code prompt against the local checkout. The prompt produces the code commit on `main` and pushes.
2. Doug pulls the updated `main` to the local checkout.
3. Doug launches the application via `uv run crmbuilder` (or the equivalent v2 launcher command).
4. Doug navigates to each surface listed in the slice's screenshot deliverable list (per PRD §6) and captures the screenshot.
5. Doug places the PNG files at `PRDs/product/crmbuilder-v2/styling-screenshots/slice-{X}/{surface-name}.png` per the naming convention.
6. Doug commits the screenshots as a single operator commit prefixed `v2: ui v0.6 slice {X} screenshots — {brief description}` and pushes.

The slice is acceptance-complete when both the code commit (from the Claude Code prompt) and the operator screenshot commit are present on `main`.

Screenshots are PNG, captured at the natural rendering size of the surface (not full-screen unless the surface fills the screen). Resolution is whatever Doug's display produces; HiDPI is expected. File sizes typically 100–300 KB each.

---

## 8. Version Source

Per the CLAUDE.md v2 version-source convention, `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is the single source of the version string. The About dialog reads via `importlib.metadata` with `__version__` as fallback.

Slice F sets `__version__` to `"0.6.0"`. No other file carries the version.

---

## 9. Closeout Discipline

After slice F passes, the operator (Doug) writes:

- The session record for the styling Conversation 2 (this conversation, SES-030) by running the close-out apply prompt at `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-030.md` — the apply prompt POSTs SES-030 + DEC-105 + DEC-106 + DEC-107 + references via `apply_close_out.py` per the SES-025/026/027 precedent. The close-out apply prompt is authored at the end of this same conversation alongside the close-out payload `close-out-payloads/ses_030.json`.
- The session records for any Claude Code slice-execution conversations that contributed to v0.6 build, written at the close of each slice's execution conversation per DEC-014 + DEC-029.
- The status-entity versioned-replace update from `"v0.5 complete"` to `"v0.6 complete"` through the desktop versioned-replace dialog.

None of the above are produced inside Claude Code slices A–F; all are operator-authored after slice F's code work completes.

---

*End of document.*
