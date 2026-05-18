# CLAUDE-CODE-PROMPT-v2-ui-v0.6-E-status-and-crash-banner

**Last Updated:** 05-16-26 18:50
**Series:** v2-ui-v0.6
**Slice:** E (5 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.6-D (dialogs + form controls)

## Purpose

Slice **E — Status, error, warning + crash banner** delivers the small but visible surfaces that complete v0.6's visual coherence. After slice D, dialogs and form controls render per the design system. Slice E adds: inline panel-level warning callouts (where v0.5 currently uses ad-hoc red `#B22222` styling), error-dialog header retoken (retiring the legacy `#1F3864` banner style), and the crash-banner re-skin into the design system (retiring the bespoke `_BANNER_BACKGROUND` chrome).

Five deliverables:

1. **`WarningCallout` widget.** New `ui/widgets/warning_callout.py` providing a small reusable widget per design pass §2.9: Lucide `circle-alert` icon + warning text in a single horizontal row, using `color.warning.default` token. The Processes panel's soft-deleted-domain message is the canonical current caller.

2. **Processes panel warning retoken.** Existing `_WARNING_STYLE = "color: #B22222;"` constant in `crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py` retired. The soft-deleted-domain warning rendered via `WarningCallout`. The message text remains informational ("the affiliated domain has been soft-deleted; re-affiliate or restore") — warning-amber color, not danger-red.

3. **Inline form-field error verification.** The QSS rule for `QLabel[role="error"]` already in `build_app_stylesheet()` (from slice A) covers inline error labels. Slice E verifies coverage across multiple panels by triggering validation errors and confirming the labels render in `color.danger.text` per design pass §2.9.

4. **Error dialog header retoken.** `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py` restructured to add a leading horizontal header row with Lucide `circle-x` icon at 18px in `color.danger.default` + title in `font.size.heading_3` (18px) `font.weight.semibold` `color.danger.text`. Legacy `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` constant removed.

5. **Crash banner re-skin.** `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py` folded into the design system per design pass §2.10. Background `color.danger.default`; text `color.neutral.0` (white) at `font.size.body` `font.weight.medium`; leading Lucide `circle-alert` icon; padding 12px×16px; banner buttons re-styled with semi-transparent white-on-color treatment via per-widget `setStyleSheet` (not via the design system QSS — the banner is exceptional). Legacy `_BANNER_BACKGROUND` constant and bespoke button-style constants removed.

This slice does NOT add: `__version__` bump (slice F); README v0.6 release note (slice F); WCAG contrast test module (slice F); status-entity versioned-replace to "v0.6 complete" (operator-authored after slice F).

## Project context

Slices A–D have delivered every architectural piece of v0.6 except this slice and closeout. The pattern is established: tokens via `t()` accessor, QSS rules via `build_app_stylesheet()`, custom widgets in `ui/widgets/`, helpers in `base/list_detail_panel.py`. Slice E adds three small, visible surfaces using those patterns.

The crash banner is intentionally outside the design system in v0.5 — it has its own self-contained chrome (`_BANNER_BACKGROUND` plus bespoke button styling). Per DEC-094 commentary in the design pass, the v0.6 call is to fold it in: the danger token is unambiguously red and reads as "alarming," so the banner doesn't need its own visual language. Folding in means future style adjustments propagate automatically rather than requiring parallel maintenance. The semi-transparent white-on-color button styling (per design pass §2.10) is the one exceptional element — kept as per-widget `setStyleSheet` inside the banner module so the design system's QSS rules stay clean.

The error dialog's existing `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` is a v0.1 vestige that uses the legacy navy as a heading color, predating the danger-text token. Slice E retires it.

## Pre-flight

1. Working directory: crmbuilder repo clone.
2. `git status` clean. Pull latest: `git pull --rebase origin main`. Slices A–D must be on `main`.
3. Verify prior slices:
   - `ui/styling.py` has the `QLabel[role="error"]` rule (from slice A).
   - `ui/widgets/master_pane_delegate.py` (slice B), `ui/widgets/references_section.py` (slice C), button helpers (slice D), context strip (slice D).
   - App launches; all panels and dialogs render per slices A–D.
4. Storage operational; v0.5 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (focus: §2 items 13–14; §4.8; §6 ACs E1–E6).
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (focus: §4 Slice E).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (focus: §2.9 Status / error / warning surfaces, §2.10 Crash banner reconciliation).
5. v2 source files:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py` — `_WARNING_STYLE` constant being retired; soft-deleted-domain warning rendered via the new helper.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py` — `_BANNER_STYLE` retiring; header restructured.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py` — full re-skin.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/` — `warning_callout.py` added.

## Step 1 — `WarningCallout` widget

Create `crmbuilder-v2/src/crmbuilder_v2/ui/widgets/warning_callout.py`:

```python
"""WarningCallout — inline panel-level warning row.

Single-row callout with leading Lucide icon and warning text per
design pass §2.9. Used for informational warnings (not hard
errors) — e.g., the Processes panel's soft-deleted-domain
message.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t


class WarningCallout(QWidget):
    """Inline warning row: Lucide icon + amber-toned label."""

    def __init__(
        self,
        text: str = "",
        *,
        icon_name: str = "circle-alert",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        space_2 = int(t("space.2").rstrip("px"))
        layout.setSpacing(space_2)

        self._icon_label = QLabel()
        self._icon_label.setPixmap(
            lucide(icon_name, size=14, color_token="color.warning.default")
                .pixmap(14, 14)
        )
        layout.addWidget(self._icon_label)

        self._text_label = QLabel(text)
        self._text_label.setObjectName("warningCalloutText")
        layout.addWidget(self._text_label, stretch=1)

    def setText(self, text: str) -> None:
        self._text_label.setText(text)

    def text(self) -> str:
        return self._text_label.text()
```

And add the corresponding QSS rule to `build_app_stylesheet()` in `ui/styling.py`:

```
QLabel#warningCalloutText {
    font-size: <font.size.small>;
    color: <color.warning.default>;
}
```

The widget exposes `setText` / `text` so callers can update the warning text dynamically (matching v0.5's pattern for the Processes-panel soft-deleted-domain message).

### 1.1 Acceptance verification (Step 1)

- `from crmbuilder_v2.ui.widgets.warning_callout import WarningCallout` succeeds.
- Instantiating `WarningCallout("Test warning text")` and showing it renders the Lucide circle-alert icon at 14px in amber + the text in `color.warning.default`.

## Step 2 — Processes panel warning retoken

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/panels/processes.py`:

1. Remove the `_WARNING_STYLE = "color: #B22222;"` constant.
2. Locate the soft-deleted-domain warning code path. Currently likely a `QLabel` instantiated with the legacy red stylesheet applied. Replace with a `WarningCallout` instance.
3. Where the panel sets the warning text (when a record's affiliated domain has been soft-deleted), update to call `self._warning_callout.setText(...)`. Where the panel clears the warning (when no warning applies), call `self._warning_callout.setText("")` plus `self._warning_callout.hide()` (and `.show()` when text is non-empty).

Verify the warning text content unchanged: "the affiliated domain has been soft-deleted; re-affiliate or restore" (or whatever the v0.5 text is — preserve the wording, just retoken the rendering).

### 2.1 Acceptance verification (Step 2)

Open the Processes panel and select a record whose affiliated domain is soft-deleted (if such a record exists in the test data). The warning renders with the new amber treatment + Lucide circle-alert icon — not the legacy red `#B22222`. If no such record exists in test data, slice E's prompt-runner can synthesize one temporarily by soft-deleting a domain that has affiliated processes, verifying the warning, then restoring the domain.

## Step 3 — Inline form-field error verification

No new code in this step — just verification that slice A's `QLabel[role="error"]` QSS rule renders correctly.

### 3.1 Verification

- Open any edit dialog with a required field (e.g., Decisions edit dialog).
- Trigger a validation error by clearing the required field and pressing Save.
- Verify the inline error label below the field renders in `color.danger.text` (a deep red `#A8281C` per the design pass §1.2.4) at `font.size.caption` (12px).
- Verify the field's border also renders red (from slice C's editable field state coverage with `fieldState="error"` property).

If the inline error label does NOT render correctly, the QSS rule may need adjustment in `ui/styling.py`'s `build_app_stylesheet()` — slice E's prompt-runner fixes and notes the change.

## Step 4 — Error dialog header retoken

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py`:

### 4.1 Remove legacy banner constant

Remove the `_BANNER_STYLE = "color: #1F3864; font-weight: bold;"` constant.

### 4.2 Restructure header

The existing dialog body likely has a title at the top (perhaps a `QLabel` with the legacy banner style applied). Replace with a horizontal header row:

```python
header_row = QWidget()
header_layout = QHBoxLayout(header_row)
header_layout.setContentsMargins(0, 0, 0, 0)
space_3 = int(t("space.3").rstrip("px"))
header_layout.setSpacing(space_3)

# Leading circle-x icon
icon_label = QLabel()
icon_label.setPixmap(
    lucide("circle-x", size=18, color_token="color.danger.default")
        .pixmap(18, 18)
)
header_layout.addWidget(icon_label)

# Title
title_label = QLabel(self._title_text)  # whatever the existing title comes from
title_label.setObjectName("errorDialogHeader")
header_layout.addWidget(title_label, stretch=1)

# Insert at top of dialog body layout, before existing content
self._body_layout.insertWidget(0, header_row)
```

QSS rule in `build_app_stylesheet()`:

```
QLabel#errorDialogHeader {
    font-size: <font.size.heading_3>;
    font-weight: <font.weight.semibold>;
    color: <color.danger.text>;
}
```

Header is followed by `space.4` (16px) of vertical margin before the body content per design pass §2.9 — apply via `setSpacing` or an explicit spacer in the dialog's outer `QVBoxLayout`.

### 4.3 Body content unchanged

The error dialog's body content rendering (single error string or `{data, meta, errors}` envelope with structured errors) remains as it is in v0.5. Slice E only changes the header treatment.

### 4.4 Acceptance verification (Step 4)

Trigger an API error (e.g., temporarily stop the API server and attempt an operation that would invoke the error dialog). The error dialog opens with the new header: Lucide circle-x icon at 18px in `color.danger.default` followed by the error title in heading-3 size + semibold weight + `color.danger.text` color. The legacy navy banner styling is gone.

## Step 5 — Crash banner re-skin

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/crash_banner.py` per design pass §2.10.

### 5.1 Remove legacy constants

Remove:
- `_BANNER_BACKGROUND` constant.
- Any bespoke button-style constants (text color, button background color overrides, etc.).

### 5.2 Banner container styling

The banner widget itself gets styling via per-widget `setStyleSheet`:

```python
self.setStyleSheet(
    f"""
    CrashBanner {{
        background: {t("color.danger.default")};
    }}
    """
)
```

(Use the actual class name `CrashBanner` — verify in source.)

Plus `setAutoFillBackground(True)` if Qt's QSS background doesn't render reliably on the top-level banner widget. Slice E's prompt-runner verifies visually.

### 5.3 Banner content

The banner currently contains a message label and possibly action buttons. Restructure per design pass §2.10:

- Leading Lucide `circle-alert` icon at 16px in `color.neutral.0` (white).
- `space.2` (8px) horizontal space between icon and message.
- Message label in `color.neutral.0` (white) at `font.size.body` `font.weight.medium`.
- Layout padding: 12px (`space.3`) vertical × 16px (`space.4`) horizontal — set via `QHBoxLayout.setContentsMargins`.
- Existing dismiss/recovery affordance buttons (if any) rendered with semi-transparent white-on-color styling — see Step 5.4.

The banner remains always-on-top at the main window, full window width, persisting until dismissed or underlying error resolved (existing v0.5 behavior preserved).

### 5.4 Banner button styling

Per-widget `setStyleSheet` on each banner button (NOT via the design system QSS — the banner is exceptional):

```python
button.setStyleSheet(
    f"""
    QPushButton {{
        background: rgba(255, 255, 255, 38);  /* color.neutral.0 at 15% alpha */
        border: 1px solid rgba(255, 255, 255, 64);  /* color.neutral.0 at 25% alpha */
        color: {t("color.neutral.0")};
        padding: {t("space.1")} {t("space.3")};
        border-radius: {t("radius.subtle")};
    }}
    QPushButton:hover {{
        background: rgba(255, 255, 255, 76);  /* 30% alpha */
    }}
    QPushButton:pressed {{
        background: rgba(255, 255, 255, 115);  /* 45% alpha */
    }}
    """
)
```

Slice E's prompt-runner verifies the alpha values render correctly (Qt's QSS supports rgba()).

### 5.5 Acceptance verification (Step 5)

Trigger a crash condition (e.g., simulate by raising an unhandled exception in a path that surfaces to the banner). The banner renders:
- Background in `color.danger.default` (red).
- Leading Lucide circle-alert icon at 16px white.
- Message text in white body-medium.
- Padding 12px × 16px.
- Action buttons (if present) render with semi-transparent white-on-color treatment + hover/pressed states.

## Step 6 — Visual regression smoke + v0.5 test suite

Verify across the application:
- Trigger validation errors on multiple panels → inline error labels render in danger-text color, fields show red border.
- Open Processes panel with a soft-deleted-domain record → amber warning callout renders.
- Trigger an API error → error dialog opens with the new circle-x header.
- (If feasible) simulate a crash → banner re-skinned per design system.

Run `uv run pytest tests/crmbuilder_v2/ -v`. Update any test assertions that exercise:
- The legacy `_WARNING_STYLE` in processes.py.
- The legacy `_BANNER_STYLE` in error.py.
- The legacy `_BANNER_BACKGROUND` in crash_banner.py.
- Any color or text-property assertions on the three affected surfaces.

## Commit message template

```
v2: ui v0.6 slice E — status, error, warning + crash banner

Delivers the small but visible status / error / warning
surfaces that complete v0.6 visual coherence.

WarningCallout widget (ui/widgets/warning_callout.py):
- Inline panel-level warning row per design pass §2.9
- Lucide circle-alert icon + color.warning.default text in
  horizontal row
- Reusable; current single caller is the Processes panel's
  soft-deleted-domain warning

Processes panel retoken (ui/panels/processes.py):
- Legacy _WARNING_STYLE = 'color: #B22222;' constant removed
- Soft-deleted-domain warning rendered via WarningCallout —
  warning-amber, not danger-red (the message is informational,
  not a hard error per design pass §2.9)

Error dialog header retoken (ui/dialogs/error.py):
- Legacy _BANNER_STYLE = 'color: #1F3864; font-weight: bold;'
  constant removed (v0.1 vestige using the legacy navy)
- Header restructured: leading Lucide circle-x icon at 18px
  color.danger.default + title in font.size.heading_3
  semibold color.danger.text
- Body content unchanged

Crash banner re-skin (ui/crash_banner.py):
- Legacy _BANNER_BACKGROUND constant and bespoke button-style
  constants removed
- Background color.danger.default; text color.neutral.0 white
  at font.size.body font.weight.medium; leading Lucide circle-
  alert icon at 16px white
- Padding 12px × 16px (space.3 × space.4)
- Banner button styling kept as per-widget setStyleSheet (the
  banner is exceptional; semi-transparent white-on-color
  styling doesn't fit the five design-system button categories)
- Behavior unchanged: always-on-top, full window width,
  persists until dismissed or error resolved

Inline form-field error verification:
- QLabel[role='error'] QSS rule from slice A confirmed
  rendering correctly across multiple panels' validation flows

Next: slice F (closeout — version bump, README, WCAG contrast
test, regression pass).

No schema changes; no API changes; v0.5 test suite remains green.
```

After committing:
- `git push origin main`
- Notify Doug for screenshot capture. Slice E screenshots: `inline-field-error.png`, `inline-panel-warning.png` (the Processes soft-deleted-domain case), `error-dialog.png`, `crash-banner.png`.

## Out of slice

- `__version__` bump to "0.6.0" (slice F).
- README v0.6 release note (slice F).
- WCAG AA contrast test module (slice F).
- Full regression smoke across all v0.6 surfaces (slice F).
- Status entity versioned-replace to "v0.6 complete" (operator-authored after slice F).
- SES-030 session record application (operator-authored after slice F).

---

*End of slice E prompt.*
