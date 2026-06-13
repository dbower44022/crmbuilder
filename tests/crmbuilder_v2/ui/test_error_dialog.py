"""Tests for the generic ErrorDialog (slice G)."""

from __future__ import annotations

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.widgets.selectable_text import SELECTABLE_TEXT_FLAGS
from PySide6.QtWidgets import QLabel


def test_error_dialog_without_detail_has_no_disclosure(qtbot):
    dialog = ErrorDialog(
        title="Could not save",
        message="Something went wrong.",
    )
    qtbot.addWidget(dialog)
    assert dialog.findChild(object, "error_detail_toggle") is None
    assert dialog.findChild(object, "error_detail_text") is None


def test_error_dialog_with_detail_has_disclosure_collapsed(qtbot):
    dialog = ErrorDialog(
        title="Could not save",
        message="Something went wrong.",
        detail="Traceback: ...",
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    button = dialog.findChild(object, "error_detail_toggle")
    text = dialog.findChild(object, "error_detail_text")
    assert button is not None
    assert text is not None
    # Default collapsed: detail widget is hidden.
    assert text.isHidden() is True
    # Toggling reveals the detail text.
    button.toggle()
    assert text.isHidden() is False


def test_error_dialog_ok_button_closes(qtbot):
    dialog = ErrorDialog(title="Whoops", message="x")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.accept()
    assert dialog.isVisible() is False


def test_error_dialog_without_action_has_no_action_button(qtbot):
    dialog = ErrorDialog(title="t", message="m")
    qtbot.addWidget(dialog)
    assert dialog.findChild(object, "error_action_button") is None


def test_error_dialog_title_and_message_are_selectable(qtbot):
    """PI-124 (WTK-144): the header and message text are copyable."""
    dialog = ErrorDialog(
        title="Could not save",
        message="Something went wrong.",
    )
    qtbot.addWidget(dialog)
    labels = {label.text(): label for label in dialog.findChildren(QLabel)}
    for text in ("Could not save", "Something went wrong."):
        flags = labels[text].textInteractionFlags()
        assert flags & SELECTABLE_TEXT_FLAGS == SELECTABLE_TEXT_FLAGS


def test_error_dialog_action_button_invokes_callback_and_closes(qtbot):
    """Slice B (B7): the optional action button closes the dialog, then runs."""
    calls: dict = {"n": 0}

    def cb() -> None:
        calls["n"] += 1

    dialog = ErrorDialog(
        title="Cannot save — export directory issue",
        message="no export dir",
        action_text="Edit engagement…",
        action_callback=cb,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    button = dialog.findChild(object, "error_action_button")
    assert button is not None
    assert button.text() == "Edit engagement…"
    button.click()
    assert calls["n"] == 1
    assert dialog.isVisible() is False
