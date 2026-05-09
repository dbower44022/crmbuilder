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
