# CLAUDE-CODE-PROMPT-v2-ui-v0.6-A-foundation

**Last Updated:** 05-16-26 17:50
**Series:** v2-ui-v0.6
**Slice:** A (1 of 6)
**Status:** Ready to execute
**Companion PRD:** `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md`
**Companion implementation plan:** `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md`
**Predecessor slice:** v2-ui-v0.5-? (UI v0.5 closeout — TBD at v0.6 build-execution time; v0.5 ships first per DEC-105)

## Purpose

This is the first of six slices that build the CRMBuilder v2 desktop UI v0.6 — the styling release that discharges PI-001 after four prior deferrals. Slice **A — Foundation + About dialog** delivers:

1. **Design token module.** Rewriting `ui/styling.py` end-to-end with the theme-keyed token system from `styling-design-pass.md` §1 plus the `t()` accessor and `build_app_stylesheet()` generator. Filename `styling.py` retained — DEC-024's minimal-QSS-stub module is the file PI-001 was created to discharge, and rewriting in place preserves the `apply_stylesheet(app)` entry point.

2. **Font asset bundling + loading.** Inter Variable and JetBrains Mono Variable committed as `.ttf` files under `ui/assets/fonts/`. Loaded at app startup via `QFontDatabase.addApplicationFont()` per DEC-090.

3. **Icon asset bundling + loader.** Lucide SVG set (14 icons in initial wave) committed under `ui/assets/icons/lucide/`. New `ui/icons.py` providing the `lucide()` loader with runtime color tinting per DEC-092.

4. **Modal elevation infrastructure.** New `ui/elevation.py` (drop-shadow helper) and `ui/widgets/modal_backdrop.py` (`ModalBackdropOverlay` plus `attach()` / `detach()` module functions) per DEC-091.

5. **Per-dialog elevation + backdrop hooks.** Six file edits: three dialog base classes (`ui/base/crud_dialog.py`, `ui/base/versioned_replace_dialog.py`, `ui/base/list_detail_panel.py`) plus three standalone `QDialog` subclasses (`ui/about_dialog.py`, `ui/dialogs/error.py`, `ui/dialogs/reference_delete.py`).

6. **Base widget hooks for token-consuming chrome.** `ui/base/list_detail_panel.py` picks up panel chrome via class-name hooks readable by the project-level QSS.

7. **App-level QSS application.** `ui/app.py` calls `apply_stylesheet(app)` from `styling.py` at startup right after font loading.

8. **About dialog re-skin.** `ui/about_dialog.py` restructured per design pass §2.8 and DEC-094 — wordmark + tagline + vertical metadata list. Acts as the canary surface exercising the full token system end-to-end.

9. **Splash screen update.** `ui/splash.py` migrates from legacy `ACCENT_COLOR` / `DEFAULT_FONT_FAMILY` constants to the new `t()` accessor.

This slice does NOT add: sidebar visual treatment (slice B), master-pane delegate (slice B), panel chrome beyond `list_detail_panel.py`'s base hooks (slice C), per-panel detail-pane form layout change (slice C), `ReferencesSection` restructure (slice C), button categories (slice D), form-control state coverage (slice D), internal context strip on record-editing dialogs (slice D), status / error / warning surface retoken (slice E), crash banner re-skin (slice E), `__version__` bump (slice F), README release note (slice F), WCAG contrast test module (slice F).

This slice does NOT write planning records (SES-030, DEC-105/096/097) to the database. Per the session-record-at-close pattern established after SES-008, those are authored by Doug through the `apply_close_out.py` script at the v0.6 build's closeout, not inside a Claude Code slice.

## Project context

UI v0.5 ships engagement management as a separate release per DEC-105 (version bundling resolved as v0.6 separate, not bundled). v0.6 is the parallel styling workstream reopening PI-001 per DEC-076. The styling design pass document at `PRDs/product/crmbuilder-v2/styling-design-pass.md` (Conversation 1 output, SES-027) is the authoritative source for visual decisions; this slice's prompt cites it rather than restating values.

Slice A is the only slice whose work is foundational rather than per-surface. Get the token system right and the five remaining slices follow cleanly; get it wrong and five downstream slices each carry the consequence. The About dialog re-skin in this same slice is the canary — it exercises tokens, fonts, icons, the modal elevation infrastructure, and the dialog hook pattern end-to-end before any panel work begins.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set:
   - `git config user.name` should return `Doug Bower`
   - `git config user.email` should return `dbower44022@users.noreply.github.com`
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the storage system is operational. Verify-first, only start if not already running:
   - First check: `curl -sf http://127.0.0.1:8765/health` — if it returns 200, the API is already running; proceed to step 6.
   - If the health check fails (connection refused or no response), start the API in the background: `uv run crmbuilder-v2-api &`. Wait ~3 seconds, then re-run the health check. If the second check still fails, stop and report to Doug before proceeding.
6. Confirm the existing v2 test suite passes: `uv run pytest tests/crmbuilder_v2/ -v`. Note the test count; this is the regression net for slice A.

## Reading order

Before producing any code, read the following in order:

1. `crmbuilder/CLAUDE.md` — universal entry. Pay attention to the v2 architecture section, especially the v2 version-source convention and the API envelope (`{data, meta, errors}`).
2. `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` — the requirements you are implementing. All slices.
3. `PRDs/product/crmbuilder-v2/ui-v0.6-implementation-plan.md` — the slice breakdown. Pay particular attention to **Slice A — Foundation + About dialog** in section 4, and to section 2.12 (token-consumption mechanism), 2.13 (font and icon asset bundling), 2.14 (screenshot capture protocol), 2.15 (WCAG contrast check).
4. `PRDs/product/crmbuilder-v2/styling-design-pass.md` — the authoritative source for visual decisions. Read §1 in full (tokens) and §2.8 in full (About dialog). §1.6 (icon library) and §1.5 (elevation/depth) deserve particular attention because they specify mechanism details.
5. v2 source files you will modify:
   - `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` — the v0.1 minimal QSS stub, being rewritten in place.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` — startup wiring; existing `apply_stylesheet(app)` call site.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/splash.py` — consumer of legacy constants.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py` — being restructured.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/crud_dialog.py` — contains both `EntityCrudDialog` and `EntityCrudDeleteDialog`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/versioned_replace_dialog.py` — contains `VersionedReplaceDialog`.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` — needs token-consuming chrome hooks.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/error.py` — standalone `QDialog` subclass.
   - `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/reference_delete.py` — standalone `QDialog` subclass.

## Step 1 — Rewrite `ui/styling.py`

Replace the contents of `crmbuilder-v2/src/crmbuilder_v2/ui/styling.py` end-to-end. The new module exposes the design system: token dict, accessor, app-stylesheet builder, and the preserved `apply_stylesheet(app)` entry point.

### 1.1 Module docstring

Rewrite the module docstring to state the new purpose. Reference DEC-024 (the original deferral that created PI-001), DEC-076 (the workstream reopening), and PI-001 itself. Include a note that previous versions of this file were a minimal QSS stub; v0.6 discharges PI-001 by rewriting in place.

### 1.2 `TOKENS` dict

Define `TOKENS: dict[str, dict[str, str]]` with one theme key `"light"` (per DEC-088: theme-keyed structure, dark-mode-ready without retrofit). Every token from design pass §1 is codified. Inline every value as Python string literals; do not import from a separate file. Categories in order:

- **Spacing** (`space.0` through `space.12`) — `"0"`, `"4px"`, `"8px"`, `"12px"`, `"16px"`, `"20px"`, `"24px"`, `"32px"`, `"40px"`, `"48px"`.
- **Color — accent** (`color.accent.default`, `color.accent.hover`, `color.accent.pressed`, `color.accent.subtle`, `color.accent.focusring`) per design pass §1.2.2.
- **Color — neutral** (`color.neutral.0` through `color.neutral.900`) per design pass §1.2.3 — nine values.
- **Color — danger / warning / success** per design pass §1.2.4.
- **Typography — family** (`font.family.default` = `"Inter"`, `font.family.mono` = `"JetBrains Mono"`).
- **Typography — size** (`font.size.caption` through `font.size.heading_1`) — seven values per design pass §1.3.
- **Typography — weight** (`font.weight.regular` through `font.weight.bold`) per design pass §1.3 — four values, as strings of the integer weight (`"400"`, `"500"`, `"600"`, `"700"`).
- **Typography — line height** (`font.line.tight` / `font.line.normal` / `font.line.relaxed`) per design pass §1.3.
- **Radius** (`radius.none` through `radius.large`) per design pass §1.4.
- **Border** (`border.hairline`, `border.field`, `border.field_focus`, `border.danger`) per design pass §1.4 — values as full CSS-style strings ready for inlining (e.g., `"1px solid {color.neutral.300}"` would not work since QSS doesn't have variables; either inline the resolved color in the token value, or have `build_app_stylesheet()` resolve them at QSS generation time. Pick the latter for cleaner separation.)
- **Elevation** (`shadow.dialog`, `overlay.modal_backdrop`) per design pass §1.5.

### 1.3 `t()` accessor

Define:

```python
def t(key: str, theme: str = "light") -> str:
    """Lookup a token value by key, defaulting to the light theme."""
    return TOKENS[theme][key]
```

Raise a clear `KeyError` (with the offending key in the message) if the key is missing. Future dark-mode work changes only the `theme` argument default; no consumer code changes.

### 1.4 `build_app_stylesheet(tokens) -> str`

Define `build_app_stylesheet(tokens: dict[str, str]) -> str` that takes a single theme's dict (NOT the outer two-level dict) and returns the QSS string applied at app startup. Take the theme dict as argument so the function is testable in isolation (slice F's WCAG contrast check consumes the dict directly via `TOKENS["light"]`).

The QSS string contains:

- **Default `*` rule** setting `font-family` to `font.family.default`, `font-size` to `font.size.body`, and `color` to `color.neutral.800`. Mirrors the existing v0.1 stub but with new values.
- **`QLineEdit` / `QComboBox` / `QPlainTextEdit` rule** setting `border: 1px solid <neutral.300>`, `padding: <space.1> <space.2>`, `background: <neutral.0>`. Resolves border/field tokens by inlining the appropriate neutral value.
- **`QLineEdit:focus`, `QComboBox:focus`, `QPlainTextEdit:focus` rule** setting `border: 1px solid <accent.default>`.
- **`QListWidget` rule** setting `background: <neutral.100>` (preparation for sidebar work in slice B; the rule is harmless on non-sidebar QListWidgets since selected/hover treatment will be specialised in slice B).
- **`QTableView` rule** removing the legacy `alternate-background-color` (design pass §2.3: no alternating row shading). Selected-state and row dividers land in slice B via the master-pane delegate.
- **`QTableView::section` (column header) rule** setting `background: <neutral.100>`, `border: 0`, `border-bottom: 1px solid <neutral.200>`, `padding: <space.2> <space.3>`, `color: <neutral.700>`, `font-weight: <font.weight.semibold>`.
- **`QPushButton` default rule** setting transparent background, 1px `<neutral.300>` border, `<neutral.700>` text, `<font.weight.medium>`, padding `<space.1> <space.3>`, `border-radius: <radius.subtle>` (3px). This is the Secondary button category by default per design pass §2.5; explicit Primary/Destructive/Text/Icon-only treatments land in slice D via the `buttonCategory` property selector.
- **`QPushButton:focus` rule** preserving the existing focus-border treatment but using the new `accent.default`.
- **`QLabel[role="error"]` rule** setting `color: <danger.text>`. Replaces the v0.1 `#B22222` reference.

Slice A keeps the QSS deliberately minimal — only rules covering app-wide chrome that every widget picks up. Per-category button styling, sidebar treatment, master-pane treatment, and ReferencesSection treatment are all in later slices.

### 1.5 `apply_stylesheet(app)` entry point

Preserve the signature `apply_stylesheet(app: QApplication) -> None`. Implementation calls `app.setStyleSheet(build_app_stylesheet(TOKENS["light"]))`. `app.py` consumers do not need to change.

### 1.6 Legacy constants removed

Delete the `ACCENT_COLOR`, `ACCENT_HOVER`, `ERROR_TEXT_COLOR`, `DEFAULT_FONT_FAMILY`, `DEFAULT_FONT_POINT_SIZE` constants. The `splash.py` consumer is updated in Step 8 to use the new `t()` accessor.

### 1.7 Acceptance verification (Step 1)

- `from crmbuilder_v2.ui.styling import TOKENS, t, build_app_stylesheet, apply_stylesheet` succeeds in a Python REPL.
- `t("color.accent.default")` returns `"#1F5FBF"`.
- `t("font.size.body")` returns `"14px"`.
- `t("space.4")` returns `"16px"`.
- `build_app_stylesheet(TOKENS["light"])` returns a non-empty string containing recognisable QSS rules.

## Step 2 — Font asset bundling and loading

### 2.1 Asset directory

Create `crmbuilder-v2/src/crmbuilder_v2/ui/assets/fonts/`. Download the variable-axis `.ttf` files:

- Inter Variable: `Inter-VariableFont_opsz,wght.ttf` from a tagged stable release of `rsms/inter` on GitHub. As of v0.6's authoring the recommended release is v4.0 or later; verify the latest tagged release at run time.
- JetBrains Mono Variable: `JetBrainsMono-VariableFont_wght.ttf` from a tagged stable release of `JetBrains/JetBrainsMono`. Verify the latest tagged release at run time.

Commit both `.ttf` files alongside an `OFL.txt` license file containing the SIL Open Font License v1.1 text that ships with both font projects.

### 2.2 App startup loading

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/app.py` to load both fonts at startup via `QFontDatabase.addApplicationFont()` BEFORE the main window is constructed. Use `importlib.resources` (or `pathlib` with `__file__`-relative resolution) to locate the bundled `.ttf` files.

Wrap the loading in a try/except that logs a warning on failure but does NOT block app launch — per PRD §3 the fallback is system-default fonts.

The existing `apply_stylesheet(app)` call site moves to AFTER the font loading so the QSS rules (which reference `font.family.default` = `"Inter"`) take effect with the bundled family loaded.

### 2.3 Acceptance verification (Step 2)

- App launches without error after these changes.
- A REPL or smoke script reading `QFontDatabase.families()` returns a list containing both `"Inter"` and `"JetBrains Mono"`.
- If the `.ttf` files are temporarily renamed to simulate a load failure, the app still launches (falls back to system defaults).

## Step 3 — Icon asset bundling and loader

### 3.1 Asset directory

Create `crmbuilder-v2/src/crmbuilder_v2/ui/assets/icons/lucide/`. Commit 14 SVG files from a tagged stable release of `lucide-icons/lucide`: `pencil.svg`, `trash-2.svg`, `rotate-ccw.svg`, `external-link.svg`, `copy.svg`, `plus.svg`, `x.svg`, `chevron-right.svg`, `chevron-down.svg`, `chevron-up.svg`, `circle-alert.svg`, `circle-x.svg`, `check.svg`, `asterisk.svg`. Commit `LICENSE.txt` (Lucide's ISC license text) alongside.

### 3.2 Loader module

Create `crmbuilder-v2/src/crmbuilder_v2/ui/icons.py` exposing:

```python
def lucide(name: str, *, size: int = 16, color_token: str = "color.neutral.700") -> QIcon:
    """Load a Lucide icon at the requested size, tinted to the given token color."""
```

Implementation:

- Locate the SVG file at `ui/assets/icons/lucide/{name}.svg` using `importlib.resources` or `pathlib`-relative resolution.
- Read the SVG text.
- Apply runtime color tinting by substituting the resolved hex color from `t(color_token)` into the SVG's `stroke` and `fill` attributes (Lucide SVGs use `stroke="currentColor"` by default — replace `currentColor` with the resolved hex value).
- Render the tinted SVG via `QSvgRenderer` into a `QPixmap` at the requested size with HiDPI device-pixel-ratio handling.
- Wrap the pixmap in a `QIcon` and return.
- Cache the result by `(name, size, color_token)` tuple in a module-level dict; subsequent calls with the same arguments return the cached `QIcon`.
- Raise `FileNotFoundError` with a clear message if the named SVG doesn't exist in the bundle.

### 3.3 Acceptance verification (Step 3)

- `lucide("trash-2", size=16, color_token="color.neutral.700")` returns a non-null `QIcon`.
- The same call repeated returns the same `QIcon` (cache hit, identity comparison via `id()` is acceptable).
- `lucide("plus", color_token="color.accent.default")` returns an icon tinted with the accent blue.
- `lucide("nonexistent")` raises `FileNotFoundError`.

## Step 4 — Modal elevation infrastructure

### 4.1 `ui/elevation.py`

Create with a single public function:

```python
def apply_dialog_shadow(dialog: QDialog) -> None:
    """Apply the design system's modal drop shadow to a dialog."""
```

Implementation: construct a `QGraphicsDropShadowEffect`, set offset (X=0, Y=4), blur radius (16), and color (resolve `shadow.dialog` token: `color.neutral.900` at 25% alpha — encode as a `QColor` with RGBA). Apply via `dialog.setGraphicsEffect(effect)`.

### 4.2 `ui/widgets/modal_backdrop.py`

Create with:

```python
class ModalBackdropOverlay(QWidget):
    """Full-window overlay dimming the main window when a modal is open."""

def attach(dialog: QDialog) -> None:
    """Register a dialog as currently-open; show the overlay if hidden."""

def detach(dialog: QDialog) -> None:
    """Deregister a dialog; hide the overlay if no other modals are open."""
```

Internal state: a module-level `_active_dialogs: set[QDialog]` plus a single `_overlay: ModalBackdropOverlay | None` instance.

`ModalBackdropOverlay` implementation:

- Subclasses `QWidget` with `Qt.WidgetAttribute.WA_TransparentForMouseEvents` so the overlay does not intercept clicks (clicks should reach the dialog's modal-blocking mechanism, not the overlay).
- `paintEvent` fills the widget with `t("color.neutral.900")` at 8% alpha (the `overlay.modal_backdrop` token; resolve the alpha by parsing the token value).
- Parented to `QApplication.activeWindow().centralWidget()` on first `attach()` call. The parent's `resizeEvent` triggers an overlay `.resize()` to match.
- Fade-in via `QPropertyAnimation` on `windowOpacity` with a 150ms duration on `attach()`. Fade-out via the same mechanism on `detach()` when `_active_dialogs` becomes empty.

`attach(dialog)` adds to the set, ensures the overlay is constructed and parented, shows it, and starts the fade-in animation. `detach(dialog)` removes from the set; if empty, starts the fade-out and hides on completion.

### 4.3 Acceptance verification (Step 4)

- `from crmbuilder_v2.ui.elevation import apply_dialog_shadow` succeeds.
- `from crmbuilder_v2.ui.widgets.modal_backdrop import ModalBackdropOverlay, attach, detach` succeeds.
- Standalone smoke test: open a `QDialog`, call `apply_dialog_shadow(dialog)` and `attach(dialog)`; the dialog renders with a visible drop shadow and the backdrop overlay appears.

## Step 5 — Per-dialog elevation + backdrop hooks

Modify the **six** files below to add `apply_dialog_shadow(self)` in the dialog's `__init__` after `super().__init__(...)`, plus override `showEvent` and `hideEvent` to call `attach(self)` and `detach(self)` respectively.

The three dialog base classes (steps 5.1–5.3) carry the hooks for every subclass via inheritance. The three standalone `QDialog` subclasses (steps 5.4–5.6) carry their own hooks because they don't inherit from any of the bases.

### 5.1 `ui/base/crud_dialog.py`

Both `EntityCrudDialog` and `EntityCrudDeleteDialog` live in this file. Add the hooks to both classes' `__init__` / `showEvent` / `hideEvent`. The repeating pattern can be factored into a small helper if useful (e.g., a `_register_modal()` method); the slice-A prompt-runner decides whether the factoring is worth doing or whether the per-class inline calls are cleaner.

### 5.2 `ui/base/versioned_replace_dialog.py`

Same pattern. Carries the hooks for `CharterReplaceDialog` and `StatusReplaceDialog` via inheritance.

### 5.3 `ui/base/list_detail_panel.py`

`ListDetailPanel` is NOT a `QDialog` — it's a panel widget. It does NOT get the elevation or backdrop hooks. (Listed here only to be explicit about the exclusion; the file IS modified in this slice but for chrome hooks per Step 6, not for modal hooks.)

### 5.4 `ui/about_dialog.py`

`AboutDialog` inherits from `QDialog` directly. Add the hooks per the pattern.

### 5.5 `ui/dialogs/error.py`

`ErrorDialog` inherits from `QDialog` directly. Same pattern.

### 5.6 `ui/dialogs/reference_delete.py`

`ReferenceDeleteDialog` inherits from `QDialog` directly (not from `EntityCrudDeleteDialog` — verify this in source before applying the hook). Same pattern.

### 5.7 Acceptance verification (Step 5)

- Opening the existing v0.5 Decision-edit dialog renders with a drop shadow; the main window dims behind it; closing the dialog removes the shadow and hides the backdrop.
- Opening the existing v0.5 Decision-delete dialog (which uses `EntityCrudDeleteDialog`) renders with shadow + backdrop.
- Opening the Reference-create dialog (which inherits from `EntityCrudDialog`) renders with shadow + backdrop without any additional code (verifies the hook propagates via the base).
- Opening the Charter-replace dialog (which uses `VersionedReplaceDialog`) renders with shadow + backdrop.
- Opening the About dialog, the Error dialog, and the Reference-delete dialog renders each with shadow + backdrop.

## Step 6 — `list_detail_panel.py` chrome hooks

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/base/list_detail_panel.py` to:

- Set the panel content background to `color.neutral.50` via a class-name hook readable by the project-level QSS. Concretely: set `self.setObjectName("listDetailPanel")` (or equivalent) and add a corresponding rule to `build_app_stylesheet()` in Step 1.4 — `QWidget#listDetailPanel { background: <neutral.50>; }`. Outer padding 16px (`space.4`) via QSS or layout margin.
- Configure the existing `QSplitter` (master/detail) with `space.3` (12px) handle width via `setHandleWidth(12)`.
- The default split ratio (45/55 master/detail per design pass §2.2) — apply via `setSizes()` after the splitter is constructed. Existing `restoreState()` mechanism is preserved for user-adjusted layouts.

Label-above form layout is OUT of slice A — slice C handles it.

### 6.1 Acceptance verification (Step 6)

- The existing v0.5 panels render with the new panel background (`color.neutral.50`).
- The master/detail splitter handle is visibly wider (12px) than v0.5's default.
- The default 45/55 split applies to fresh panels (no saved state).

## Step 7 — App startup wiring in `ui/app.py`

Confirm the existing `apply_stylesheet(app)` call site in `ui/app.py` moves to AFTER the font loading added in Step 2. The order of operations at app startup is:

1. Construct `QApplication`.
2. Load Inter and JetBrains Mono via `QFontDatabase.addApplicationFont()`.
3. Call `apply_stylesheet(app)` — generates and applies the QSS string from `TOKENS["light"]`.
4. Construct the splash screen.
5. Construct the main window.

### 7.1 Acceptance verification (Step 7)

- App launches and renders with Inter as the default font (visible in any text label).
- App launches and renders with the new color tokens (visible in `QLineEdit` borders, button chrome, list backgrounds).
- v0.5 functional behavior is unchanged.

## Step 8 — Splash screen migration

Modify `crmbuilder-v2/src/crmbuilder_v2/ui/splash.py`:

- Change imports from `ACCENT_COLOR, DEFAULT_FONT_FAMILY` to `t` (and `TOKENS` if needed).
- Update the `pixmap.fill(QColor(ACCENT_COLOR))` call site to `pixmap.fill(QColor(t("color.accent.default")))`.
- Update the `QFont(DEFAULT_FONT_FAMILY, 14)` call site to `QFont(t("font.family.default"), 14)`.

### 8.1 Acceptance verification (Step 8)

- The splash screen renders with the new accent blue (`#1F5FBF`) rather than the legacy navy (`#1F3864`).
- The splash message renders in Inter (loaded in Step 2) — though at the 14pt size set in splash code.

## Step 9 — About dialog re-skin

Restructure `crmbuilder-v2/src/crmbuilder_v2/ui/about_dialog.py` per design pass §2.8 and DEC-094.

### 9.1 New layout

Replace the existing `QFormLayout` structure with a `QVBoxLayout` containing three sections:

1. **Header block** (top of dialog body):
   - Wordmark: `QLabel` with text `"CRMBuilder v2"`, font set to Inter at `font.size.heading_2` (22px), weight semibold (600), color `color.neutral.900`. Use `t()` accessor for the color value; set font via `QFont` API.
   - Tagline: `QLabel` with text `"Declarative CRM deployment and methodology authoring"`, font at `font.size.small` (13px), weight regular, color `color.neutral.500`.
   - `space.1` (4px) vertical space between wordmark and tagline.
   - `space.4` (16px) vertical space below the header block.

2. **Metadata list** (vertical two-line-per-row structure):
   - Each metadata item gets two lines:
     - Line 1: the label in `font.size.small` (13px), weight medium (500), color `color.neutral.500` — examples: `"Application"`, `"Version"`, `"API base url"`, `"Database path"`, `"Snapshot directory"`. Sentence-cased.
     - Line 2: the value in `font.size.body` (14px), color `color.neutral.800`. Paths and URLs use `font.family.mono` (JetBrains Mono) at `font.size.small` (13px), color `color.neutral.700`.
   - `space.3` (12px) vertical space between metadata rows.
   - Values remain selectable: `Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard` (preserves the existing v0.5 behavior so users can copy paths).

3. **Action row** (bottom of dialog body):
   - Single `QPushButton` with label `"Close"`. Secondary button category (no explicit property assignment needed in slice A — Secondary is the default).
   - Right-aligned via `QHBoxLayout` with a stretch on the left.

### 9.2 Dialog chrome

- Container background: `color.neutral.0` (white, default Qt).
- Inner padding: `space.5` (20px) on all sides — set via `QVBoxLayout.setContentsMargins(20, 20, 20, 20)`.
- Minimum width preserved at 440px from current code.
- No internal context strip (About is not a record-editing dialog).
- Drop shadow + backdrop overlay applied via the hooks added in Step 5.4.

### 9.3 Acceptance verification (Step 9)

- Help → About menu opens the dialog.
- Dialog renders with: wordmark visible, tagline below it, metadata rows rendered as two-line-per-row vertical list with mono-font paths, single Close button right-aligned.
- Dialog has visible drop shadow.
- Main window dims behind the dialog when open.
- Clicking Close dismisses the dialog and the backdrop fades out.
- Metadata values are selectable (highlight by drag).

## Commit message template

```
v2: ui v0.6 slice A — foundation infrastructure + About dialog

Discharges the foundational layer of PI-001 per ui-PRD-v0.6.md §2
items 1-6 plus item 11 (About dialog).

Token system (ui/styling.py):
- Rewritten in place; v0.1 minimal QSS stub replaced end-to-end
- TOKENS dict (theme-keyed per DEC-088); 'light' theme codifies every
  value from styling-design-pass.md §1
- t() accessor; build_app_stylesheet() generator; apply_stylesheet(app)
  entry point preserved (consumers in app.py unchanged)
- Legacy ACCENT_COLOR / ACCENT_HOVER / ERROR_TEXT_COLOR /
  DEFAULT_FONT_FAMILY / DEFAULT_FONT_POINT_SIZE constants removed

Asset bundling (ui/assets/):
- fonts/: Inter Variable + JetBrains Mono Variable per DEC-090; OFL
  license bundled
- icons/lucide/: 14 SVG initial wave per DEC-092; ISC license bundled
- ui/icons.py: lucide(name, size, color_token) loader with runtime
  color tinting and (name, size, color_token) caching

Modal elevation (DEC-091):
- ui/elevation.py: apply_dialog_shadow(dialog) helper using
  QGraphicsDropShadowEffect per shadow.dialog token
- ui/widgets/modal_backdrop.py: ModalBackdropOverlay widget plus
  attach()/detach() module functions; parented to centralWidget;
  fade-in via QPropertyAnimation on windowOpacity

Per-dialog hooks (six files):
- ui/base/crud_dialog.py (covers EntityCrudDialog + EntityCrudDeleteDialog)
- ui/base/versioned_replace_dialog.py (covers Charter + Status replace)
- ui/about_dialog.py (standalone)
- ui/dialogs/error.py (standalone)
- ui/dialogs/reference_delete.py (standalone)
- ui/base/list_detail_panel.py (chrome hooks, NOT modal hooks)

App startup (ui/app.py):
- Loads bundled fonts before main window via QFontDatabase
- Calls apply_stylesheet(app) after fonts load

Splash migration (ui/splash.py):
- ACCENT_COLOR / DEFAULT_FONT_FAMILY usages migrated to t() accessor

About dialog (ui/about_dialog.py):
- Restructured per design pass §2.8 and DEC-094: wordmark + tagline
  header + vertical two-line metadata list + single right-aligned
  Close button
- Acts as canary surface exercising the full token system end-to-end

Next: slice B (sidebar + master-pane delegate).

No schema changes; no API changes; v0.5 test suite remains green.
```

After committing, run:

- `git push origin main`
- Notify Doug that slice A is complete and ready for screenshot capture per the protocol in implementation plan §7. Doug will capture `styling-screenshots/slice-A/about-dialog.png` and commit it as a separate operator commit.

## Out of slice

- Sidebar visual treatment (slice B).
- Master-pane delegate (slice B).
- Per-panel chrome retoken (slice C).
- Label-above form layout (slice C).
- `ReferencesSection` restructure (slice C).
- Button categories beyond Secondary default (slice D).
- Form-control state coverage beyond default chrome (slice D).
- Internal context strip on record-editing dialogs (slice D).
- Delete-confirm dialog body treatment (slice D).
- Inline form-field error styling (slice D).
- Status / error / warning surfaces (slice E).
- Crash banner re-skin (slice E).
- `__version__` bump (slice F).
- README v0.6 release note (slice F).
- WCAG contrast test module (slice F).
- Status entity versioned-replace to "v0.6 complete" (operator-authored after slice F).
- SES-030 session record application (operator-authored after slice F via apply-close-out prompt).

---

*End of slice A prompt.*
