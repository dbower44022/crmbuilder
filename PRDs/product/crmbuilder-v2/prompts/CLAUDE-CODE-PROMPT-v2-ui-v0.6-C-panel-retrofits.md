# CLAUDE-CODE-PROMPT-v2-ui-v0.6-C-panel-retrofits

**Last Updated:** 05-16-26 18:20
**Series:** v2-ui-v0.6
**Slice:** C (3 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.6-B (sidebar + master-pane delegate)

## Purpose

Slice **C — Panel retrofits + ReferencesSection** delivers the panel-level visual coherence promised by v0.6. After slices A (foundation) and B (sidebar + master-pane delegate) land, panel chrome is still partly Qt-default and detail panes still use label-left form layout. Slice C closes that gap across every panel.

Seven deliverables:

1. **Panel chrome retoken** across all panels — confirms `color.neutral.50` background, 16px outer padding, splitter handle at 12px width with hairline divider, default 45/55 master/detail split. Slice A's `ListDetailPanel` base already carries the hooks; slice C verifies application across all subclasses and adds the same chrome to `VersionedPanel`-based panels.

2. **Label-above form layout EVERYWHERE.** Every `QFormLayout` in the codebase (panel detail-pane builders + `crud_dialog.py` base + `versioned_replace_dialog.py` base + any per-dialog forms) gets `setRowWrapPolicy(QFormLayout.WrapAllRows)` applied. The `build_app_stylesheet()` function in `styling.py` gains a QSS rule for `QFormLayout QLabel` applying the design pass §2.4 label treatment.

3. **Required-field marker.** New helper `required_label(text: str) -> QLabel` in `ui/base/list_detail_panel.py` (or a sibling helpers module) returning a QLabel with Lucide `asterisk` icon at 10px in `color.danger.text` prepended to the label text. Panel detail-pane builders adopt the helper for required fields.

4. **Editable field state coverage.** QSS rules added to `build_app_stylesheet()` covering the four state classes per design pass §2.4: default (1px `color.neutral.300` border), focused (1px `color.accent.default` border + focus ring), error (1px `color.danger.default` border), disabled (`color.neutral.100` background + `color.neutral.200` border + `color.neutral.300` text). Plus a separate rule for read-only field treatment via a QSS class hook (`QLineEdit[readOnly="true"]` or equivalent).

5. **Status combo "Valid transitions" hint caption.** Each panel with a status field (Domains, Entities, CRM Candidates) gets a sibling `QLabel` below its status combo. The caption renders "Valid transitions: <enum-1>, <enum-2>" computed from the propose-verify successor set. Slice C provides a code pattern.

6. **Notes collapsible toggle.** Existing notes field collapsible toggle (currently a flat `QToolButton`) gains the design pass §2.4 treatment: Lucide `chevron-right` / `chevron-down` at 14px in `color.neutral.700` followed by "Notes" label in `font.size.small` `font.weight.medium`. Click anywhere on the toggle row collapses/expands.

7. **ReferencesSection sub-sectioned plain-list rendering.** `ui/widgets/references_section.py` rewritten internally for the design pass §2.4 layout. Public API preserved (constructor signature, `navigate_requested` signal, `references_changed` signal, `Add reference` button behavior, right-click context menu). The grouping model changes from (direction → type) two-level to per-(direction, type) kind-labeled sub-sections.

This slice does NOT add: dialog chrome retoken beyond what's needed for label-above (slice D); internal context strip on record-editing dialogs (slice D); button categories (slice D); form-control state coverage beyond editable/disabled/read-only QSS (slice D adds combo dropdown popup, checkbox treatment); inline form-field error message rendering (slice D adds the message; the field's red border is in slice C); status / error / warning panel-level surfaces (slice E); crash banner (slice E); `__version__` (slice F).

## Project context

Slices A and B landed the foundation and the shared selected-state vocabulary. After slice B, every panel's master pane renders with the new vocabulary but panel chrome (background, padding, splitter) is mostly Qt-default and detail panes still use label-left `QFormLayout`. Slice C closes both gaps.

Slice C is the largest slice by file count: 12+ panels touched, the `ReferencesSection` widget rewritten internally, two dialog bases updated for `WrapAllRows`, the `build_app_stylesheet()` function gains 5–8 new QSS rules. Per DEC-107's screenshot acceptance pattern, slice C's after-state screenshots are the most numerous (one per panel plus the multi-kind ReferencesSection example).

The retrofit pattern is highly uniform across panels: apply tokens (already done by slice A's `ListDetailPanel` chrome hooks), apply `WrapAllRows` to the panel's `QFormLayout`, adopt the `required_label` helper for required fields, add status combo caption where applicable. Slice C's prompt describes the pattern once and trusts the prompt-runner to apply it uniformly, verifying with the screenshot suite.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean.
3. Confirm git identity: `Doug Bower` / `dbower44022@users.noreply.github.com`.
4. Pull latest: `git pull --rebase origin main`. Slices A and B must be on `main`.
5. Verify slices A and B are in place:
   - `ui/styling.py` rewritten with `TOKENS` dict and `build_app_stylesheet()`.
   - `ui/widgets/master_pane_delegate.py` exists with `MasterPaneDelegate` and `MasterPaneTreeDelegate`.
   - `ui/sidebar.py` modified with `SidebarItemDelegate`.
   - App launches; About dialog and sidebar render per slices A/B specifications.
6. Confirm storage operational at `http://127.0.0.1:8765/health`; start in background if needed.
7. Confirm v0.5 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`.
8. Note the actual panel files in `ui/panels/`. Per the implementation plan, expected: 12 panels (Sessions, Decisions, Risks, Planning Items, Topics, References, Charter, Status, Domains, Entities, Processes, CRM Candidates) plus v0.5's engagement panel (likely `engagements.py` plural per v0.5 test-file naming). Verify the actual filename of the engagement panel and add to the retrofit list.

## Reading order

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (focus: §2 items 9, 10; §4.6, 4.7 partial; §6 ACs C1–C7).
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (focus: §4 Slice C).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (focus: §2.2 panel chrome, §2.4 detail pane).
5. v2 source files:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` — `build_app_stylesheet()` gets new rules.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — `required_label` helper, label-above form layout pattern, splitter chrome.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_panel.py` — same retrofit for versioned-panel-based panels.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — `WrapAllRows` on the `QFormLayout` used by both bases.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py` — same.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py` — internal rewrite for sub-sectioned plain-list.
   - All `crmbuilder-v2/src/crmbuilder_v2/ui/panels/*.py` — retrofit pattern applied per panel.

## Step 1 — Pre-retrofit verification

Audit every panel file and:

- Identify the panel's `QFormLayout` instance(s) for the detail pane.
- Identify any required fields (per the existing v0.5 schema definitions in `dialogs/_*_schema.py` — `required: True` flags).
- Identify whether the panel has a status field (Domains, Entities, CRM Candidates expected).
- Verify the engagement panel filename (likely `engagements.py` plural; confirm by `find ui/panels/`).
- Identify any panel using a layout pattern other than `QFormLayout` for its detail pane; pause-and-report if any.

Produce a table per panel: filename → has-QFormLayout → required-fields-list → has-status-combo. Use this table to drive Steps 4–7's per-panel work.

### 1.1 Acceptance verification (Step 1)

Audit table produced. Engagement panel filename confirmed. Any panel using a non-`QFormLayout` detail-pane layout is flagged and reported.

## Step 2 — `build_app_stylesheet()` additions

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py`'s `build_app_stylesheet(tokens)` function to add the rules below.

### 2.1 Form layout label rule

```
QFormLayout QLabel {
    font-size: <font.size.small>;
    font-weight: <font.weight.medium>;
    color: <color.neutral.700>;
    padding-top: <space.1>;
}
```

Applies app-wide. Picks up the design pass §2.4 label treatment for every QFormLayout-managed label in panels and dialogs.

### 2.2 Editable field state coverage

Default `QLineEdit`, `QComboBox`, `QPlainTextEdit` rules already exist from slice A's minimal styling; slice C extends with:

```
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid <color.accent.default>;
    /* focus ring drawn via QPainter overlay; cannot reliably express as outline in QSS for input widgets */
}

QLineEdit[fieldState="error"], QComboBox[fieldState="error"], QPlainTextEdit[fieldState="error"] {
    border: 1px solid <color.danger.default>;
}

QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled {
    background: <color.neutral.100>;
    border: 1px solid <color.neutral.200>;
    color: <color.neutral.300>;
}

QLineEdit[readOnly="true"], QPlainTextEdit[readOnly="true"] {
    background: <color.neutral.100>;
    border: 1px solid <color.neutral.200>;
    color: <color.neutral.700>;
}
```

The error state uses a custom dynamic property `fieldState` rather than QSS pseudo-states because Qt's QSS doesn't have a standard "error" pseudo-state. Panels apply via `field.setProperty("fieldState", "error")` and re-apply style via `field.style().polish(field)` when toggling.

The focus-ring outline (per design pass §2.4) is harder — Qt's QSS `outline` property doesn't apply to input widgets reliably. Per slice C's prompt-runner judgment: either accept that the focus ring is visually a 1px accent border (without the 2px-outside outline), or add a small `QWidget` overlay on focused input widgets via an event filter. The simpler "border-only" treatment is acceptable for v0.6; deferred enhancement.

### 2.3 ReferencesSection sub-section header rule (optional QSS support)

```
QLabel[role="references-kind-header"] {
    font-size: <font.size.small>;
    font-weight: <font.weight.semibold>;
    color: <color.neutral.700>;
}
```

The widget can set the `role` property on its sub-section headers; the QSS rule then handles styling without per-widget `setStyleSheet` calls. Same pattern as the v0.1-shipped `QLabel[role="error"]` convention.

### 2.4 Acceptance verification (Step 2)

After this step, opening any panel renders editable fields with the new border colors and disabled treatment (visible by tabbing into a field — focus border changes to accent). Read-only fields render with the gray background per the QSS rule.

## Step 3 — `required_label` helper

In `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` (or a sibling `ui/widgets/form_helpers.py` if cleaner), add:

```python
from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t

def required_label(text: str) -> QLabel:
    """Build a form label with a leading required-field asterisk icon."""
    label = QLabel(text)
    # Render the asterisk icon prepended to label text via QSS background-image,
    # or via a parent QHBoxLayout(icon, label). Picking inline-icon approach:
    icon = lucide("asterisk", size=10, color_token="color.danger.text")
    # Build composite widget; return a QLabel-like API or a QWidget container.
    ...
    return label
```

The exact mechanism — inline-icon-via-pixmap-in-label, or composite QWidget with QHBoxLayout(QLabel(icon), QLabel(text)) — is slice C's prompt-runner choice. The composite approach is more flexible but the helper signature `required_label(text) -> QLabel` is preferred to keep `QFormLayout.addRow(required_label("Name"), field)` calls clean. If returning a composite QWidget is necessary, the helper signature becomes `required_label(text) -> QWidget` and `QFormLayout.addRow(widget, field)` still works.

### 3.1 Acceptance verification (Step 3)

`from crmbuilder_v2.ui.base.list_detail_panel import required_label` (or wherever it lives) succeeds. `required_label("Name")` returns a widget that renders with the asterisk icon visible before "Name".

## Step 4 — Label-above form layout EVERYWHERE

Apply `setRowWrapPolicy(QFormLayout.WrapAllRows)` to every `QFormLayout` instance. Concrete call sites:

### 4.1 Dialog bases

- `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — the `QFormLayout` constructed inside `EntityCrudDialog._build_form()` (or equivalent method). Same QFormLayout serves `EntityCrudDeleteDialog` via shared init or not — verify and apply.
- `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py` — the `QFormLayout` for the replace dialog body.

### 4.2 Panel detail panes

For each panel from Step 1's audit, locate the panel's detail-pane construction code (likely `_build_detail_widget` or `render_detail`), find the `QFormLayout` instance, and add the `setRowWrapPolicy` call.

### 4.3 Required field adoption

For each required field identified in Step 1's audit, replace the panel's existing label construction with `required_label(text)`. E.g., `form.addRow(QLabel("Name"), name_field)` becomes `form.addRow(required_label("Name"), name_field)`.

### 4.4 Per-dialog forms

Any dialog file outside the bases (`crud_dialog.py`, `versioned_replace_dialog.py`) that constructs its own `QFormLayout` directly — verify via the Step 1 audit and apply the same `WrapAllRows` policy. Expected: none, but verify.

### 4.5 Acceptance verification (Step 4)

- Opening any panel shows labels above their fields, not to the left of them.
- Opening any record-editing dialog shows labels above their fields.
- Required fields show the asterisk icon before their label text.

## Step 5 — Status combo "Valid transitions" caption

For each panel with a status field (per Step 1's audit — Domains, Entities, CRM Candidates expected, plus any others discovered):

### 5.1 Caption widget

Below the panel's status combo, add a sibling `QLabel`. The label's text reads `"Valid transitions: <enum-1>, <enum-2>"` computed from the propose-verify successor set for the current record.

Layout pattern within the panel's detail-pane builder:

```python
status_container = QWidget()
status_layout = QVBoxLayout(status_container)
status_layout.setContentsMargins(0, 0, 0, 0)
status_layout.setSpacing(int(t("space.1").rstrip("px")))  # 4px between combo and caption
status_layout.addWidget(self.status_combo)
self.status_hint_label = QLabel("")
self.status_hint_label.setObjectName("statusHintCaption")
status_layout.addWidget(self.status_hint_label)
form.addRow(required_label("Status"), status_container)
```

QSS rule added to `build_app_stylesheet()`:

```
QLabel#statusHintCaption {
    font-size: <font.size.caption>;
    color: <color.neutral.500>;
}
```

### 5.2 Caption text update

In the panel's `render_detail` (or wherever the status combo is populated for a record), compute the valid successors via the existing propose-verify mechanism and set `self.status_hint_label.setText(f"Valid transitions: {', '.join(successors)}")`. If no transitions valid (terminal state), set text to empty string (the label remains in the layout for size stability).

### 5.3 Acceptance verification (Step 5)

Opening the Domains panel and selecting any record shows the status combo with the hint caption below: e.g., "Valid transitions: ready, archived". Same for Entities and CRM Candidates.

## Step 6 — Notes collapsible toggle

For each panel with a notes field (likely all panels — verify in Step 1 audit), replace the existing flat `QToolButton` toggle with the design pass §2.4 treatment:

- Toggle row: Lucide `chevron-right` (collapsed) / `chevron-down` (expanded) at 14px in `t("color.neutral.700")`, followed by `space.2` (8px) horizontal space, then "Notes" label in `t("font.size.small")` `t("font.weight.medium")` `t("color.neutral.700")`.
- Implementation: replace the existing `QToolButton` `setStyleSheet("border: none;")` block with a small custom widget that handles the click event, swaps the icon on expand/collapse, and toggles the notes field's visibility.
- The notes field appears below the toggle when expanded with `space.2` (8px) of vertical separation.

A shared helper widget makes sense if multiple panels share this pattern (likely they do — every detail pane has notes). Suggest: `class CollapsibleSection(QWidget)` in `ui/widgets/collapsible_section.py`. Slice C's prompt-runner decides whether the per-panel friction warrants the shared helper.

### 6.1 Acceptance verification (Step 6)

Opening any panel with a notes field shows the new chevron + "Notes" toggle. Clicking it expands/collapses the notes field.

## Step 7 — ReferencesSection internal rewrite

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/references_section.py`. Refactor in place — preserve the public API (constructor signature, `navigate_requested` signal, `references_changed` signal, `Add reference` button, right-click context menu).

### 7.1 Kind→label mapping

Add a module-level constant:

```python
_KIND_LABELS: dict[tuple[str, str], str] = {
    ("inbound", "session_decides_decision"): "Decided in",
    ("outbound", "decision_is_about_planning_item"): "Is about",
    ("outbound", "decision_supersedes_decision"): "Supersedes",
    ("inbound", "decision_supersedes_decision"): "Superseded by",
    ("outbound", "process_hands_off_to_process"): "Hands off to",
    ("inbound", "process_hands_off_to_process"): "Receives from",
    # ... etc — verify all kinds from v0.5's RELATIONSHIP_RULES are mapped
}

_DEFAULT_LABEL = "References"  # fallback for kinds not explicitly mapped
```

The exact entries are derived from v0.5's `RELATIONSHIP_RULES` (per the docstring in `dialogs/reference_create.py`). Slice C's prompt-runner verifies coverage; any unmapped kind falls through to `_DEFAULT_LABEL`.

### 7.2 Rewrite the rendering method

The current `_populate()` (or equivalent) groups by (direction → type). Rewrite to:

1. Flatten the inbound and outbound payloads into a list of (direction, type, target) tuples.
2. Filter out kinds in `exclude_relationships` (preserving v0.5 behavior).
3. Group by (direction, type) tuple; produce `_KIND_LABELS[(direction, type)]` as the sub-section header.
4. Render each sub-section: header `QLabel` with `setProperty("role", "references-kind-header")` (picks up the QSS rule from Step 2.3); entry rows below.
5. Each entry: identifier in `font.family.mono` at `font.size.small` `color.neutral.700`, followed by `space.3` (12px), then title in `font.size.body` `color.neutral.800`.
6. Entry hover tint via QSS rule on `QLabel[role="references-entry"]:hover` or via per-row event filter.
7. Right-click context menu unchanged from v0.5: `Delete reference`, `Go to {target identifier}`.
8. Sub-sections separated by `space.4` (16px) vertical space.
9. `Add reference` button below the last sub-section; same v0.3-shipped behavior. Style as Text/Link button (transparent background, Lucide `plus` icon, `color.accent.default` text, `font.weight.medium`). Note: full Text/Link button category styling lands in slice D; for slice C, set the basic appearance via per-widget `setStyleSheet` and let slice D's QSS rules supersede if necessary.
10. Empty state ("No references" line + Add reference button) preserved from v0.5.

The two top-level direction-grouped sections from v0.5 are REMOVED. The `inbound_label` and `outbound_label` constructor args (per v0.4 Processes-panel use case overriding to "Receives from" / "Hands off to") become vestigial in the new model — they no longer affect rendering. Keep them in the constructor signature for back-compat but ignore at render time; add a deprecation comment.

### 7.3 Acceptance verification (Step 7)

- Opening the Decisions panel and selecting DEC-076 renders the ReferencesSection with sub-sections grouped by kind, e.g.:
  ```
  Decided in
    SES-025  v0.5-orientation conversation close-out
  Is about
    PI-001   Full styling design pass per DEC-024
  ```
- Identifiers render in mono font; titles in body font.
- Hovering an entry tints its background.
- Right-clicking an entry opens the context menu with delete + go-to actions.
- Clicking Add reference still opens the reference-create dialog.
- Empty state on a record with no references renders the "No references" line + Add reference button.

## Step 8 — Visual regression smoke

Run the application and verify across every panel:

- Detail pane shows label-above form layout — labels on a row above their fields.
- Required fields show the asterisk icon before label text.
- Status combo (where present) shows hint caption below.
- Notes collapsible toggle renders with chevron + "Notes" treatment.
- ReferencesSection renders sub-sectioned plain-list grouping.
- v0.5 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`.

## Commit message template

```
v2: ui v0.6 slice C — panel retrofits + ReferencesSection

Delivers panel-level visual coherence across all panels.

build_app_stylesheet additions (ui/styling.py):
- QFormLayout QLabel rule applying design pass §2.4 label treatment
- Editable field state coverage (default/focused/error/disabled/
  read-only) — error state via dynamic fieldState property
- QLabel role hooks for references-kind-header and
  statusHintCaption

Form layout (label-above EVERYWHERE):
- QFormLayout.WrapAllRows applied to all QFormLayout instances:
  every panel detail pane + crud_dialog base + versioned_replace_-
  dialog base
- required_label(text) helper in base/list_detail_panel.py
  renders Lucide asterisk icon before label text; panel detail
  builders adopt for required fields

Status combo hint caption:
- Per-panel QLabel below status combo (Domains, Entities, CRM
  Candidates)
- Caption updated from propose-verify successor set in render_-
  detail

Notes collapsible toggle:
- Replaces flat QToolButton with chevron + Notes treatment per
  design pass §2.4
- Shared helper widget if pattern repeats (slice C decides)

ReferencesSection rewrite (ui/widgets/references_section.py):
- Refactor in place; public API preserved (constructor sig,
  signals, add-reference + context menu)
- _KIND_LABELS module constant maps (direction, type) tuples to
  title-case kind labels per design pass §2.4
- Sub-sectioned plain-list rendering replaces v0.5's inbound/
  outbound direction grouping
- inbound_label / outbound_label constructor args kept for back-
  compat but vestigial in new model (deprecation comment added)

Affected panels: all 12 existing panels (8 governance: Sessions,
Decisions, Risks, Planning Items, Topics, References, Charter,
Status; 4 methodology: Domains, Entities, Processes, CRM
Candidates) plus v0.5's engagement panel (engagements.py per
verification).

Next: slice D (dialogs + form controls).

No schema changes; no API changes; v0.5 test suite remains green.
```

After committing, run:

- `git push origin main`
- Notify Doug that slice C is complete and ready for screenshot capture per implementation plan §7. Screenshots: one per affected panel (`slice-C/sessions-panel.png` through `slice-C/engagements-panel.png`) plus `references-section-multi-kind.png` showing a record with at least three relationship kinds.

## Out of slice

- Dialog chrome retoken (slice D): background, padding, drop shadow + backdrop already in slice A; internal context strip in slice D.
- Button categories beyond default Secondary (slice D): Primary, Destructive, Text/Link, Icon-only with full state coverage.
- Combo dropdown popup styling (slice D): tokenized item rendering, hover/selected items.
- Checkbox styling with Lucide `check` icon (slice D).
- Inline form-field error MESSAGE rendering below fields (slice D — the field red border is in slice C; the message text below is in slice D).
- Inline panel-level warning callouts (slice E): the Processes panel soft-deleted-domain warning gets warning-amber treatment in slice E.
- Error dialog header retoken (slice E).
- Crash banner re-skin (slice E).
- `__version__` (slice F).
- README v0.6 release note (slice F).
- WCAG contrast test module (slice F).

---

*End of slice C prompt.*
