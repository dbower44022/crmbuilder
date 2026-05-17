# CLAUDE-CODE-PROMPT-v2-ui-v0.6-D-dialogs-and-form-controls

**Last Updated:** 05-16-26 18:35
**Series:** v2-ui-v0.6
**Slice:** D (4 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.6-C (panel retrofits + ReferencesSection)

## Purpose

Slice **D — Dialogs + form controls** completes the dialog and form story for v0.6. After slice C, dialog forms render with label-above layout and editable fields have state coverage on borders. Slice D adds the rest: internal context strip on record-editing dialogs, five button categories with full state coverage, form controls beyond the basic text input (combo dropdown popup, checkbox custom indicator), and delete-confirm dialog body treatment.

Six deliverables:

1. **Five button categories with full state coverage.** Primary, Secondary, Destructive, Text/Link, Icon-only — each rendered per design pass §2.5 with default/hover/pressed/focused/disabled state coverage via QSS rules in `build_app_stylesheet()`. The Secondary category is already the default from slice A; this slice adds rules for the other four categories. Plus four helper functions in `base/list_detail_panel.py` (`primary_button`, `destructive_button`, `text_link_button`, `icon_button`) that return QPushButton instances with the appropriate `buttonCategory` dynamic property set.

2. **Button-category migration across the codebase.** Every existing `QPushButton` construction site that should NOT be Secondary gets migrated to use the appropriate helper. Save → `primary_button`; Delete → `destructive_button`; "Add reference" and similar inline affordances → `text_link_button`; panel toolbar refresh / show-deleted toggles → `icon_button`. The legacy `#c1272d` red destructive treatment in `dialogs/reference_delete.py` and `base/crud_dialog.py` is removed alongside the `#b6868a` disabled-destructive treatment.

3. **Internal context strip on record-editing dialogs.** New method `_build_context_strip()` on `EntityCrudDialog` base, called in `__init__` only when the dialog is in edit mode. Renders identifier in mono font plus record name above the form area per design pass §2.7. Excluded by design pass: create-mode dialogs, About dialog, delete-confirm dialogs, error dialog, reference-delete dialog.

4. **Combo dropdown popup styling.** QSS rules added to `build_app_stylesheet()` per design pass §2.6: tokenized popup container background and border; per-item height, padding, hover-state tint; selected-item background. Plus a right-side Lucide `chevron-down` icon at 14px in `color.neutral.500` on the combo itself.

5. **Checkbox custom indicator.** QSS rule using `QCheckBox::indicator` with `background-image: url(...)` referencing the bundled Lucide `check.svg` plus `color.accent.default` background-color for checked state per design pass §2.6.

6. **Delete-confirm dialog body treatment.** Existing per-entity delete dialogs (`decision_delete.py`, `planning_item_delete.py`, etc.) and the standalone `dialogs/reference_delete.py` get the design pass §2.7 delete-specific treatment: single paragraph body in `font.line.relaxed` (1.6) line height, destructive button right-aligned with Cancel to its left.

This slice does NOT add: status / error / warning panel-level surfaces (slice E); crash banner re-skin (slice E); `__version__` bump (slice F); WCAG contrast test module (slice F).

## Project context

Slices A, B, and C delivered: foundation (tokens, fonts, icons, modal elevation), shared selected-state vocabulary (sidebar + master-pane delegate), panel chrome and detail-pane retrofit (label-above forms, status caption, notes toggle, ReferencesSection sub-sectioned rendering). After slice C, the panels are visually coherent end-to-end. Slice D closes the dialog story.

The button category work is the largest scope item in slice D — touching every dialog file and every panel toolbar across the codebase. The migration is mechanical (helpers exist; call sites updated to use them) but voluminous. Slice D's prompt-runner verifies coverage via Step 7's smoke test.

The context strip is a smaller but trickier change because it intersects with `EntityCrudDialog`'s existing structure. Slice D's prompt-runner verifies the strip renders correctly on edit-mode dialogs without breaking create-mode or delete-confirm patterns.

## Pre-flight

1. Working directory: crmbuilder repo clone.
2. `git status` clean. Pull latest: `git pull --rebase origin main`. Slices A, B, C must be on `main`.
3. Verify prior slices:
   - `ui/styling.py` has button-category default rules in `build_app_stylesheet()` (from slice A).
   - `ui/widgets/master_pane_delegate.py` exists (from slice B).
   - `ui/widgets/references_section.py` rewritten with sub-sectioned plain-list rendering (from slice C).
   - `ui/base/list_detail_panel.py` has `required_label` helper (from slice C).
   - App launches; panels render with label-above forms.
4. Storage operational; v0.5 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (focus: §2 items 11–12; §4.7; §6 ACs D1–D6).
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (focus: §4 Slice D).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (focus: §2.5 Buttons, §2.6 Form controls, §2.7 Dialogs).
5. v2 source files:
   - `ui/styling.py` — `build_app_stylesheet()` gets new rules.
   - `ui/base/list_detail_panel.py` — button helpers join `required_label`.
   - `ui/base/crud_dialog.py` — context strip method added; both `EntityCrudDialog` and `EntityCrudDeleteDialog` use Secondary/Primary/Destructive buttons via helpers.
   - `ui/base/versioned_replace_dialog.py` — uses helpers for Apply/Cancel.
   - `ui/dialogs/*.py` — per-dialog button construction sites migrated to helpers.
   - All `ui/panels/*.py` — panel toolbar buttons (refresh, show-deleted toggle) migrated to `icon_button`.

## Step 1 — Button helper definitions

Add four helper functions in `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` (alongside `required_label` from slice C; or move both helpers to a sibling `ui/widgets/form_helpers.py` if cleanliness warrants — slice D's prompt-runner picks).

```python
from PySide6.QtWidgets import QPushButton
from crmbuilder_v2.ui.icons import lucide

def primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("buttonCategory", "primary")
    return btn

def destructive_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("buttonCategory", "destructive")
    return btn

def text_link_button(text: str, *, icon_name: str | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("buttonCategory", "text")
    if icon_name:
        btn.setIcon(lucide(icon_name, size=14, color_token="color.accent.default"))
    return btn

def icon_button(icon_name: str, *, tooltip: str) -> QPushButton:
    btn = QPushButton()
    btn.setProperty("buttonCategory", "icon-only")
    btn.setIcon(lucide(icon_name, size=14, color_token="color.neutral.700"))
    btn.setToolTip(tooltip)
    btn.setFixedSize(28, 28)
    return btn
```

The `buttonCategory` dynamic property drives the QSS rules added in Step 2.

### 1.1 Acceptance verification (Step 1)

`from crmbuilder_v2.ui.base.list_detail_panel import primary_button, destructive_button, text_link_button, icon_button` (or new location) succeeds.

## Step 2 — `build_app_stylesheet()` button category rules

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py`'s `build_app_stylesheet(tokens)` to add per-category state coverage rules. Secondary already covered by slice A's default `QPushButton` rule; this step adds the other four categories.

### 2.1 Primary

```
QPushButton[buttonCategory="primary"] {
    background: <color.accent.default>;
    color: <color.neutral.0>;
    border: 0;
    padding: <space.1> <space.3>;
    border-radius: <radius.subtle>;
    font-weight: <font.weight.medium>;
    min-width: 88px;
}
QPushButton[buttonCategory="primary"]:hover {
    background: <color.accent.hover>;
}
QPushButton[buttonCategory="primary"]:pressed {
    background: <color.accent.pressed>;
}
QPushButton[buttonCategory="primary"]:disabled {
    background: <color.neutral.300>;
    color: <color.neutral.500>;
}
```

### 2.2 Destructive

Same structure as Primary but with `color.danger.default` background (and a slightly darker hover/pressed — slice D's prompt-runner picks specific values; recommended +6%/+12% lightness reduction).

### 2.3 Text/Link

```
QPushButton[buttonCategory="text"] {
    background: transparent;
    border: 0;
    color: <color.accent.default>;
    font-weight: <font.weight.medium>;
    padding: <space.1> <space.2>;
}
QPushButton[buttonCategory="text"]:hover {
    text-decoration: underline;
}
QPushButton[buttonCategory="text"]:pressed {
    color: <color.accent.pressed>;
}
QPushButton[buttonCategory="text"]:disabled {
    color: <color.neutral.300>;
}
```

### 2.4 Icon-only

```
QPushButton[buttonCategory="icon-only"] {
    background: transparent;
    border: 0;
    padding: 0;
}
QPushButton[buttonCategory="icon-only"]:hover {
    background: <color.neutral.100>;
}
QPushButton[buttonCategory="icon-only"]:pressed {
    background: <color.neutral.200>;
}
QPushButton[buttonCategory="icon-only"]:disabled {
    /* icon tint handled at construction; QSS opacity acceptable */
}
```

### 2.5 Acceptance verification (Step 2)

Manually constructed `primary_button("Save")`, `destructive_button("Delete")`, `text_link_button("Add", icon_name="plus")`, `icon_button("rotate-ccw", tooltip="Refresh")` instances render with the appropriate category styling end-to-end across all five states (visible by hover, click, tab-focus, disable).

## Step 3 — Combo dropdown popup + checkbox custom indicator

### 3.1 Combo

Add to `build_app_stylesheet()`:

```
QComboBox {
    /* existing default chrome from slice A retained */
    padding-right: 24px;  /* room for the chevron icon */
}
QComboBox::drop-down {
    border: 0;
    width: 20px;
}
QComboBox::down-arrow {
    image: url(<asset path to chevron-down.svg, pre-tinted color.neutral.500>);
    width: 14px;
    height: 14px;
}
QComboBox QAbstractItemView {
    background: <color.neutral.0>;
    border: 1px solid <color.neutral.300>;
    border-radius: <radius.subtle>;
    /* drop shadow harder to apply via QSS on popup view; deferred */
    padding: <space.1>;
}
QComboBox QAbstractItemView::item {
    height: 28px;
    padding: <space.2> <space.3>;
    font-size: <font.size.body>;
    color: <color.neutral.800>;
}
QComboBox QAbstractItemView::item:hover {
    background: <color.neutral.100>;
}
QComboBox QAbstractItemView::item:selected {
    background: <color.accent.subtle>;
    color: <color.neutral.900>;
}
```

The `QComboBox::down-arrow` `image: url(...)` references the bundled chevron-down.svg. Color tinting is done at the SVG file level (a pre-tinted version committed to assets), OR via Qt's `QComboBox` custom paint hooks. Per slice D's prompt-runner judgment: use the simpler approach of committing a pre-tinted SVG variant (e.g., `chevron-down-neutral-500.svg`) — but only if needed; if the default `currentColor` Lucide SVG renders cleanly via Qt's QSS image loader, no pre-tinting is necessary. Verify visually.

### 3.2 Checkbox

```
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid <color.neutral.300>;
    border-radius: <radius.subtle>;
    background: <color.neutral.0>;
}
QCheckBox::indicator:hover {
    border: 1px solid <color.neutral.500>;
}
QCheckBox::indicator:checked {
    background: <color.accent.default>;
    border: 1px solid <color.accent.default>;
    image: url(<asset path to check.svg, pre-tinted color.neutral.0>);
}
QCheckBox::indicator:checked:hover {
    background: <color.accent.hover>;
}
QCheckBox::indicator:disabled {
    background: <color.neutral.100>;
    border: 1px solid <color.neutral.200>;
}
QCheckBox::indicator:checked:disabled {
    image: url(<asset path to check.svg, pre-tinted color.neutral.300>);
}
```

The check icon needs a pre-tinted white variant committed to `ui/assets/icons/lucide/check-white.svg` (or similar) for the checked-state. Slice D's prompt-runner verifies a tinted variant is committed or that the runtime tinting approach in `ui/icons.py` works via QSS image URL (it does not — QSS `url()` reads files, not Python loader output). So pre-tinted SVG file is the approach.

### 3.3 Acceptance verification (Step 3)

- Opening any panel detail pane with a combo box (Domains, Entities, etc. for status; any panel with vocab fields) shows the new chevron-down icon and the tokenized popup styling when the combo is expanded.
- Any checkbox in the app (likely few — verify by inspection) renders the new 16×16 box with hover/checked/disabled states.

## Step 4 — Internal context strip on record-editing dialogs

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` to add the context strip in `EntityCrudDialog`'s edit mode.

### 4.1 Edit-mode detection

The existing `EntityCrudDialog.__init__` already distinguishes create vs edit (likely via a `record` constructor argument that's None in create mode and a record dict in edit mode). Verify the detection mechanism and add a single `if self._is_edit_mode():` (or equivalent boolean check) guarding the context-strip insertion.

### 4.2 Context strip method

```python
def _build_context_strip(self, identifier: str, record_name: str) -> QWidget:
    """Build the internal context strip for an edit-mode dialog."""
    strip = QWidget()
    strip.setObjectName("dialogContextStrip")
    layout = QHBoxLayout(strip)
    layout.setContentsMargins(*[int(t("space.3").rstrip("px"))] * 4)

    id_label = QLabel(identifier)
    id_label.setObjectName("dialogContextStripIdentifier")
    layout.addWidget(id_label)

    layout.addSpacing(int(t("space.3").rstrip("px")))

    name_label = QLabel(record_name)
    name_label.setObjectName("dialogContextStripName")
    name_label.setWordWrap(False)
    name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    # Truncate with ellipsis on overflow
    layout.addWidget(name_label, stretch=1)

    return strip
```

QSS rules added to `build_app_stylesheet()`:

```
QWidget#dialogContextStrip {
    background: <color.neutral.100>;
    border-bottom: 1px solid <color.neutral.200>;
}
QLabel#dialogContextStripIdentifier {
    font-family: <font.family.mono>;
    font-size: <font.size.small>;
    color: <color.neutral.700>;
    font-weight: <font.weight.medium>;
}
QLabel#dialogContextStripName {
    font-size: <font.size.body>;
    color: <color.neutral.800>;
}
```

The strip is inserted at the top of the dialog body in `__init__`, before the form. The existing `EntityCrudDialog` layout already has a known root layout; slice D's prompt-runner adds the strip insertion at the appropriate point.

### 4.3 Excluded dialogs

Per design pass §2.7, the context strip is excluded from:
- `EntityCrudDialog` in create mode (the conditional check from Step 4.1 handles this).
- `EntityCrudDeleteDialog` (delete-confirm — explicit exclusion in `_build_context_strip` caller).
- `AboutDialog` (does not inherit from `EntityCrudDialog`).
- `ErrorDialog` (does not inherit).
- `ReferenceCreateDialog` (inherits from `EntityCrudDialog` but is a create-mode dialog — the edit-mode check from Step 4.1 handles this).
- `ReferenceDeleteDialog` (does not inherit).
- `CharterReplaceDialog` and `StatusReplaceDialog` (inherit from `VersionedReplaceDialog`, not `EntityCrudDialog`).

Slice D's prompt-runner verifies that `EntityCrudDeleteDialog`'s confirmation flow doesn't accidentally pick up the strip via inheritance.

### 4.4 Acceptance verification (Step 4)

- Opening an edit dialog for any record (e.g., Decisions panel → edit DEC-076) shows the identifier + record name strip at the top of the dialog body.
- Opening a create dialog (e.g., Decisions panel → New decision) does NOT show the strip.
- Opening a delete-confirm dialog does NOT show the strip.
- About dialog, error dialog, reference-delete dialog, reference-create dialog all do NOT show the strip.

## Step 5 — Button-category migration across the codebase

Apply the button helpers across every existing button construction site.

### 5.1 Dialog Save / Cancel / Delete buttons

For every `EntityCrudDialog` subclass (and the base itself), the Save button uses `primary_button("Save")`. Cancel stays as a bare `QPushButton("Cancel")` (Secondary by default). Delete in `EntityCrudDeleteDialog` uses `destructive_button("Delete")`.

The Save/Cancel/Delete button construction lives in the base classes; the migration is typically a single per-base edit reaching every subclass via inheritance. Verify.

### 5.2 Replace dialog Apply / Cancel

`VersionedReplaceDialog`: Apply → `primary_button("Apply")`. Cancel stays Secondary.

### 5.3 Reference dialog buttons

- `ReferenceCreateDialog`: Save → `primary_button("Save")` (inherits via base; verify).
- `ReferenceDeleteDialog`: Delete → `destructive_button("Delete")`.

### 5.4 About dialog Close button

Close stays as bare `QPushButton("Close")` (Secondary by default). Per design pass §2.8 — "Single secondary button (per §2.5) at the bottom-right of the dialog body."

### 5.5 Error dialog Close button

Same as About: Close stays Secondary.

### 5.6 ReferencesSection "Add reference" button

Migrate to `text_link_button("Add reference", icon_name="plus")`. The widget is in `ui/widgets/references_section.py`; slice C added the basic appearance via per-widget `setStyleSheet` (per the slice C prompt's Step 7.2 note). Slice D replaces that with the helper.

### 5.7 Panel toolbar buttons

For every panel with a toolbar (likely all panels via `ListDetailPanel`'s standard toolbar widget):
- Refresh button → `icon_button("rotate-ccw", tooltip="Refresh")`.
- Show-deleted toggle → `icon_button("trash-2", tooltip="Show deleted records")` (the tooltip text reflects toggle state — slice D's prompt-runner picks the exact toggle semantics).
- Any other toolbar action button → `icon_button` with appropriate icon.

The toolbar construction code is typically in `ListDetailPanel` (or a sub-widget); single-edit propagation expected.

### 5.8 Legacy color cleanup

Remove the legacy `#c1272d` red and `#b6868a` disabled-destructive treatment from `dialogs/reference_delete.py` and `base/crud_dialog.py`. The Destructive category styling from Step 2.2 replaces both.

### 5.9 Acceptance verification (Step 5)

Open every dialog type and verify button styling:
- Edit dialog: Save renders Primary (accent blue, white text), Cancel Secondary (transparent with gray border), Delete Destructive (red).
- Create dialog: Save Primary, Cancel Secondary.
- Delete-confirm: Delete Destructive, Cancel Secondary.
- About: Close Secondary.
- Error: Close Secondary.
- Reference dialogs: similar coverage.
- Every panel: toolbar buttons render as icon-only with hover tinting.

## Step 6 — Delete-confirm dialog body treatment

Modify `EntityCrudDeleteDialog` base (and `ReferenceDeleteDialog` standalone) per design pass §2.7's delete-specific treatment.

### 6.1 Body content

The body content is a single paragraph explaining the deletion and irreversibility. Currently exists in v0.5; slice D updates the styling:
- Font: `font.size.body` (14px), `color.neutral.800`.
- Line height: `font.line.relaxed` (1.6).
- Set via QSS on a class-named label, or per-instance via the existing body label.

### 6.2 Action button row

- Destructive button right-aligned.
- Cancel to its left (with `space.2` between).
- The action row's `QHBoxLayout` uses `addStretch()` before Cancel, then Cancel, then `space.2` spacer, then Delete.

### 6.3 No context strip

Confirmed in Step 4.3 — delete-confirm dialogs do not include the strip.

### 6.4 Acceptance verification (Step 6)

Opening a delete-confirm dialog (any record's delete from the master view) renders: single paragraph body in relaxed line height; Destructive Delete button right-aligned; Cancel button to its left.

## Step 7 — Visual regression smoke + v0.5 test suite

Run the application and verify:
- Every dialog type opens with appropriate chrome, context strip (where applicable), and button category styling.
- Every panel toolbar shows icon-only buttons.
- Combo dropdowns render with chevron icon and tokenized popups.
- Checkboxes (if any visible) render with the 16×16 design system treatment.
- Inline error labels render in danger-text color (verify by triggering a validation error on any form).

Run `uv run pytest tests/crmbuilder_v2/ -v`. Update any test assertions that look for legacy button text/color/styling. If any v0.5 test exercises specific button visual state (e.g., asserts a Save button is "primary" via some property check), the assertion may need an update.

## Commit message template

```
v2: ui v0.6 slice D — dialogs + form controls

Delivers the dialog and form control story for v0.6.

Button categories (build_app_stylesheet additions):
- Five categories with full state coverage: Primary (accent
  fill, white text), Secondary (transparent + neutral border —
  default), Destructive (danger fill), Text/Link (transparent +
  accent text), Icon-only (28x28 square, icon-only)
- buttonCategory dynamic property drives QSS rules
- Default fall-through: bare QPushButton renders Secondary

Button helpers (base/list_detail_panel.py):
- primary_button(text)
- destructive_button(text)
- text_link_button(text, *, icon_name=None)
- icon_button(icon_name, *, tooltip)

Button migration across codebase:
- Dialog Save → primary_button (via CRUD base)
- Dialog Delete → destructive_button (via base)
- ReferencesSection Add reference → text_link_button(plus)
- Panel toolbar refresh + show-deleted → icon_button
- Legacy #c1272d red + #b6868a disabled-destructive treatment
  removed from reference_delete.py and crud_dialog.py

Combo dropdown + checkbox styling (build_app_stylesheet):
- QComboBox::down-arrow with Lucide chevron-down
- QComboBox QAbstractItemView popup styling
- QCheckBox::indicator with Lucide check.svg for checked
  state; pre-tinted SVG variants committed to assets

Internal context strip (base/crud_dialog.py):
- _build_context_strip(identifier, record_name) on
  EntityCrudDialog; auto-applied in edit mode only
- color.neutral.100 background, mono identifier + body name
- Excluded from create-mode, delete-confirm, About, Error,
  ReferenceDelete (verified per design pass §2.7)

Delete-confirm dialog body treatment:
- font.line.relaxed (1.6) line height; Destructive button
  right-aligned with Cancel to its left

Next: slice E (status, error, warning surfaces + crash banner).

No schema changes; no API changes; v0.5 test suite remains green.
```

After committing:

- `git push origin main`
- Notify Doug for screenshot capture per implementation plan §7. Slice D screenshots: `edit-dialog-with-context-strip.png`, `delete-confirm-dialog.png`, `button-states-primary.png` (showing default/hover/pressed/focused/disabled), `button-states-secondary.png`, `button-states-destructive.png`, `form-controls.png` (showing one of each control type).

## Out of slice

- Inline panel-level warning callouts (slice E): the Processes panel soft-deleted-domain warning.
- Error dialog header retoken with Lucide circle-x icon (slice E).
- Crash banner re-skin (slice E).
- `__version__` bump and README v0.6 release note (slice F).
- WCAG contrast test module (slice F).
- Status entity versioned-replace to "v0.6 complete" (operator-authored after slice F).

---

*End of slice D prompt.*
