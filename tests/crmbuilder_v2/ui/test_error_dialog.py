"""Tests for the generic ErrorDialog (slice G)."""

from __future__ import annotations

from crmbuilder_v2.ui.dialogs.error import ErrorDialog


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
