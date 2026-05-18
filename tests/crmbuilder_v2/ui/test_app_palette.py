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
    # build_application applies the project QSS after setStyle("Fusion"),
    # which wraps the style in Qt's internal QStyleSheetStyle proxy.
    # Clearing the stylesheet exposes the underlying base style so we
    # can assert it's Fusion via its objectName.
    app.setStyleSheet("")
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
