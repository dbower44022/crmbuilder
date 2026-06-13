"""Tests for the CrashBanner selectable text + Copy button (PI-124 / WTK-144)."""

from __future__ import annotations

from crmbuilder_v2.ui.crash_banner import CrashBanner
from crmbuilder_v2.ui.widgets.selectable_text import SELECTABLE_TEXT_FLAGS
from PySide6.QtGui import QGuiApplication


def test_crash_banner_message_label_is_selectable(qtbot):
    banner = CrashBanner()
    qtbot.addWidget(banner)
    flags = banner._label.textInteractionFlags()
    assert flags & SELECTABLE_TEXT_FLAGS == SELECTABLE_TEXT_FLAGS


def test_crash_banner_copy_button_copies_current_message(qtbot):
    banner = CrashBanner()
    qtbot.addWidget(banner)
    banner.show_with_message("Reconnect failed after 3 attempt(s). See api.log.")

    button = banner.findChild(object, "crashBannerCopy")
    assert button is not None
    button.click()

    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "Reconnect failed after 3 attempt(s). See api.log."


def test_crash_banner_copy_button_does_not_hide_banner(qtbot):
    # Copy is non-destructive — unlike Reconnect, it must not dismiss the
    # banner (the operator may still want to read or re-copy the message).
    banner = CrashBanner()
    qtbot.addWidget(banner)
    banner.show_with_message("Storage server stopped.")

    button = banner.findChild(object, "crashBannerCopy")
    button.click()
    assert banner.isHidden() is False
