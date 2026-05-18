# CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-followup-force-light-palette

**Last Updated:** 05-18-26 06:30
**Series:** v2-ui-v0.6
**Slice:** A follow-up (defect fix discovered after slice B landed)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion design pass:** `PRDs/product/crmbuilder-v2/styling-design-pass.md`
**Predecessor:** v2-ui-v0.6 slices A and B — committed and pushed; UI rendering broken on Linux Mint

## Purpose

Slice A's `build_application()` in `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` constructs a `QApplication`, loads fonts, and applies the project QSS — but does NOT force a Qt application style or palette. On platforms that delegate Qt rendering to the OS native theme (Linux Mint with Cinnamon is the surfaced case; macOS and other Linux distros likely affected to varying degrees), Qt picks up OS palette values for any widget surface the project QSS doesn't explicitly override. The project QSS focuses on chrome, text inputs, table views, headers, buttons, and panel containers; it does NOT have explicit rules for every QLabel, QFrame, or generic QWidget background. Those surfaces inherit their palette from `QPalette` roles (Window, Base, Text, etc.) which Qt sources from the OS theme.

On Doug's Linux Mint with a dark GTK theme, this produces an unusable rendering: black backgrounds (sourced from the GTK Window role) with near-black text (`color.neutral.800` = #272D36 from the QSS) rendering as "dark blue on black" — unreadable. Changing the GTK theme to a "light" Mint theme doesn't reliably fix it because some Mint "light" themes still have dark palette roles, and Qt's GTK reading is sensitive to the specific theme structure.

The fix neutralizes OS theme influence:

1. Force `QStyle` to **Fusion** — Qt's cross-platform style that doesn't delegate to GTK or the native platform style. Renders identically across Linux/macOS/Windows.
2. Force `QPalette` to an explicit light palette built from the existing `TOKENS["light"]` values — so any widget surface that doesn't have an explicit QSS rule still gets light-theme colors from the palette, matching the design pass.

After this fix, the application renders identically regardless of OS theme. The styling design pass intent (DEC-088, DEC-089) is preserved; the WCAG contrast check in slice F operates against the same token values as before.

**Scope: small surgical commit.** Two changes total: imports plus a code block inside `build_application()`. Plus one regression test verifying the style and key palette roles after construction.

## Project context

The styling design pass shipped a light-theme-only release per DEC-088 and DEC-089. The QSS in `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` is correct and complete for its scope; the bug is not in the QSS but in the application bootstrap that should establish a palette baseline before the QSS takes over.

Forcing `QStyle.Fusion` plus a `QPalette` is the standard remedy for "Qt app on Linux looks wrong because of GTK theme bleed-through." It's a defensive measure: on platforms where the OS theme happens to be light-theme-compatible, the change is a no-op visually; on platforms where the OS theme conflicts, the change makes the app render correctly.

This is not a design-pass deviation — palette roles map 1:1 to existing TOKENS values. WCAG contrast verification in slice F is unaffected (the contrast check operates on TOKENS values, not on rendered palette).

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone root.
2. Confirm `git status` is clean.
3. Confirm git identity is `Doug Bower <doug@dougbower.com>`.
4. Pull latest: `git pull --rebase origin main`.
5. Confirm slice A and slice B have landed: `grep -l "build_application" crmbuilder-v2/src/crmbuilder_v2/ui/app.py` should match; `ls crmbuilder-v2/src/crmbuilder_v2/ui/widgets/master_pane_delegate.py` should succeed.
6. Confirm full v2 test suite passes pre-fix as the regression baseline: `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -q`. Note the count (baseline 1236 passed, 1 skipped per slice B).

## Reading order

1. `crmbuilder/CLAUDE.md` — v2 section, especially the styling workstream pointers.
2. `PRDs/product/crmbuilder-v2/styling-design-pass.md` §1.2 (color tokens) — confirm the TOKENS values you'll be referencing from the palette construction match design intent.
3. `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` — read `build_application()` to identify the exact insertion point (between `QApplication` construction and `_load_bundled_fonts()`).
4. `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` — confirm the `TOKENS["light"]` dict keys and values you'll consume.
5. `tests/crmbuilder_v2/ui/test_app.py` or similar existing test for `build_application()` — find the existing test fixture pattern to mirror in the new regression test.

## Step 1 — Force Fusion style and light palette in `build_application()`

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py`. Add imports at the top (alongside existing PySide6 imports):

```python
from PySide6.QtGui import QPalette, QColor
```

If `from crmbuilder_v2.ui.styling import apply_stylesheet` already exists, extend it to also import `TOKENS`:

```python
from crmbuilder_v2.ui.styling import apply_stylesheet, TOKENS
```

In `build_application()`, after the existing `app = QApplication(argv if argv is not None else sys.argv)` line and before the existing `_load_bundled_fonts()` call, insert:

```python
# Force Fusion style + explicit light palette so OS theme (GTK on Linux,
# native on macOS/Windows) cannot bleed through to widget surfaces that
# the project QSS doesn't explicitly cover. The palette colors mirror
# TOKENS["light"] so the application bootstrap stays consistent with
# the styling design pass.
app.setStyle("Fusion")
_apply_light_palette(app)
```

Below `build_application()`, add the helper function `_apply_light_palette()`:

```python
def _apply_light_palette(app: QApplication) -> None:
    """Force an explicit light palette built from TOKENS["light"].

    Ensures widget surfaces that don't have explicit QSS rules still
    render against light-theme colors regardless of OS theme. Palette
    role-to-token mapping mirrors the design pass §1.2 color tokens
    and stays in sync with TOKENS without duplicating values.
    """
    light = TOKENS["light"]
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(light["color.neutral.0"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(light["color.neutral.800"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(light["color.neutral.0"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(light["color.neutral.50"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(light["color.neutral.0"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(light["color.neutral.800"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(light["color.neutral.800"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(light["color.neutral.500"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(light["color.neutral.0"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(light["color.neutral.700"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(light["color.danger.default"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(light["color.accent.default"]))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(light["color.accent.pressed"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(light["color.accent.subtle"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(light["color.neutral.900"]))
    # Disabled-state roles for grayed-out widgets.
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
                     QColor(light["color.neutral.300"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
                     QColor(light["color.neutral.300"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
                     QColor(light["color.neutral.300"]))
    app.setPalette(palette)
```

Also handle the `existing is not None` branch in `build_application()` — when a `QApplication` already exists (test re-use case), apply the style + palette there too:

```python
existing = QApplication.instance()
if existing is not None:
    existing.setStyle("Fusion")          # NEW
    _apply_light_palette(existing)        # NEW
    _load_bundled_fonts()
    apply_stylesheet(existing)
    return existing
```

This keeps the test fixtures consistent with production behavior.

## Step 2 — Regression test

Add `tests/crmbuilder_v2/ui/test_app_palette.py`:

```python
"""Regression test for v0.6 slice A follow-up — force-light-palette fix.

Verifies that build_application() sets QStyle to Fusion and that
key QPalette color roles match TOKENS["light"] values, neutralizing
OS theme bleed-through on platforms where Qt delegates to the
native style (Linux+GTK is the surfaced case; macOS native style
similarly affected).
"""

from PySide6.QtGui import QPalette, QColor

from crmbuilder_v2.ui.app import build_application
from crmbuilder_v2.ui.styling import TOKENS


def test_style_is_fusion(qapp):
    app = build_application()
    assert app.style().objectName().lower() == "fusion", \
        f"expected Fusion style, got {app.style().objectName()}"


def test_palette_window_is_light_neutral(qapp):
    app = build_application()
    palette = app.palette()
    expected = QColor(TOKENS["light"]["color.neutral.0"])
    actual = palette.color(QPalette.ColorRole.Window)
    assert actual == expected, \
        f"Window role expected {expected.name()}, got {actual.name()}"


def test_palette_text_is_dark_neutral(qapp):
    app = build_application()
    palette = app.palette()
    expected = QColor(TOKENS["light"]["color.neutral.800"])
    actual = palette.color(QPalette.ColorRole.Text)
    assert actual == expected, \
        f"Text role expected {expected.name()}, got {actual.name()}"


def test_palette_window_text_is_dark_neutral(qapp):
    """The label-readability case from the slice B regression — without
    this fix, QLabel widgets without explicit QSS rules render
    WindowText against Window, producing dark text on dark background."""
    app = build_application()
    palette = app.palette()
    expected = QColor(TOKENS["light"]["color.neutral.800"])
    actual = palette.color(QPalette.ColorRole.WindowText)
    assert actual == expected, \
        f"WindowText role expected {expected.name()}, got {actual.name()}"


def test_palette_highlight_uses_accent_subtle(qapp):
    app = build_application()
    palette = app.palette()
    expected = QColor(TOKENS["light"]["color.accent.subtle"])
    actual = palette.color(QPalette.ColorRole.Highlight)
    assert actual == expected, \
        f"Highlight role expected {expected.name()}, got {actual.name()}"
```

The `qapp` fixture is the existing pytest-qt fixture used in other v0.6 UI tests. If `build_application()` requires teardown (e.g., the QApplication instance shouldn't leak across tests), follow the v0.5 / slice A patterns from existing test files for the fixture lifecycle.

## Acceptance verification

Before committing:

1. **New tests pass.** `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ui/test_app_palette.py -v` — 5 tests pass.
2. **Full v2 suite stays green.** `cd crmbuilder-v2 && uv run pytest tests/crmbuilder_v2/ -q` — 1236 baseline + 5 new = 1241 passed, 1 skipped. No regressions.
3. **Visual verification (operator, Doug).** Launch the application via `uv run crmbuilder-v2-api &` plus the desktop launcher and confirm:
   - Sidebar renders with light backgrounds (neutral.100 chrome, neutral.0 panel content)
   - Master pane renders with white background, near-black text — labels are readable
   - Buttons render with white background and dark text per the design pass
   - About dialog (slice A surface) still renders correctly
   - Sidebar group headers, master pane rows, soft-deleted treatment all render per slice B intent
4. **Verify identical render across themes.** If feasible: change Linux Mint to a different theme (any flavor — dark, light, hybrid) and re-launch the app. The app should render identically every time. The screenshot acceptance gate is satisfied regardless of OS theme after this fix.

## Commit

```bash
git add crmbuilder-v2/src/crmbuilder_v2/ui/app.py \
        tests/crmbuilder_v2/ui/test_app_palette.py

git commit -m "v2: ui v0.6 slice A follow-up — force Fusion style + explicit light palette to neutralize OS theme bleed-through

Slice A's build_application() constructed QApplication, loaded fonts,
and applied the project QSS but did not force a Qt style or palette.
On Linux Mint with a Cinnamon/GTK theme, Qt picked up GTK palette
values for widget surfaces the project QSS does not explicitly cover
(QLabel backgrounds, QWidget container backgrounds). The result on a
dark Mint theme: black backgrounds with near-black text rendered as
'dark blue on black' — unreadable labels across the UI.

Changing the OS theme alone did not reliably fix it; some Mint 'light'
themes still have dark palette roles, and Qt's GTK reading was
sensitive to the specific theme structure.

The fix:
- Force QStyle to Fusion (cross-platform Qt-native style, does not
  delegate to GTK or native platform styles)
- Force QPalette to an explicit light palette built from TOKENS['light']
  so widget surfaces without explicit QSS rules render in design-pass
  light-theme colors

After this fix, the application renders identically regardless of OS
theme. Palette role-to-token mapping mirrors design pass §1.2 color
tokens; no design pass values are duplicated or drifted.

Regression test: tests/crmbuilder_v2/ui/test_app_palette.py covers
five palette role assertions plus the Fusion style assertion. The
WindowText/Window contrast case (the label-readability bug) is
explicitly tested as test_palette_window_text_is_dark_neutral.

Test count: 1236 baseline + 5 new = 1241 passed, 1 skipped."
```

Doug pushes. Do NOT push.

## What NOT to do

- Do NOT modify `styling.py` — the QSS and TOKENS values are correct. The bug is in the application bootstrap, not in the design pass values.
- Do NOT introduce a new dark-theme branch or theme-switching plumbing. v0.6 is light-theme-only per DEC-089; dark theme is deferred to a future release.
- Do NOT change the WCAG contrast check in slice F — palette role mapping uses the same TOKENS values, so contrast verification is unaffected.
- Do NOT bump `__version__` — this is a follow-up patch to slice A, not a new release.
- Do NOT modify any panel, dialog, widget, or master-pane delegate code — slice A's foundation and slice B's sidebar/master-pane retrofits are correct; the fix is strictly to the QApplication bootstrap.
- Do NOT modify the screenshot acceptance gate or PRD acceptance criteria — they remain as authored.
- Do NOT touch slice C work in progress if it's running concurrently — this fix is in `app.py` and is orthogonal to slice C's panel-retrofit work.

---

*End of prompt.*
