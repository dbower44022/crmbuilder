"""Design tokens and project-level QSS for the v2 desktop UI.

Discharges PI-001 — the full styling design pass deferred at v0.1
close per DEC-024 and reopened as the v0.6 parallel workstream per
DEC-076.

Earlier versions of this module were a minimal QSS stub: a navy accent
on a few selection highlights, Arial 10pt default, and a single error-
text color. v0.6 rewrites the file end-to-end with the theme-keyed
design token system specified in ``styling-design-pass.md`` §1. The
``apply_stylesheet(app)`` entry point is preserved so call sites in
``app.py`` do not change.

The token system has four public names:

* ``TOKENS`` — the theme-keyed dict. ``TOKENS["light"][key]`` returns
  the value for the named token. A ``"dark"`` theme can be added
  without consumer-code retrofit (DEC-088).
* ``t(key, theme="light")`` — accessor that returns a token value or
  raises ``KeyError`` naming the missing key.
* ``build_app_stylesheet(tokens)`` — generates the project-level QSS
  string from a single theme's dict. Accepts the inner dict (not the
  outer two-level structure) so the slice F WCAG contrast check can
  consume tokens directly without QSS generation.
* ``apply_stylesheet(app)`` — convenience wrapper that builds and
  applies the light-theme stylesheet to a ``QApplication``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

# Asset directory for SVGs referenced from QSS ``image: url(...)`` rules.
# QSS reads files from disk, not through ``ui.icons.lucide``'s runtime
# tinting; pre-tinted SVG variants (``check-neutral-0.svg`` etc.) are
# committed under this directory and the absolute path is interpolated
# into the stylesheet at build time so the URL works regardless of cwd.
_ICON_ASSET_DIR = (
    Path(__file__).resolve().parent / "assets" / "icons" / "lucide"
)


def _icon_url(filename: str) -> str:
    """Render an ``url(...)`` value for a bundled icon SVG.

    Qt accepts forward slashes on every platform and strips a ``file://``
    scheme; emitting just the absolute path keeps the rule portable.
    """
    return f"url({(_ICON_ASSET_DIR / filename).as_posix()})"

# ---------------------------------------------------------------------------
# Token dict — codified from styling-design-pass.md §1
# ---------------------------------------------------------------------------

TOKENS: dict[str, dict[str, str]] = {
    "light": {
        # Spacing scale — design pass §1.1, 4px base unit.
        "space.0": "0",
        "space.1": "4px",
        "space.2": "8px",
        "space.3": "12px",
        "space.4": "16px",
        "space.5": "20px",
        "space.6": "24px",
        "space.8": "32px",
        "space.10": "40px",
        "space.12": "48px",
        # Color — accent — design pass §1.2.2.
        "color.accent.default": "#1F5FBF",
        "color.accent.hover": "#2A6CCE",
        "color.accent.pressed": "#184F9F",
        "color.accent.subtle": "#E8F0FB",
        # Focus ring rendered as rgba so consumers can drop it
        # straight into QSS without recomputing the alpha.
        "color.accent.focusring": "rgba(31, 95, 191, 0.4)",
        # Color — neutral — design pass §1.2.3.
        "color.neutral.0": "#FFFFFF",
        "color.neutral.50": "#F7F9FB",
        "color.neutral.100": "#EEF1F5",
        "color.neutral.200": "#DDE3EA",
        "color.neutral.300": "#C1CAD4",
        "color.neutral.500": "#7A8694",
        "color.neutral.700": "#3F4854",
        "color.neutral.800": "#272D36",
        "color.neutral.900": "#0F1318",
        # Color — status — design pass §1.2.4.
        "color.danger.default": "#C0392B",
        "color.danger.text": "#A8281C",
        "color.danger.subtle": "#FBEBE8",
        "color.warning.default": "#B0731A",
        "color.warning.subtle": "#FBF2E0",
        "color.success.default": "#2D7A4D",
        # Typography — design pass §1.3.
        "font.family.default": "Inter",
        "font.family.mono": "JetBrains Mono",
        "font.size.caption": "12px",
        "font.size.small": "13px",
        "font.size.body": "14px",
        "font.size.body_large": "16px",
        "font.size.heading_3": "18px",
        "font.size.heading_2": "22px",
        "font.size.heading_1": "28px",
        "font.weight.regular": "400",
        "font.weight.medium": "500",
        "font.weight.semibold": "600",
        "font.weight.bold": "700",
        "font.line.tight": "1.2",
        "font.line.normal": "1.45",
        "font.line.relaxed": "1.6",
        # Radius and border — design pass §1.4.
        "radius.none": "0px",
        "radius.subtle": "3px",
        "radius.default": "6px",
        "radius.large": "10px",
        # Elevation — design pass §1.5. Encoded as a structural hint:
        # consumers (apply_dialog_shadow) read the underlying neutral.900
        # color plus the literal offset/blur values, not these strings.
        # The token presence here documents the design intent and lets
        # the WCAG check enumerate the elevation surface.
        "shadow.dialog": (
            "offset=(0,4) blur=16 color=#0F1318 alpha=0.25"
        ),
        "overlay.modal_backdrop": "color=#0F1318 alpha=0.08",
    }
}


def t(key: str, theme: str = "light") -> str:
    """Look up a token value by key; default to the light theme.

    Raises ``KeyError`` whose message names the offending key so a
    typo at a call site is easy to diagnose.
    """
    try:
        return TOKENS[theme][key]
    except KeyError as exc:
        missing = exc.args[0] if exc.args else key
        raise KeyError(
            f"Unknown design token: theme={theme!r}, key={missing!r}"
        ) from None


def build_app_stylesheet(tokens: dict[str, str]) -> str:
    """Build the project-level QSS string from a single theme's dict.

    Takes the inner theme dict (e.g. ``TOKENS["light"]``), not the
    outer two-level structure, so the WCAG contrast check in slice F
    can consume tokens directly.

    The QSS is intentionally minimal — only app-wide chrome that every
    widget picks up by default. Per-category buttons, sidebar
    treatment, master-pane delegate, ReferencesSection treatment, and
    per-panel chrome are all added in later slices.
    """

    def get(key: str) -> str:
        try:
            return tokens[key]
        except KeyError as exc:
            missing = exc.args[0] if exc.args else key
            raise KeyError(
                f"build_app_stylesheet: missing token {missing!r}"
            ) from None

    rules: list[str] = [
        # Default font + body color across every widget.
        f"""
* {{
    font-family: "{get('font.family.default')}";
    font-size: {get('font.size.body')};
    color: {get('color.neutral.800')};
}}
""",
        # Text inputs / combos default state.
        f"""
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    border: 1px solid {get('color.neutral.300')};
    background: {get('color.neutral.0')};
    padding: {get('space.1')} {get('space.2')};
    selection-background-color: {get('color.accent.subtle')};
    selection-color: {get('color.neutral.900')};
}}
""",
        # Focused state — accent border. The 2px-outside focus-ring per
        # design pass §2.4 is deferred: Qt's QSS ``outline`` property is
        # not reliably honored on input widgets, so the focused-border
        # alone carries the visual cue in v0.6.
        f"""
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {get('color.accent.default')};
}}
""",
        # Error state — toggled via the dynamic ``fieldState`` property
        # ``field.setProperty("fieldState", "error")``; consumers call
        # ``field.style().polish(field)`` afterward to re-evaluate the
        # selector. Qt has no native "error" pseudo-state, so the
        # property hook stands in for one.
        f"""
QLineEdit[fieldState="error"], QComboBox[fieldState="error"], QPlainTextEdit[fieldState="error"], QTextEdit[fieldState="error"] {{
    border: 1px solid {get('color.danger.default')};
}}
""",
        # Disabled state — gray background, washed-out text.
        f"""
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    background: {get('color.neutral.100')};
    border: 1px solid {get('color.neutral.200')};
    color: {get('color.neutral.300')};
}}
""",
        # Read-only treatment — distinct from disabled (text stays
        # legible, content can be selected/copied). Distinguishes a
        # field that is intentionally locked from one that is gated off.
        f"""
QLineEdit[readOnly="true"], QPlainTextEdit[readOnly="true"], QTextEdit[readOnly="true"] {{
    background: {get('color.neutral.100')};
    border: 1px solid {get('color.neutral.200')};
    color: {get('color.neutral.700')};
}}
""",
        # Form-label treatment per design pass §2.4 — small,
        # medium-weight, slightly muted, with a 4px breathing pad
        # above the field below. ``role="form-label"`` is tagged
        # on labels built by :func:`required_label` (the most
        # important target — required-field labels); a fallback
        # ``QFormLayout QLabel`` descendant selector covers the
        # auto-generated labels Qt creates for ``addRow(str, widget)``.
        f"""
QLabel[role="form-label"] {{
    font-size: {get('font.size.small')};
    font-weight: {get('font.weight.medium')};
    color: {get('color.neutral.700')};
    padding-top: {get('space.1')};
}}
QFormLayout QLabel {{
    font-size: {get('font.size.small')};
    font-weight: {get('font.weight.medium')};
    color: {get('color.neutral.700')};
    padding-top: {get('space.1')};
}}
""",
        # Status combo "Valid transitions" caption — sits directly
        # below a status combo on Domains, Entities, CRM Candidates.
        f"""
QLabel#statusHintCaption {{
    font-size: {get('font.size.caption')};
    color: {get('color.neutral.500')};
}}
""",
        # ReferencesSection sub-section headers (slice C — DEC-107).
        # The widget tags its kind-header QLabels with this role so the
        # styling lives here, not in per-widget setStyleSheet calls.
        f"""
QLabel[role="references-kind-header"] {{
    font-size: {get('font.size.small')};
    font-weight: {get('font.weight.semibold')};
    color: {get('color.neutral.700')};
}}
""",
        # Sidebar / generic list widgets pick up a subtle background.
        # Per-state (selected/hover) treatment lands in slice B; this
        # rule is harmless for non-sidebar QListWidgets.
        f"""
QListWidget {{
    background: {get('color.neutral.100')};
    border: 0;
}}
""",
        # Table view — no alternating rows per design pass §2.3.
        # Selected-state and row dividers land in slice B via the
        # shared master-pane delegate.
        f"""
QTableView {{
    background: {get('color.neutral.0')};
    gridline-color: {get('color.neutral.200')};
    selection-background-color: {get('color.accent.subtle')};
    selection-color: {get('color.neutral.900')};
}}
""",
        # Column header treatment.
        f"""
QHeaderView::section {{
    background: {get('color.neutral.100')};
    border: 0;
    border-bottom: 1px solid {get('color.neutral.200')};
    padding: {get('space.2')} {get('space.3')};
    color: {get('color.neutral.700')};
    font-weight: {get('font.weight.semibold')};
}}
""",
        # Default QPushButton — Secondary category per §2.5.
        # Per-category property selectors (primary / destructive /
        # text / icon-only) are added in slice D below.
        f"""
QPushButton {{
    background: transparent;
    border: 1px solid {get('color.neutral.300')};
    color: {get('color.neutral.700')};
    font-weight: {get('font.weight.medium')};
    padding: {get('space.1')} {get('space.3')};
    border-radius: {get('radius.subtle')};
    min-width: 88px;
}}
QPushButton:hover {{
    background: {get('color.neutral.100')};
}}
QPushButton:pressed {{
    background: {get('color.neutral.200')};
}}
QPushButton:focus {{
    border: 1px solid {get('color.accent.default')};
    outline: none;
}}
QPushButton:disabled {{
    background: transparent;
    border: 1px solid {get('color.neutral.200')};
    color: {get('color.neutral.300')};
}}
""",
        # Primary category — accent fill, white text. Used for Save in
        # CRUD dialogs, Apply in versioned-replace, and the panel-level
        # "New X" toolbar buttons. Per design pass §2.5.
        f"""
QPushButton[buttonCategory="primary"] {{
    background: {get('color.accent.default')};
    color: {get('color.neutral.0')};
    border: 1px solid {get('color.accent.default')};
    padding: {get('space.1')} {get('space.3')};
    border-radius: {get('radius.subtle')};
    font-weight: {get('font.weight.medium')};
    min-width: 88px;
}}
QPushButton[buttonCategory="primary"]:hover {{
    background: {get('color.accent.hover')};
    border: 1px solid {get('color.accent.hover')};
}}
QPushButton[buttonCategory="primary"]:pressed {{
    background: {get('color.accent.pressed')};
    border: 1px solid {get('color.accent.pressed')};
}}
QPushButton[buttonCategory="primary"]:focus {{
    border: 1px solid {get('color.accent.pressed')};
    outline: none;
}}
QPushButton[buttonCategory="primary"]:disabled {{
    background: {get('color.neutral.300')};
    border: 1px solid {get('color.neutral.300')};
    color: {get('color.neutral.500')};
}}
""",
        # Destructive category — danger fill, white text. Used for
        # Delete in CRUD-delete dialogs and the reference-delete dialog.
        # Replaces the legacy inline ``#c1272d`` / ``#b6868a`` blocks.
        f"""
QPushButton[buttonCategory="destructive"] {{
    background: {get('color.danger.default')};
    color: {get('color.neutral.0')};
    border: 1px solid {get('color.danger.default')};
    padding: {get('space.1')} {get('space.3')};
    border-radius: {get('radius.subtle')};
    font-weight: {get('font.weight.medium')};
    min-width: 88px;
}}
QPushButton[buttonCategory="destructive"]:hover {{
    background: #A93226;
    border: 1px solid #A93226;
}}
QPushButton[buttonCategory="destructive"]:pressed {{
    background: #922B1F;
    border: 1px solid #922B1F;
}}
QPushButton[buttonCategory="destructive"]:focus {{
    border: 1px solid #922B1F;
    outline: none;
}}
QPushButton[buttonCategory="destructive"]:disabled {{
    background: {get('color.neutral.300')};
    border: 1px solid {get('color.neutral.300')};
    color: {get('color.neutral.500')};
}}
""",
        # Text / Link category — transparent, accent text. Used for
        # inline affordances inside a content area (the ReferencesSection
        # "Add reference" button is the canonical example).
        f"""
QPushButton[buttonCategory="text"] {{
    background: transparent;
    border: 0;
    color: {get('color.accent.default')};
    font-weight: {get('font.weight.medium')};
    padding: {get('space.1')} {get('space.2')};
    min-width: 0;
    text-align: left;
}}
QPushButton[buttonCategory="text"]:hover {{
    color: {get('color.accent.hover')};
    text-decoration: underline;
}}
QPushButton[buttonCategory="text"]:pressed {{
    color: {get('color.accent.pressed')};
}}
QPushButton[buttonCategory="text"]:disabled {{
    color: {get('color.neutral.300')};
}}
""",
        # Icon-only category — 28×28 transparent square. Used for the
        # panel Refresh button. The fixed size is set at construction
        # time in :func:`icon_button`; this rule supplies the chrome.
        f"""
QPushButton[buttonCategory="icon-only"] {{
    background: transparent;
    border: 0;
    padding: 0;
    min-width: 0;
    border-radius: {get('radius.subtle')};
}}
QPushButton[buttonCategory="icon-only"]:hover {{
    background: {get('color.neutral.100')};
}}
QPushButton[buttonCategory="icon-only"]:pressed {{
    background: {get('color.neutral.200')};
}}
QPushButton[buttonCategory="icon-only"]:focus {{
    background: {get('color.neutral.100')};
    outline: none;
}}
""",
        # Combo dropdown chrome — design pass §2.6. The closed combo
        # reads from the slice-A default rules above; this block adds
        # the right-side chevron icon, popup container, and per-item
        # styling. The chevron asset is a pre-tinted SVG variant
        # bundled at ``assets/icons/lucide/chevron-down-neutral-500.svg``
        # because Qt's QSS ``image: url(...)`` reads files rather than
        # invoking the runtime tinting in ``ui.icons.lucide``.
        f"""
QComboBox {{
    padding-right: 24px;
}}
QComboBox::drop-down {{
    border: 0;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: top right;
}}
QComboBox::down-arrow {{
    image: {_icon_url("chevron-down-neutral-500.svg")};
    width: 14px;
    height: 14px;
}}
QComboBox QAbstractItemView {{
    background: {get('color.neutral.0')};
    border: 1px solid {get('color.neutral.300')};
    border-radius: {get('radius.subtle')};
    padding: {get('space.1')};
    selection-background-color: {get('color.accent.subtle')};
    selection-color: {get('color.neutral.900')};
    outline: 0;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: {get('space.2')} {get('space.3')};
    color: {get('color.neutral.800')};
}}
QComboBox QAbstractItemView::item:hover {{
    background: {get('color.neutral.100')};
    color: {get('color.neutral.900')};
}}
QComboBox QAbstractItemView::item:selected {{
    background: {get('color.accent.subtle')};
    color: {get('color.neutral.900')};
}}
""",
        # Checkbox custom indicator — design pass §2.6. The check
        # asset is a pre-tinted SVG variant bundled alongside the
        # chevron above (white for the checked state, neutral-300 for
        # disabled-checked).
        f"""
QCheckBox {{
    spacing: {get('space.2')};
    color: {get('color.neutral.800')};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {get('color.neutral.300')};
    border-radius: {get('radius.subtle')};
    background: {get('color.neutral.0')};
}}
QCheckBox::indicator:hover {{
    border: 1px solid {get('color.neutral.500')};
}}
QCheckBox::indicator:checked {{
    background: {get('color.accent.default')};
    border: 1px solid {get('color.accent.default')};
    image: {_icon_url("check-neutral-0.svg")};
}}
QCheckBox::indicator:checked:hover {{
    background: {get('color.accent.hover')};
    border: 1px solid {get('color.accent.hover')};
}}
QCheckBox::indicator:disabled {{
    background: {get('color.neutral.100')};
    border: 1px solid {get('color.neutral.200')};
}}
QCheckBox::indicator:checked:disabled {{
    background: {get('color.neutral.100')};
    border: 1px solid {get('color.neutral.200')};
    image: {_icon_url("check-neutral-300.svg")};
}}
QCheckBox:disabled {{
    color: {get('color.neutral.300')};
}}
""",
        # Inline error label hook used by EntityCrudDialog.
        f"""
QLabel[role="error"] {{
    color: {get('color.danger.text')};
}}
""",
        # WarningCallout text label (slice E — design pass §2.9).
        # Amber-toned informational warning, distinct from danger-red.
        f"""
QLabel#warningCalloutText {{
    font-size: {get('font.size.small')};
    color: {get('color.warning.default')};
}}
""",
        # Error dialog header (slice E — design pass §2.9). Sits to the
        # right of the circle-x icon in the header row; uses heading-3
        # semibold danger-text per the design pass.
        f"""
QLabel#errorDialogHeader {{
    font-size: {get('font.size.heading_3')};
    font-weight: {get('font.weight.semibold')};
    color: {get('color.danger.text')};
}}
""",
        # Panel chrome — content background for ListDetailPanel.
        # Slice A adds the objectName hook on the panel widget itself;
        # see ui/base/list_detail_panel.py.
        f"""
QWidget#listDetailPanel {{
    background: {get('color.neutral.50')};
}}
""",
        # Internal context strip on edit-mode CRUD dialogs (design
        # pass §2.7). Tinted band sitting at the top of the dialog
        # body that shows the record identifier (mono) plus the record
        # name. Excluded from create-mode, delete-confirm, About,
        # Error, ReferenceDelete dialogs — only edit-mode CRUD dialogs
        # set the ``dialogContextStrip`` objectName via
        # ``EntityCrudDialog._build_context_strip``.
        f"""
QWidget#dialogContextStrip {{
    background: {get('color.neutral.100')};
    border-bottom: 1px solid {get('color.neutral.200')};
}}
QLabel#dialogContextStripIdentifier {{
    font-family: "{get('font.family.mono')}";
    font-size: {get('font.size.small')};
    color: {get('color.neutral.700')};
    font-weight: {get('font.weight.medium')};
}}
QLabel#dialogContextStripName {{
    font-size: {get('font.size.body')};
    color: {get('color.neutral.800')};
}}
""",
        # Delete-confirm dialog body label — design pass §2.7's
        # relaxed line height. Tagged via ``role="delete-body"`` on
        # the body QLabel inside both ``EntityCrudDeleteDialog`` and
        # the standalone ``ReferenceDeleteDialog``.
        f"""
QLabel[role="delete-body"] {{
    font-size: {get('font.size.body')};
    color: {get('color.neutral.800')};
    line-height: {get('font.line.relaxed')};
}}
""",
    ]

    return "\n".join(rule.strip() for rule in rules) + "\n"


def apply_stylesheet(app: QApplication) -> None:
    """Apply the project-level light-theme stylesheet to the application."""
    app.setStyleSheet(build_app_stylesheet(TOKENS["light"]))
