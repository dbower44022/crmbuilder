"""Tests for the EntityIdentifierPicker widget — v0.3 slice C."""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.entity_identifier_picker import (
    EntityIdentifierPicker,
)
from PySide6.QtCore import Qt


def _make(qtbot) -> EntityIdentifierPicker:
    picker = EntityIdentifierPicker()
    qtbot.addWidget(picker)
    return picker


def test_set_entries_populates_combo(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First decision"), ("DEC-002", "Second")])
    assert picker.count() == 2
    assert picker.itemText(0) == "DEC-001 — First decision"
    assert picker.itemText(1) == "DEC-002 — Second"


def test_set_entries_renders_identifier_only_when_title_blank(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "")])
    assert picker.itemText(0) == "DEC-001"


def test_set_entries_clears_existing(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First")])
    picker.set_entries([("SES-001", "First session")])
    assert picker.count() == 1
    assert picker.itemText(0) == "SES-001 — First session"


def test_selected_identifier_returns_id_for_active_index(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First"), ("DEC-002", "Second")])
    picker.setCurrentIndex(1)
    assert picker.selected_identifier() == "DEC-002"


def test_selected_identifier_returns_none_for_unmatched_text(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First")])
    picker.setCurrentIndex(-1)
    picker.setEditText("nonsense that doesn't match anything")
    assert picker.selected_identifier() is None


def test_selected_identifier_returns_none_when_empty(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First")])
    picker.setCurrentIndex(-1)
    picker.setEditText("")
    assert picker.selected_identifier() is None


def test_selected_identifier_resolves_identifier_only_text(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First")])
    picker.setCurrentIndex(-1)
    picker.setEditText("DEC-001")
    assert picker.selected_identifier() == "DEC-001"


def test_clear_selection_blanks_widget(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First")])
    picker.setCurrentIndex(0)
    picker.clear_selection()
    assert picker.currentIndex() == -1
    assert picker.currentText() == ""


def test_completer_match_contains(qtbot):
    """Completer's match-contains filter accepts substrings of identifier or title."""
    picker = _make(qtbot)
    picker.set_entries(
        [("DEC-001", "Storage architecture"), ("DEC-002", "UI architecture")]
    )
    completer = picker.completer()
    assert completer.filterMode() == Qt.MatchFlag.MatchContains
    # The completer's model is the picker's model; both items are
    # available to it for filtering.
    assert completer.model().rowCount() == 2


def test_selection_changed_signal_emitted_on_activation(qtbot):
    picker = _make(qtbot)
    picker.set_entries([("DEC-001", "First"), ("DEC-002", "Second")])
    received: list[str] = []
    picker.selection_changed.connect(received.append)
    # ``activated`` fires when an item is selected through the dropdown
    # or completer; we emit it directly to simulate that.
    picker.activated.emit(1)
    assert received == ["DEC-002"]


# ---------------------------------------------------------------------------
# Opened list: single-spaced rows and an in-list search box
# (REQ-564 / REQ-565, PI-465)
# ---------------------------------------------------------------------------


def _picker_with_many(qtbot, n: int = 40):
    picker = EntityIdentifierPicker()
    qtbot.addWidget(picker)
    picker.set_entries(
        [(f"PI-{i:03d}", f"Planning item number {i}") for i in range(1, n + 1)]
    )
    return picker


def test_popup_rows_are_single_spaced(qtbot):
    """REQ-564: an opened row is one text line high, not the stock
    28-pixel-plus-padding row."""
    picker = _picker_with_many(qtbot)
    picker.showPopup()
    popup = picker.popup()
    row = popup.view.sizeHintForRow(0)
    line = popup.view.fontMetrics().height()
    assert row <= line + 6, (row, line)
    picker.hidePopup()


def test_popup_shows_a_search_box_at_the_top(qtbot):
    picker = _picker_with_many(qtbot)
    picker.showPopup()
    popup = picker.popup()
    assert popup.search.isVisible()
    assert popup.search.hasFocus() or popup.isVisible()
    assert popup.visible_count() == 40
    picker.hidePopup()


def test_popup_search_narrows_rows_by_identifier_or_name(qtbot):
    """REQ-565: typing narrows to rows whose identifier or name contains
    the text; clearing restores the full list."""
    picker = _picker_with_many(qtbot)
    picker.showPopup()
    popup = picker.popup()
    popup.search.setText("number 3")
    assert popup.visible_count() == 11  # 3, 30..39
    popup.search.setText("PI-012")
    assert popup.visible_count() == 1
    popup.search.setText("")
    assert popup.visible_count() == 40
    picker.hidePopup()


def test_popup_choose_selects_row_and_fires_signals(qtbot):
    picker = _picker_with_many(qtbot)
    picker.showPopup()
    popup = picker.popup()
    popup.search.setText("number 7")
    with qtbot.waitSignal(picker.selection_changed, timeout=1000) as blocker:
        popup.choose(popup.proxy.index(0, 0))
    assert blocker.args == ["PI-007"]
    assert picker.selected_identifier() == "PI-007"
    assert picker.currentText() == "PI-007 — Planning item number 7"
    assert not popup.isVisible()


def test_popup_enter_picks_first_visible_match(qtbot):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    picker = _picker_with_many(qtbot)
    picker.showPopup()
    popup = picker.popup()
    popup.search.setText("PI-025")
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(popup.search, event)
    assert picker.selected_identifier() == "PI-025"
    assert not popup.isVisible()


def test_popup_escape_closes_without_selecting(qtbot):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    picker = _picker_with_many(qtbot)
    picker.clear_selection()
    picker.showPopup()
    popup = picker.popup()
    QApplication.sendEvent(
        popup.search,
        QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        ),
    )
    assert not popup.isVisible()
    assert picker.selected_identifier() is None


def test_popup_follows_new_entries(qtbot):
    picker = _picker_with_many(qtbot, 3)
    picker.showPopup()
    picker.hidePopup()
    picker.set_entries([("ENT-001", "Contact")])
    picker.showPopup()
    assert picker.popup().visible_count() == 1
    picker.hidePopup()
