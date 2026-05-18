# CLAUDE-CODE-PROMPT-v2-ui-v0.6-F-closeout

**Last Updated:** 05-16-26 19:05
**Series:** v2-ui-v0.6
**Slice:** F (6 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.6-E (status, error, warning + crash banner)

## Purpose

Slice **F — Closeout** is the final slice of v0.6. After slices A–E land, every visual surface in v0.6 renders per the design system. Slice F mechanically completes the release: bumps `__version__`, adds the README release note, adds the WCAG AA contrast verification test, runs a final regression pass, and produces the integration smoke confirmation.

Five deliverables:

1. **`__version__` bump.** `crmbuilder-v2/src/crmbuilder_v2/__init__.py` updated from `"0.5.0"` to `"0.6.0"`. About dialog (re-skinned in slice A) reads via `importlib.metadata` with `__version__` as fallback per the CLAUDE.md v2 version-source convention.

2. **README v0.6 release note.** `crmbuilder-v2/README.md` extended with a v0.6 entry matching v0.5's format: one-paragraph summary plus a bullet list of highlights (design tokens module, bundled Inter + JetBrains Mono fonts, bundled Lucide icons, five button categories, master-pane delegate, sub-sectioned ReferencesSection, modal elevation, retired legacy color values).

3. **WCAG contrast test module.** New `tests/crmbuilder_v2/ui/test_token_contrast.py` exercising the WCAG AA contrast check per DEC-107 against every text-on-background combination listed in design pass §4.4 (A9). Uses the `wcag-contrast-ratio` PyPI library (or a hand-rolled implementation if the library isn't available — slice F's prompt-runner picks). The test is a build gate; failures are not tolerated.

4. **Full regression test pass.** `uv run pytest tests/crmbuilder_v2/ -v` returns green across the entire suite, including the new WCAG contrast test module.

5. **Final integration smoke.** Open the application; verify About dialog shows v0.6.0; open each panel and confirm rendering matches the design system end-to-end; open each dialog category and confirm chrome / buttons / fields render per the design pass.

This slice does NOT include: SES-030 session record application via `apply_close_out.py` — that is operator-authored after slice F lands. Status entity versioned-replace from "v0.5 complete" to "v0.6 complete" — operator-authored through the desktop versioned-replace dialog. Both happen post-slice-F per implementation plan §9.

## Project context

Slice F is mechanical. The architectural work for v0.6 is complete. Slice F's job is to (a) make the version bump official, (b) document the release, (c) add the one new automated check the release needs, (d) confirm the suite passes, and (e) confirm visual coherence end-to-end via integration smoke.

The WCAG contrast check is the most substantive new code in slice F, but even it is mechanical: read the design pass §4.4 (A9) combinations, compute the contrast ratio for each, assert each meets the AA threshold for its text size. If any fails, a token-value adjustment lands in `styling.py` and slice F re-runs.

## Pre-flight

1. Working directory: crmbuilder repo clone.
2. `git status` clean. Pull latest: `git pull --rebase origin main`. Slices A–E must be on `main`.
3. Verify prior slices:
   - `__version__` in `crmbuilder-v2/src/crmbuilder_v2/__init__.py` is `"0.5.0"` (or whatever v0.5 set it to).
   - About dialog renders per slice A.
   - Sidebar, master pane, panel chrome, dialogs, status surfaces all render per slices A–E.
   - App launches cleanly.
4. Storage operational; v0.5 test suite passes.

## Reading order

1. `crmbuilder/CLAUDE.md`.
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` (focus: §5 Cross-Cutting Concerns; §6 ACs F1–F7; §11 Decisions to Be Recorded).
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` (focus: §4 Slice F; §6 Test Target; §7 Screenshot Capture Protocol; §8 Version Source; §9 Closeout Discipline).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` (focus: §4.4 A9 — the WCAG combinations to test).
5. v2 source files:
   - `crmbuilder-v2/src/crmbuilder_v2/__init__.py` — `__version__` bump.
   - `crmbuilder-v2/README.md` — v0.6 release note insertion.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` — `TOKENS["light"]` dict consumed by the WCAG test.

## Step 1 — `__version__` bump

Edit `crmbuilder-v2/src/crmbuilder_v2/__init__.py`:

Change `__version__ = "0.5.0"` to `__version__ = "0.6.0"`.

(If `__version__` is sourced from `importlib.metadata` with fallback, also confirm `pyproject.toml`'s `[project]` version is bumped to `0.6.0` — the CLAUDE.md v2 version-source convention names `__init__.py` as canonical but `pyproject.toml` may need parallel update for the `importlib.metadata` fallback to work. Slice F's prompt-runner verifies and updates both if needed.)

### 1.1 Acceptance verification (Step 1)

- Reading `crmbuilder_v2.__version__` in a Python REPL returns `"0.6.0"`.
- Opening the About dialog shows "0.6.0" in the Version field.

## Step 2 — README v0.6 release note

Edit `crmbuilder-v2/README.md` adding a v0.6 entry. Match the format used for v0.5 — typically a heading like `## v0.6 — Visual design system retrofit (May 2026)` (or similar phrasing aligned with v0.5's style), followed by:

- One paragraph summarizing v0.6: discharges PI-001 (full styling design pass) per DEC-024 after four prior deferrals; introduces a complete design token system (`ui/styling.py` rewritten) with theme-keyed structure ready for future dark mode; bundles Inter Variable and JetBrains Mono Variable fonts and the Lucide icon library; applies token-driven visual treatment uniformly across sidebar, panels, dialogs, form controls, status surfaces, and the crash banner.

- A bullet list of highlights:
  - Design tokens module: 60+ tokens covering spacing, color (9-step neutral, accent, status), typography, radius, border, elevation. Theme-keyed; dark-mode-ready without retrofit.
  - Bundled assets: Inter Variable, JetBrains Mono Variable (both OFL); Lucide icons (ISC).
  - Sidebar and master-pane delegate: shared selected-state vocabulary (left accent bar + tint + medium-weight text) per DEC-093.
  - Panel retrofit: panel chrome, label-above form layout, ReferencesSection sub-sectioned plain-list rendering.
  - Dialogs: five button categories with full state coverage; internal context strip on record-editing dialogs; delete-confirm body treatment.
  - Status surfaces: inline form-field error treatment; panel-level warning callouts (warning-amber, distinct from danger-red); error-dialog header retoken; crash banner folded into the design system.
  - Modal elevation: drop shadow + backdrop overlay on every QDialog.
  - Retired legacy color constants: `#1F3864` (navy), `#f4f4f4`, `#444`, `#666`, `#888` (grays), `#c1272d` (red), `#b6868a` (disabled-destructive), `#B22222` (legacy warning-as-error).

The exact wording is slice F's prompt-runner's call; match the v0.5 entry's tone and section structure.

### 2.1 Acceptance verification (Step 2)

- `README.md` has a v0.6 section that reads cleanly alongside the v0.5 section.

## Step 3 — WCAG contrast test module

Create `tests/crmbuilder_v2/ui/test_token_contrast.py`:

### 3.1 Library choice

Use `wcag-contrast-ratio` (PyPI, MIT-licensed; small pure-Python library exposing `wcag_contrast_ratio.rgb(rgb1, rgb2) -> float`). Add as a dev dependency in `pyproject.toml` under `[dependency-groups.dev]` (or wherever v2's dev deps live).

If `wcag-contrast-ratio` fails to install or its API has changed, fall back to a hand-rolled implementation of the WCAG 2.x contrast formula:

```python
def _luminance(hex_color: str) -> float:
    """Compute relative luminance per WCAG 2.x."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

def contrast_ratio(hex1: str, hex2: str) -> float:
    """WCAG 2.x contrast ratio between two hex colors."""
    l1, l2 = _luminance(hex1), _luminance(hex2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)
```

### 3.2 Test structure

```python
"""WCAG AA contrast verification for the v0.6 design token system.

Per DEC-107, this is a build gate. Failures are not tolerated.
Each text-on-background combination listed in styling-design-pass.md
§4.4 (A9) is checked against the WCAG AA threshold for its target
text size.

WCAG AA thresholds:
- 4.5:1 minimum for normal-size text (<18pt or <14pt bold).
- 3.0:1 minimum for large-size text (>=18pt or >=14pt bold).
"""

from __future__ import annotations

import pytest

# Import either the library or the fallback implementation:
try:
    from wcag_contrast_ratio import rgb as _ratio
    def _contrast(hex1: str, hex2: str) -> float:
        def _to_rgb(h: str) -> tuple[float, float, float]:
            h = h.lstrip("#")
            return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        return _ratio(_to_rgb(hex1), _to_rgb(hex2))
except ImportError:
    # Fallback inline implementation per Step 3.1
    ...

from crmbuilder_v2.ui.styling import TOKENS

_LIGHT = TOKENS["light"]

# (text_token, background_token, threshold, description)
_COMBINATIONS = [
    ("color.neutral.800", "color.neutral.0", 4.5, "body text on white"),
    ("color.neutral.500", "color.neutral.0", 4.5, "secondary text on white"),
    ("color.neutral.700", "color.neutral.100", 4.5, "read-only field text on disabled bg"),
    ("color.accent.default", "color.neutral.0", 4.5, "accent text on white (text-link buttons)"),
    ("color.danger.text", "color.neutral.0", 4.5, "danger text on white"),
    ("color.warning.default", "color.neutral.0", 4.5, "warning text on white"),
    ("color.neutral.0", "color.accent.default", 4.5, "white on accent (primary button text)"),
    ("color.neutral.0", "color.danger.default", 4.5, "white on danger (destructive button text, crash banner)"),
]

@pytest.mark.parametrize("text_token,bg_token,threshold,description", _COMBINATIONS)
def test_wcag_aa_contrast(text_token, bg_token, threshold, description):
    text_color = _LIGHT[text_token]
    bg_color = _LIGHT[bg_token]
    ratio = _contrast(text_color, bg_color)
    assert ratio >= threshold, (
        f"WCAG AA failure: {description} "
        f"({text_token}={text_color} on {bg_token}={bg_color}) "
        f"ratio={ratio:.2f}; required>={threshold}"
    )
```

### 3.3 Threshold handling

All current combinations from design pass §4.4 target AA at the relevant text size:
- Body text combinations: AA threshold 4.5:1 (small text).
- Accent text on white (`color.accent.default` on `color.neutral.0` = 4.61:1 per design pass): passes AA at small text.
- Warning on white: design pass notes "borderline at caption size" — confirmed 4.7:1 at body size, possibly fails at caption.

If the warning-on-white combination fails the AA threshold of 4.5:1 at the body-size threshold, the warning token darkens slightly (per PRD Open Question #4 and the design pass §4.4 note). Recommended adjustment: change `color.warning.default` from `#B0731A` to `#9D6517` in `styling.py`'s `TOKENS["light"]` dict. Re-run the test. The change is isolated to `styling.py` — no other slice's work is affected.

### 3.4 Acceptance verification (Step 3)

- `uv run pytest tests/crmbuilder_v2/ui/test_token_contrast.py -v` passes — all 8 combinations meet AA at their target size.
- If any combination fails, slice F's prompt-runner applies the token-value adjustment, re-runs, and updates the design pass §4.4 / PRD §10 open question accordingly (the adjustment closes the open question with a concrete resolution).

## Step 4 — Full regression test pass

Run `uv run pytest tests/crmbuilder_v2/ -v`.

The expected result is green across the entire suite:
- v0.5 test suite (engagement management functional tests).
- All v0.5 UI tests for engagement panel rendering — slice C may have updated assertions on the engagement panel's master-pane rendering; verify those changes don't break the test suite.
- All v0.4 and earlier UI tests — slices C and D may have updated assertions related to ReferencesSection rendering and button styling; verify those changes propagate cleanly.
- The new `test_token_contrast.py` module.

If any test fails:
- If the failure is a v0.5 functional regression (a button no longer triggers an action, a dialog doesn't open), the failure is NOT acceptable in slice F — investigate which slice introduced the regression and fix.
- If the failure is a v0.5 visual test asserting on legacy styling (e.g., a test that looks for `#1F3864` in some rendered widget property), the assertion was supposed to be updated in the earlier slice that retired the legacy styling. Slice F's prompt-runner updates the assertion to match the new design system and notes the update.

### 4.1 Acceptance verification (Step 4)

`uv run pytest tests/crmbuilder_v2/ -v` returns 0 (success) across the entire suite.

## Step 5 — Final integration smoke

Launch the application: `uv run crmbuilder-v2` (or the appropriate launcher).

Visit every surface in turn and confirm rendering matches the design system end-to-end. The checklist:

- [ ] Splash screen renders with new accent blue (`#1F5FBF`) and Inter font.
- [ ] Main window opens. Sidebar renders 220px wide with `color.neutral.100` background, Governance/Methodology group headers, entries in body-size text.
- [ ] Click each sidebar entry. Selected-state vocabulary appears (3px left accent bar + tinted background + medium-weight text). Stale dot color is `#1F5FBF`.
- [ ] Each panel opens with `color.neutral.50` panel background, 16px outer padding, 12px-wide splitter handle. Default 45/55 split renders.
- [ ] Master pane in each panel renders with new column headers, 28px rows, hover/selected vocabulary matching sidebar. Identifier column in mono font.
- [ ] Topics panel uses Lucide chevrons for branch indicators; indentation respects accent bar.
- [ ] Detail pane in each panel: label-above forms, required-field asterisk icons, status combo hint caption (where applicable), notes collapsible toggle with chevron + "Notes".
- [ ] ReferencesSection renders sub-sectioned plain-list grouping (verify on Decisions panel with DEC-076 — should show "Decided in", "Is about" headers).
- [ ] Open an edit dialog: drop shadow + backdrop overlay; internal context strip with mono identifier + record name; label-above form; Primary Save + Secondary Cancel + Destructive Delete buttons.
- [ ] Open a create dialog: no context strip; same form layout; Save/Cancel buttons.
- [ ] Open a delete-confirm: no context strip; relaxed-line-height body; Destructive Delete right-aligned with Cancel.
- [ ] About dialog: wordmark + tagline + vertical metadata list; mono path values; Close button right-aligned; v0.6.0 visible.
- [ ] Trigger a validation error on any form: inline error label in danger-text below field; field border red.
- [ ] Processes panel with a soft-deleted-domain record: WarningCallout renders with amber + circle-alert icon.
- [ ] Trigger an API error: error dialog with Lucide circle-x header + danger-text title; drop shadow + backdrop.
- [ ] (If feasible) simulate a crash condition: banner re-skinned with danger-red background, white text, circle-alert icon.

### 5.1 Acceptance verification (Step 5)

Every checklist item passes visually.

## Commit message template

```
v2: ui v0.6 slice F — closeout (release v0.6.0)

Final slice of UI v0.6. Mechanically completes the release
that discharges PI-001 after four prior deferrals (DEC-024,
DEC-026, DEC-037, DEC-042 → DEC-076 reopening).

Version bump:
- crmbuilder-v2/src/crmbuilder_v2/__init__.py: __version__ =
  '0.6.0'
- pyproject.toml: project version 0.6.0 (if applicable to
  importlib.metadata fallback)

README:
- v0.6 release note section added matching v0.5's format
- Highlights: tokens module, bundled fonts/icons, selected-
  state vocabulary, panel retrofit, dialog work, status
  surfaces, modal elevation, retired legacy colors

WCAG contrast test (tests/crmbuilder_v2/ui/test_token_contrast.py):
- Build-gate test per DEC-107
- 8 text-on-background combinations from design pass §4.4
  (A9) verified against WCAG AA threshold (4.5:1 for small
  body text)
- Uses wcag-contrast-ratio library with hand-rolled fallback
- If warning-on-white fails AA at body size, the token value
  in styling.py is adjusted (recommended #B0731A → #9D6517)
  and the test re-runs

Full regression:
- uv run pytest tests/crmbuilder_v2/ -v passes green across
  the entire suite (v0.5 functional + UI tests, all v0.4
  earlier tests with retoken-assertion updates from slices
  C/D, new WCAG test module)

Integration smoke:
- Every panel, dialog, form-control, status surface verified
  rendering per the design system end-to-end via the slice F
  checklist

v0.6 IS RELEASED.

Operator-authored steps to complete the release (next):
- Status entity versioned-replace from 'v0.5 complete' to
  'v0.6 complete' via the desktop versioned-replace dialog
- SES-030 session record application via apply_close_out.py
  prompt at PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-
  PROMPT-apply-close-out-ses-030.md (authored at v0.6 plan
  close, applied after slice F)

No schema changes; no API changes. PI-001 discharged.
```

After committing:
- `git push origin main`
- Notify Doug that v0.6 build is complete. Operator-authored closeout follows: status versioned-replace + SES-030 application.

## Out of slice

- SES-030 session record application via `apply_close_out.py` — operator-authored after slice F lands. The close-out apply prompt and `close-out-payloads/ses_030.json` are authored at this conversation's close, NOT in slice F.
- Status entity versioned-replace from "v0.5 complete" to "v0.6 complete" — operator-authored through the desktop versioned-replace dialog.
- v0.7+ planning conversations and slice work.

---

*End of slice F prompt. End of v2 UI v0.6 slice series.*
